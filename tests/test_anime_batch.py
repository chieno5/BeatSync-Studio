from types import SimpleNamespace

import numpy as np
import pytest

from beatsync_studio.anime import AnimeCharacterMatcher


@pytest.mark.parametrize("batch, expected", [("batch", [3]), (1, [1, 1, 1]), (2, [2, 2])])
def test_batch_shapes_and_padding(batch, expected):
    calls = []

    class Model:
        def get_inputs(self):
            return [SimpleNamespace(shape=[batch, 3, 384, 384])]

        def run(self, outputs, inputs):
            data = inputs["input"]
            calls.append(len(data))
            return [data.reshape(len(data), -1)]

    matcher = AnimeCharacterMatcher.__new__(AnimeCharacterMatcher)
    matcher._np = np
    matcher.feature_model = Model()
    matcher.feature_input = "input"
    matcher._prepare_feature = lambda image, box: np.array([box[0]], dtype=np.float32)
    result = matcher._features(None, [(1, 0, 0, 0), (2, 0, 0, 0), (3, 0, 0, 0)])
    assert calls == expected
    np.testing.assert_array_equal(result[:, 0], [1, 2, 3])
