import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from qwen_backend import MAX_TOKENS, SAMPLE_RATE, recognize_words


def split_at_boundary(samples, rate, *, chunk_duration, **_):
    size = round(chunk_duration * rate)
    return [
        (samples[start : start + size], start / rate)
        for start in range(0, len(samples), size)
    ]


class QwenTextLimitTests(unittest.TestCase):
    def test_only_saturated_ranges_split_and_keep_the_original_timeline(self):
        audio = range(100 * SAMPLE_RATE)
        calls = []

        def generate(samples, *, language, max_tokens):
            calls.append((samples.start, samples.stop, max_tokens))
            # Only the final top-level chunk and its first half hit their limits.
            if len(samples) in (20 * SAMPLE_RATE, 10 * SAMPLE_RATE) and (
                samples.start == 80 * SAMPLE_RATE
            ):
                return SimpleNamespace(
                    text="Discard this", generation_tokens=max_tokens
                )
            return SimpleNamespace(
                text=f"Part {samples.start // SAMPLE_RATE}",
                segments=[{"language": None}],
                generation_tokens=5,
            )

        asr = Mock(generate=generate)
        progress = Mock()
        words = recognize_words(asr, None, audio, "auto", split_at_boundary, progress)
        self.assertEqual(
            [(word["word"], word["start"], word["end"]) for word in words],
            [
                (" Part 0", 0, 80),
                (" Part 80", 80, 85),
                (" Part 85", 85, 90),
                (" Part 90", 90, 100),
            ],
        )
        self.assertEqual(
            [(start // SAMPLE_RATE, end // SAMPLE_RATE) for start, end, _ in calls],
            [(0, 80), (80, 100), (80, 90), (80, 85), (85, 90), (90, 100)],
        )
        self.assertEqual([limit for _, _, limit in calls[:2]], [MAX_TOKENS] * 2)
        self.assertTrue(all(limit < MAX_TOKENS for _, _, limit in calls[2:]))
        fractions = [call.args[1] for call in progress.call_args_list]
        self.assertEqual(fractions, sorted(fractions))
        self.assertEqual(fractions[-1], 1.0)

    def test_minimum_chunk_retries_with_repetition_penalty(self):
        asr = Mock()
        asr.generate.side_effect = [
            SimpleNamespace(text="Discard this", generation_tokens=MAX_TOKENS),
            SimpleNamespace(
                text="Recovered", generation_tokens=1, segments=[{"language": None}]
            ),
        ]
        words = recognize_words(
            asr, None, range(3 * SAMPLE_RATE), "auto", split_at_boundary, Mock()
        )
        self.assertEqual(words, [{"word": " Recovered", "start": 0.0, "end": 3.0}])
        self.assertEqual(asr.generate.call_count, 2)
        self.assertIn("repetition_penalty", asr.generate.call_args.kwargs)
        self.assertLess(asr.generate.call_args.kwargs["max_tokens"], MAX_TOKENS)

    def test_persistent_saturation_reports_an_error_instead_of_partial_text(self):
        def generate(samples, *, language, max_tokens, **_):
            return SimpleNamespace(text="Discard this", generation_tokens=max_tokens)

        asr = Mock(generate=Mock(side_effect=generate))
        with self.assertRaisesRegex(RuntimeError, "auch nach mehreren Versuchen"):
            recognize_words(
                asr, None, range(2 * SAMPLE_RATE), "de", split_at_boundary, Mock()
            )
        self.assertEqual(asr.generate.call_count, 2)
        self.assertIn("repetition_penalty", asr.generate.call_args.kwargs)
