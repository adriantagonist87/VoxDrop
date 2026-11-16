"""Combine three local pyannote diarization hypotheses before assigning words."""

import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyannote.core import Annotation

HERE = Path(__file__).resolve().parent


@dataclass
class MultiplePasses:
    baseline: "Annotation"
    selected: "Annotation"
    pass_seconds: list[float]
    pass_counts: list[int | None]
    fusion_seconds: float
    fallback: str | None

    def details(self):
        return {
            "method": "single-fallback" if self.fallback else "dover-lap",
            "passes": sum(count is not None for count in self.pass_counts),
            "note": self.fallback,
        }


def combine(annotations, duration):
    bundled = HERE.parent / "DoverPackages"
    packages = bundled if bundled.is_dir() else HERE / ".runtime" / "dover-packages"
    if str(packages) not in sys.path:
        sys.path.append(str(packages))

    from dover_lap.libs.turn import Turn
    from dover_lap.src.doverlap import DOVERLap
    from pyannote.core import Annotation, Segment

    turns = []
    for annotation in annotations:
        sample_turns = []
        for turn, _, speaker in annotation.itertracks(yield_label=True):
            start = max(0.0, turn.start)
            end = min(duration, turn.end)
            if start < end:
                sample_turns.append(
                    Turn(start, end, speaker_id=str(speaker), file_id="recording")
                )
        if not sample_turns:
            raise ValueError("Ein Durchgang hat keine Sprechersegmente erkannt.")
        turns.append(sample_turns)

    consensus = DOVERLap.combine_turns_list(
        turns, "recording", label_mapping="greedy", gaussian_filter_std=0.1
    )
    result = Annotation()
    for index, turn in enumerate(consensus):
        result[Segment(turn.onset, turn.offset), index] = str(turn.speaker_id)
    if not result.labels():
        raise ValueError("Die Fusion hat keine Sprechersegmente geliefert.")
    return result.support()


def apply_annotation(annotation, transcript):
    from aTrain_core.outputs import (
        assign_word_speakers,
        smooth_speaker_flips,
        transform_speakers_results,
    )

    if not annotation.labels():
        return transcript
    result = assign_word_speakers(transform_speakers_results(annotation), transcript)
    smooth_speaker_flips(result["segments"])
    return result


def run_multiple(pipeline, audio, speaker_count, report):
    import torch
    from aTrain_core.globals import SAMPLING_RATE

    waveform = {
        "waveform": torch.from_numpy(audio[None, :]),
        "sample_rate": SAMPLING_RATE,
    }
    original = pipeline.parameters(instantiated=True)
    clustering = original["clustering"]
    training = pipeline.training
    inference = pipeline._segmentation
    original_step = inference.step
    predictions = []
    pass_counts = []
    pass_seconds = []
    failure = None

    try:
        # pyannote's hyperparameter cache reuses the baseline features for
        # the clustering variant. The longer step needs its own features.
        pipeline.training = True
        cached_waveform = dict(waveform)
        for index in range(1, 4):
            phase = f"Sprecherprüfung {index}/3 (DOVER-Lap)"
            report(phase, 0.0)
            started = time.monotonic()
            last_progress = started

            def hook(
                step, artifact, file=None, total=None, completed=None, *, phase=phase
            ):
                nonlocal last_progress
                now = time.monotonic()
                if not total or completed is None or now - last_progress < 1:
                    return
                if step == "segmentation":
                    report(phase, 0.5 * completed / total)
                elif step == "embeddings":
                    report(phase, 0.5 + 0.5 * completed / total)
                else:
                    return
                last_progress = now

            try:
                if index == 2:
                    pipeline.instantiate(
                        {
                            **original,
                            "clustering": {**clustering, "threshold": 0.55, "Fb": 0.7},
                        }
                    )
                elif index == 3:
                    pipeline.instantiate(original)
                    inference.step = original_step * 1.5
                    cached_waveform = dict(waveform)

                annotation = pipeline(
                    cached_waveform, num_speakers=speaker_count, hook=hook
                ).speaker_diarization
                predictions.append(annotation)
                pass_counts.append(len(annotation.labels()))
            except Exception as error:
                if index == 1:
                    raise
                failure = f"Prüfdurchgang {index} fehlgeschlagen: {error}"
                pass_counts.append(None)
            pass_seconds.append(time.monotonic() - started)
            report(phase, 1.0)
    finally:
        pipeline.training = training
        inference.step = original_step
        pipeline.instantiate(original)

    baseline = predictions[0]
    selected = None
    fusion_seconds = 0.0
    if failure is None:
        report("Sprecherergebnisse zusammenführen (DOVER-Lap)", None)
        started = time.monotonic()
        try:
            selected = combine(predictions, len(audio) / SAMPLING_RATE)
        except Exception as error:  # noqa: BLE001 - retain the usable local speaker result
            failure = f"Fusion fehlgeschlagen: {error}"
        fusion_seconds = time.monotonic() - started

    if (
        selected is not None
        and speaker_count is not None
        and len(selected.labels()) != speaker_count
    ):
        failure = (
            f"Fusion ergab {len(selected.labels())} statt {speaker_count} Sprecher."
        )
        selected = None
    if selected is None:
        selected = next(
            (
                item
                for item in predictions
                if speaker_count is None or len(item.labels()) == speaker_count
            ),
            baseline,
        )
        if speaker_count is not None and len(selected.labels()) != speaker_count:
            failure = f"{failure} Kein Einzellauf erreichte die Vorgabe von {speaker_count} Sprechern."
        report("DOVER-Lap: Einzellauf für Sprecherzuordnung verwendet", None)

    return MultiplePasses(
        baseline, selected, pass_seconds, pass_counts, fusion_seconds, failure
    )
