import unittest

from beatsync_studio.intervals import merge_match_samples, merge_overlapping_segments
from beatsync_studio.models import MatchSample, TimeSegment


class IntervalTests(unittest.TestCase):
    def test_empty_samples_return_no_segments(self):
        self.assertEqual(
            merge_match_samples([], max_gap=2, padding=1, duration=10, sample_interval=1), []
        )

    def test_samples_merge_and_are_bounded(self):
        samples = [
            MatchSample(0.2, 0.6),
            MatchSample(1.2, 0.8),
            MatchSample(5.0, 0.7),
        ]
        segments = merge_match_samples(
            samples, max_gap=1.5, padding=1.0, duration=6.0, sample_interval=1.0
        )
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0].start, 0.0)
        self.assertEqual(segments[0].end, 2.7)
        self.assertEqual(segments[0].peak_similarity, 0.8)
        self.assertEqual(segments[0].sample_count, 2)
        self.assertEqual(segments[1].end, 6.0)

    def test_invalid_sampling_values_fail(self):
        with self.assertRaises(ValueError):
            merge_match_samples([], max_gap=0, padding=0, duration=1, sample_interval=0)

    def test_overlaps_created_by_padding_are_merged(self):
        segments = merge_overlapping_segments(
            [
                TimeSegment(1.0, 4.0, 0.8, 2),
                TimeSegment(3.5, 6.0, 0.9, 3),
                TimeSegment(8.0, 9.0, 0.7, 1),
            ]
        )
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0], TimeSegment(1.0, 6.0, 0.9, 5))


if __name__ == "__main__":
    unittest.main()
