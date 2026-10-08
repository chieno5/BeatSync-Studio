from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def analysis_key(path: Path, matcher: Any, max_width: int) -> str:
    stat = path.stat()
    payload = {
        "version": 1,
        "video": file_digest(path),
        "size": stat.st_size,
        "matcher": matcher.cache_identity,
        "width": max_width,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


class AnalysisCache:
    """Persist raw scores, including no-face and failed-decode samples, atomically."""

    def __init__(self, path: Path, key: str):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, timeout=30)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS samples ("
            "analysis TEXT, timestamp_us INTEGER, decoded INTEGER, score REAL, "
            "PRIMARY KEY (analysis, timestamp_us))"
        )
        self.key = key

    def load(self) -> dict[int, tuple[bool, float | None]]:
        return {
            timestamp: (bool(decoded), score)
            for timestamp, decoded, score in self.connection.execute(
                "SELECT timestamp_us, decoded, score FROM samples WHERE analysis = ?",
                (self.key,),
            )
        }

    def save(self, timestamp: int, decoded: bool, score: float | None) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT OR REPLACE INTO samples VALUES (?, ?, ?, ?)",
                (self.key, timestamp, int(decoded), score),
            )

    def close(self) -> None:
        self.connection.close()
