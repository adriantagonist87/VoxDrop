"""Remove long non-speech intervals while retaining the recording's clock."""

MIN_SILENCE_MS = 3000
SPEECH_PAD_MS = 400
SPEECH_THRESHOLD = 0.35


def select_speech(audio):
    import numpy as np
    from aTrain_core.globals import SAMPLING_RATE
    from faster_whisper.vad import (
        SpeechTimestampsMap,
        VadOptions,
        get_speech_timestamps,
    )

    options = VadOptions(
        threshold=SPEECH_THRESHOLD,
        min_silence_duration_ms=MIN_SILENCE_MS,
        speech_pad_ms=SPEECH_PAD_MS,
    )
    ranges = get_speech_timestamps(audio, options, sampling_rate=SAMPLING_RATE)
    if not ranges:
        raise ValueError(
            "Die Stille-Erkennung hat keine Sprache in der Aufnahme gefunden."
        )

    # Retain short pauses at either edge as well as pauses within speech.
    min_edge_gap = (MIN_SILENCE_MS - SPEECH_PAD_MS) * SAMPLING_RATE / 1000
    if ranges[0]["start"] < min_edge_gap:
        ranges[0]["start"] = 0
    if len(audio) - ranges[-1]["end"] < min_edge_gap:
        ranges[-1]["end"] = len(audio)
    if ranges == [{"start": 0, "end": len(audio)}]:
        return audio, None

    retained = [audio[span["start"] : span["end"]] for span in ranges]
    if len(retained) == 1:
        speech = retained[0]
    else:
        speech = np.concatenate(retained)
    return speech, SpeechTimestampsMap(ranges, SAMPLING_RATE, time_precision=6)


def restore_timestamps(transcript, mapping, speech_duration):
    def restore(item):
        start = min(speech_duration, max(0, item["start"]))
        end = min(speech_duration, max(start, item["end"]))
        item["start"] = mapping.get_original_time(start)
        item["end"] = max(item["start"], mapping.get_original_time(end, is_end=True))

    for segment in transcript["segments"]:
        restore(segment)
        for word in segment["words"]:
            restore(word)
