from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .cache import file_digest
from .face import _ensure_model


class AnimeCharacterMatcher:
    """Anime YOLO detection with CCIP character identity embeddings."""

    def __init__(self, reference_images: Sequence[Path]):
        if not reference_images:
            raise ValueError("At least one reference image is required")
        try:
            import cv2
            import numpy as np
            import onnxruntime as ort
        except ImportError as exc:
            raise RuntimeError(
                "Anime dependencies are missing. Install with: pip install -e .[anime]"
            ) from exc

        self._cv2 = cv2
        self._np = np
        detector_path = _ensure_model("anime_face_detect_v1.4_n.onnx")
        feature_path = _ensure_model("ccip_caformer2_feat.onnx")
        metrics_path = _ensure_model("ccip_caformer2_metrics.onnx")
        providers = ["CPUExecutionProvider"]
        self.detector = ort.InferenceSession(str(detector_path), providers=providers)
        self.feature_model = ort.InferenceSession(str(feature_path), providers=providers)
        self.metrics_model = ort.InferenceSession(str(metrics_path), providers=providers)
        self.detector_input = self.detector.get_inputs()[0].name
        self.feature_input = self.feature_model.get_inputs()[0].name
        self.metrics_input = self.metrics_model.get_inputs()[0].name
        self.providers = ["Anime-YOLO-CCIP-CPU"]

        embeddings = []
        for path in reference_images:
            image = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError(f"Cannot read reference image: {path}")
            boxes = self._detect(image)
            if not boxes:
                raise ValueError(f"No anime face detected in reference image: {path}")
            box = max(boxes, key=lambda item: (item[2] - item[0]) * (item[3] - item[1]))
            embeddings.append(self._feature(image, box))
        self.reference_embedding = self._merge(embeddings)
        self.cache_identity = {
            "engine": "anime.py-v1",
            "models": [
                file_digest(_ensure_model(name))
                for name in [
                    "anime_face_detect_v1.4_n.onnx",
                    "ccip_caformer2_feat.onnx",
                    "ccip_caformer2_metrics.onnx",
                ]
            ],
            "embedding": self.reference_embedding.tobytes().hex(),
        }

    def _letterbox(self, image: Any, size: int = 640) -> tuple[Any, float, int, int]:
        height, width = image.shape[:2]
        scale = min(size / width, size / height)
        resized_width = max(1, round(width * scale))
        resized_height = max(1, round(height * scale))
        resized = self._cv2.resize(image, (resized_width, resized_height))
        pad_x = (size - resized_width) // 2
        pad_y = (size - resized_height) // 2
        canvas = self._np.full((size, size, 3), 114, dtype=self._np.uint8)
        canvas[pad_y : pad_y + resized_height, pad_x : pad_x + resized_width] = resized
        return canvas, scale, pad_x, pad_y

    def _detect(self, image: Any, confidence: float = 0.25) -> list[tuple[int, int, int, int]]:
        canvas, scale, pad_x, pad_y = self._letterbox(image)
        blob = self._cv2.dnn.blobFromImage(canvas, 1.0 / 255.0, (640, 640), swapRB=True)
        predictions = self._np.squeeze(
            self.detector.run(None, {self.detector_input: blob.astype(self._np.float32)})[0]
        )
        if predictions.ndim != 2:
            raise RuntimeError(f"Unexpected anime detector output shape: {predictions.shape}")
        if predictions.shape[0] <= 10:
            predictions = predictions.T

        raw_boxes = []
        scores = []
        for row in predictions:
            score = float(row[4:].max())
            if score < confidence:
                continue
            center_x, center_y, width, height = map(float, row[:4])
            left = (center_x - width / 2.0 - pad_x) / scale
            top = (center_y - height / 2.0 - pad_y) / scale
            raw_boxes.append([int(left), int(top), int(width / scale), int(height / scale)])
            scores.append(score)

        indices = self._cv2.dnn.NMSBoxes(raw_boxes, scores, confidence, 0.7)
        image_height, image_width = image.shape[:2]
        boxes = []
        for index in indices:
            left, top, width, height = raw_boxes[int(index)]
            x0 = max(0, left)
            y0 = max(0, top)
            x1 = min(image_width, left + width)
            y1 = min(image_height, top + height)
            if x1 > x0 and y1 > y0:
                boxes.append((x0, y0, x1, y1))
        return boxes

    def _character_crop(self, image: Any, box: tuple[int, int, int, int]) -> Any:
        x0, y0, x1, y1 = box
        width = x1 - x0
        height = y1 - y0
        image_height, image_width = image.shape[:2]
        left = max(0, int(x0 - width * 0.9))
        right = min(image_width, int(x1 + width * 0.9))
        top = max(0, int(y0 - height * 0.7))
        bottom = min(image_height, int(y1 + height * 1.8))
        return image[top:bottom, left:right]

    def _prepare_feature(self, image: Any, box: tuple[int, int, int, int]) -> Any:
        crop = self._character_crop(image, box)
        rgb = self._cv2.cvtColor(crop, self._cv2.COLOR_BGR2RGB)
        rgb = self._cv2.resize(rgb, (384, 384), interpolation=self._cv2.INTER_AREA)
        data = rgb.transpose(2, 0, 1).astype(self._np.float32) / 255.0
        mean = self._np.asarray((0.48145466, 0.4578275, 0.40821073), dtype=self._np.float32)
        std = self._np.asarray((0.26862954, 0.26130258, 0.27577711), dtype=self._np.float32)
        data = (data - mean[:, None, None]) / std[:, None, None]
        return data

    def _features(self, image: Any, boxes: Sequence[tuple[int, int, int, int]]) -> Any:
        data = self._np.stack([self._prepare_feature(image, box) for box in boxes])
        batch = self.feature_model.get_inputs()[0].shape[0]
        # Respect fixed batch models; pad only the final chunk, then discard padding.
        chunk_size = batch if isinstance(batch, int) and batch > 0 else min(8, len(boxes))
        outputs = []
        for start in range(0, len(boxes), chunk_size):
            chunk = data[start : start + chunk_size]
            count = len(chunk)
            if isinstance(batch, int) and count < batch:
                chunk = self._np.concatenate(
                    [chunk, self._np.repeat(chunk[-1:], batch - count, axis=0)]
                )
            outputs.append(self.feature_model.run(None, {self.feature_input: chunk})[0][:count])
        return self._np.concatenate(outputs).astype(self._np.float32)

    def _feature(self, image: Any, box: tuple[int, int, int, int]) -> Any:
        return self._features(image, [box])[0]

    def _merge(self, embeddings: Sequence[Any]) -> Any:
        matrix = self._np.stack(embeddings).astype(self._np.float32)
        lengths = self._np.linalg.norm(matrix, axis=1)
        normalized = matrix / lengths[:, None]
        merged = normalized.mean(axis=0)
        return merged / self._np.linalg.norm(merged) * lengths.mean()

    def _similarity(self, candidate: Any) -> float:
        pair = self._np.stack([self.reference_embedding, candidate]).astype(self._np.float32)
        differences = self.metrics_model.run(None, {self.metrics_input: pair})[0]
        return 1.0 - float(differences[0, 1])

    def best_similarity(self, frame: Any) -> float | None:
        boxes = self._detect(frame)
        if not boxes:
            return None
        return max(self._similarity(feature) for feature in self._features(frame, boxes))
