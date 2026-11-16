"""Qwen3 ASR and forced alignment using the Transformers Windows runtime."""

import gc
import json
from types import SimpleNamespace

from qwen_backend import ALIGNER, ASR, emit, recognize_chunks, timed_words


def split_at_quiet_points(audio, sample_rate, *, chunk_duration, search_expand_sec=2):
    import numpy as np

    step = max(1, round(sample_rate * chunk_duration))
    radius = min(step // 4, round(sample_rate * search_expand_sec))
    window = max(1, sample_rate // 100)
    start = 0
    chunks = []
    while len(audio) - start > step + radius:
        nominal = start + step
        candidates = range(nominal - radius, nominal + radius + 1, window)
        end = min(
            candidates,
            key=lambda index: (
                float(np.mean(abs(audio[index : index + window]))),
                abs(index - nominal),
            ),
        )
        chunks.append((audio[start:end], start / sample_rate))
        start = end
    if start < len(audio):
        chunks.append((audio[start:], start / sample_rate))
    return chunks


class QwenRecognizer:
    def __init__(self, processor, model, torch):
        self.processor = processor
        self.model = model
        self.torch = torch

    def generate(self, audio, language, max_tokens, repetition_penalty=1.0):
        torch = self.torch
        try:
            with torch.inference_mode():
                inputs = self.processor.apply_transcription_request(
                    audio, language=language, return_tensors="pt"
                ).to(device=self.model.device, dtype=self.model.dtype)
                output = self.model.generate(
                    **inputs,
                    max_new_tokens=max_tokens,
                    do_sample=False,
                    repetition_penalty=repetition_penalty,
                )
                tokens = getattr(output, "sequences", output)[
                    0, inputs.input_ids.shape[1] :
                ]
                decoded = self.processor.decode(tokens, return_format="parsed")
                return SimpleNamespace(
                    text=decoded["transcription"],
                    generation_tokens=len(tokens),
                    segments=[{"language": decoded["language"]}],
                )
        except torch.OutOfMemoryError:
            pass
        torch.cuda.empty_cache()
        raise MemoryError("Zu wenig GPU-Speicher für diesen Qwen-Abschnitt.")


class QwenAligner:
    def __init__(self, processor, model, torch):
        self.processor = processor
        self.model = model
        self.torch = torch
        self.aligner_processor = self
        self.language = None

    def tokenize_space_lang(self, text):
        return self.processor.split_words_for_alignment(text, self.language)

    def generate(self, audio, text, language):
        self.language = language
        torch = self.torch
        try:
            with torch.inference_mode():
                inputs, words = self.processor.prepare_forced_aligner_inputs(
                    audio, text, language, return_tensors="pt"
                )
                inputs = inputs.to(device=self.model.device, dtype=self.model.dtype)
                items = self.processor.decode_forced_alignment(
                    self.model(**inputs).logits,
                    inputs.input_ids,
                    words,
                    self.model.config.timestamp_token_id,
                    self.model.config.timestamp_segment_time,
                )[0]
                return SimpleNamespace(
                    items=[SimpleNamespace(**item) for item in items]
                )
        except torch.OutOfMemoryError:
            pass
        torch.cuda.empty_cache()
        return SimpleNamespace(items=[])


def run_windows(model_root, recording, result, hardware, language):
    import numpy as np
    import torch
    from transformers import (
        Qwen3ASRForConditionalGeneration,
        Qwen3ASRForTokenClassification,
        Qwen3ASRProcessor,
    )

    cuda = hardware == "cuda"
    if cuda and not torch.cuda.is_available():
        raise RuntimeError(
            "Die NVIDIA-GPU ist für Qwen nicht verfügbar. Prüfe den Treiber."
        )
    device = "cuda:0" if cuda else "cpu"
    dtype = torch.bfloat16 if cuda else torch.float32
    options = {"local_files_only": True, "dtype": dtype, "device_map": {"": device}}
    report = lambda phase, fraction: emit(phase=phase, fraction=fraction)
    audio = np.load(recording, mmap_mode="r", allow_pickle=False)
    chunks = []
    report(f"Qwen-Modell laden ({'NVIDIA CUDA' if cuda else 'CPU'})", None)
    recognizer = QwenRecognizer(
        Qwen3ASRProcessor.from_pretrained(model_root / ASR, local_files_only=True),
        Qwen3ASRForConditionalGeneration.from_pretrained(
            model_root / ASR, **options
        ).eval(),
        torch,
    )
    recognize_chunks(
        recognizer,
        audio,
        language,
        split_at_quiet_points,
        report,
        lambda samples, text, detected, start, end: chunks.append(
            (samples, text, detected, start, end)
        ),
    )
    # Fit 8 GB GPUs by loading the two model weights in sequence.
    del recognizer
    gc.collect()
    if cuda:
        torch.cuda.empty_cache()
    words = []
    if chunks:
        report("Qwen-Wortzeiten berechnen", 0.0)
        aligner = QwenAligner(
            Qwen3ASRProcessor.from_pretrained(
                model_root / ALIGNER, local_files_only=True
            ),
            Qwen3ASRForTokenClassification.from_pretrained(
                model_root / ALIGNER, **options
            ).eval(),
            torch,
        )
        for index, chunk in enumerate(chunks, start=1):
            words.extend(timed_words(aligner, *chunk, len(audio)))
            report("Qwen-Wortzeiten berechnen", index / len(chunks))
    result.write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
