import tempfile
import unittest
from pathlib import Path

from beatsync_studio.sources import discover_local_videos, normalize_bilibili_input


class SourceTests(unittest.TestCase):
    def test_normalize_bv_id_and_url(self):
        bv = "BV1ab411c7DE"
        self.assertEqual(normalize_bilibili_input(bv), (bv, f"https://www.bilibili.com/video/{bv}"))
        self.assertEqual(
            normalize_bilibili_input(f"https://www.bilibili.com/video/{bv}?p=109"),
            (f"{bv}_p109", f"https://www.bilibili.com/video/{bv}?p=109"),
        )

    def test_invalid_bv_fails(self):
        with self.assertRaises(ValueError):
            normalize_bilibili_input("not-a-bv")

    def test_discover_local_videos_is_recursive_and_filtered(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested = root / "nested"
            nested.mkdir()
            (root / "a.mp4").touch()
            (nested / "b.MKV").touch()
            (nested / "notes.txt").touch()
            self.assertEqual(discover_local_videos(root), [root / "a.mp4", nested / "b.MKV"])


if __name__ == "__main__":
    unittest.main()
