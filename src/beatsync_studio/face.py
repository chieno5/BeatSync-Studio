from __future__ import annotations

import os
import urllib.request
from collections.abc import Sequence
from pathlib import Path
from typing import Any

MODEL_URLS = {
    "anime_face_detect_v1.4_n.onnx": (
        "https://hub.deepghs.org/deepghs/anime_face_detection/resolve/main/"
        "face_detect_v1.4_n/model.onnx?download=true"
    ),
    "ccip_caformer2_feat.onnx": (
        "https://hub.deepghs.org/deepghs/ccip_onnx/resolve/main/"
        "ccip-caformer-2-randaug-pruned_fp32/model_feat.onnx"
    ),
    "ccip_caformer2_metrics.onnx": (
        "https://hub.deepghs.org/deepghs/ccip_onnx/resolve/main/"
        "ccip-caformer-2-randaug-pruned_fp32/model_metrics.onnx"
    ),
    "face_detection_yunet_2023mar.onnx": (
        "https://github.com/opencv/opencv_zoo/raw/main/models/"
        "face_detection_yunet/face_detection_yunet_2023mar.onnx"
    ),
    "face_recognition_sface_2021dec.onnx": (
        "https://github.com/opencv/opencv_zoo/raw/main/models/"
        "face_recognition_sface/face_recognition_sface_2021dec.onnx"
    ),
}

MODEL_SIZES = {
    "anime_face_detect_v1.4_n.onnx": 12_102_558,
    "ccip_caformer2_feat.onnx": 150_248_245,
    "ccip_caformer2_metrics.onnx": 1_618,
    "face_detection_yunet_2023mar.onnx": 232_589,
    "face_recognition_sface_2021dec.onnx": 38_696_353,
}


def _model_directory() -> Path:
    configured = os.environ.get("BEATSYNC_MODEL_DIR")
    return Path(configured) if configured else Path.cwd() / "models"


def _ensure_model(filename: str) -> Path:
    model_dir = _model_directory()
    model_dir.mkdir(parents=True, exist_ok=True)
    destination = model_dir / filename
    expected_size = MODEL_SIZES[filename]
    if destination.is_file() and destination.stat().st_size == expected_size:
        return destination
    destination.unlink(missing_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    print(f"Downloading model: {filename} ({expected_size / 1024 / 1024:.1f} MiB)")
    request = urllib.request.Request(
        MODEL_URLS[filename], headers={"User-Agent": "BeatSync-Studio/0.1"}
    )
    try:
        with (
            urllib.request.urlopen(request, timeout=60) as response,
            temporary.open("wb") as target,
        ):
            while block := response.read(1024 * 1024):
                target.write(block)
        actual_size = temporary.stat().st_size
        if actual_size != expected_size:
            raise RuntimeError(
                f"Incomplete model download for {filename}: expected {expected_size} bytes, "
                f"received {actual_size}"
            )
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return destination


class FaceMatcher:
    """OpenCV YuNet + SFace matcher with lazily downloaded ONNX models."""

    def __init__(self, reference_images: Sequence[Path]):
        if not reference_images:
            raise ValueError("At least one reference image is required")
        try:
            import cv2
            import numpy as np
        except ImportError as exc:
            raise RuntimeError(
                "Face dependencies are missing. Re-run the project setup script."
            ) from exc

        self._cv2 = cv2
        self._np = np
        detector_model = _ensure_model("face_detection_yunet_2023mar.onnx")
        recognizer_model = _ensure_model("face_recognition_sface_2021dec.onnx")
        self.detector = cv2.FaceDetectorYN.create(
            str(detector_model), "", (320, 320), 0.5, 0.3, 5000
        )
        self.recognizer = cv2.FaceRecognizerSF.create(str(recognizer_model), "")
        self.providers = ["OpenCV-DNN-CPU"]
        self.reference_embedding = self._build_reference(reference_images)

    def _detect(self, image: Any) -> Any:
        height, width = image.shape[:2]
        self.detector.setInputSize((width, height))
        _, faces = self.detector.detect(image)
        if faces is None:
            return []
        return faces

    def _feature(self, image: Any, face: Any) -> Any:
        aligned = self.recognizer.alignCrop(image, face)
        return self._normalize(self.recognizer.feature(aligned).reshape(-1))

    def _rotate_bound(self, image: Any, angle: float) -> Any:
        height, width = image.shape[:2]
        center = (width / 2.0, height / 2.0)
        matrix = self._cv2.getRotationMatrix2D(center, angle, 1.0)
        cosine = abs(matrix[0, 0])
        sine = abs(matrix[0, 1])
        output_width = int((height * sine) + (width * cosine))
        output_height = int((height * cosine) + (width * sine))
        matrix[0, 2] += output_width / 2.0 - center[0]
        matrix[1, 2] += output_height / 2.0 - center[1]
        return self._cv2.warpAffine(
            image,
            matrix,
            (output_width, output_height),
            borderMode=self._cv2.BORDER_REPLICATE,
        )

    def _best_reference_face(self, image: Any) -> tuple[Any, Any] | None:
        candidates = []
        for angle in (0, -15, 15, -30, 30, -45, 45):
            oriented = image if angle == 0 else self._rotate_bound(image, angle)
            faces = self._detect(oriented)
            if len(faces):
                face = max(faces, key=lambda item: float(item[2] * item[3]))
                candidates.append((float(face[14]), oriented, face))
        if not candidates:
            return None
        _, oriented, face = max(candidates, key=lambda item: item[0])
        return oriented, face

    def _build_reference(self, paths: Sequence[Path]) -> Any:
        embeddings = []
        for path in paths:
            image = self._cv2.imread(str(path))
            if image is None:
                raise ValueError(f"Cannot read reference image: {path}")
            detected = self._best_reference_face(image)
            if detected is None:
                raise ValueError(f"No face detected in reference image: {path}")
            oriented, face = detected
            embeddings.append(self._feature(oriented, face))
        return self._normalize(self._np.mean(embeddings, axis=0))

    def _normalize(self, embedding: Any) -> Any:
        norm = self._np.linalg.norm(embedding)
        if norm == 0:
            raise ValueError("Face model returned a zero-length embedding")
        return embedding / norm

    def best_similarity(self, frame: Any) -> float | None:
        faces = self._detect(frame)
        if len(faces) == 0:
            return None
        return max(
            float(self._np.dot(self.reference_embedding, self._feature(frame, face)))
            for face in faces
        )
