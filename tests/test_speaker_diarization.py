import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from pyannote.core import Annotation, Segment

from speaker_diarization import combine, run_multiple


def annotation(*turns):
    result = Annotation()
    for index, (start, end, label) in enumerate(turns):
        result[Segment(start, end), index] = label
    return result


class PipelineFixture:
    training = False

    def __init__(self, predictions):
        self._segmentation = SimpleNamespace(step=1.0)
        self.settings = {"clustering": {"threshold": 0.6, "Fb": 0.8}}
        self.predictions = iter(predictions)
        self.calls = []

    def parameters(self, *, instantiated):
        return self.settings

    def instantiate(self, settings):
        self.settings = settings

    def __call__(self, waveform, *, num_speakers, hook):
        self.calls.append(
            (waveform, num_speakers, self.settings, self._segmentation.step)
        )
        return SimpleNamespace(speaker_diarization=next(self.predictions))


class SpeakerDiarizationTests(unittest.TestCase):
    def test_fusion_maps_labels_and_preserves_overlapping_voices(self):
        tracks = [
            annotation((0, 3, "A"), (2, 5, "B")),
            annotation((0, 3, "Z"), (2, 5, "Y")),
            annotation((0, 3, "Y"), (2, 5, "Z")),
        ]
        fused = combine(tracks, duration=5)
        self.assertEqual(len(fused.labels()), 2)
        overlap = fused.crop(Segment(2.2, 2.8))
        self.assertEqual(len(overlap.labels()), 2)

    def test_fixed_count_is_passed_to_each_run_and_used_for_fallback(self):
        base = annotation((0, 1, "A"))
        alternative = annotation((0, 0.5, "A"), (0.5, 1, "B"))
        invalid = annotation((0, 0.3, "A"), (0.3, 0.6, "B"), (0.6, 1, "C"))
        pipeline = PipelineFixture([base, alternative, invalid])
        with patch("speaker_diarization.combine", return_value=invalid):
            result = run_multiple(
                pipeline, np.zeros(16000, dtype=np.float32), 2, lambda *_: None
            )

        self.assertEqual([call[1] for call in pipeline.calls], [2, 2, 2])
        self.assertIs(pipeline.calls[0][0], pipeline.calls[1][0])
        self.assertIsNot(pipeline.calls[0][0], pipeline.calls[2][0])
        self.assertNotEqual(pipeline.calls[0][2], pipeline.calls[1][2])
        self.assertNotEqual(pipeline.calls[0][3], pipeline.calls[2][3])
        self.assertEqual(pipeline._segmentation.step, 1.0)
        self.assertFalse(pipeline.training)
        self.assertIs(result.selected, alternative)
        self.assertEqual(result.details()["method"], "single-fallback")
        self.assertIn("3 statt 2", result.fallback)
