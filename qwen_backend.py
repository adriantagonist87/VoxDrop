"""Offline Qwen ASR and word alignment, isolated from aTrain's Python packages."""

import argparse
import gc
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from platform_io import WINDOWS, child_process, process_options

ASR = "qwen3-asr-1.7b"
ALIGNER = "qwen3-forced-aligner-0.6b"
SAMPLE_RATE = 16000
MAX_TOKENS = 4096
MIN_RETRY_SAMPLES = 2 * SAMPLE_RATE
LANGUAGES = {"de": "German", "en": "English"}
ALIGNER_LANGUAGES = {
    "english",
    "french",
    "german",
    "italian",
    "portuguese",
    "russian",
    "spanish",
}
HERE = Path(__file__).resolve().parent
EVENT = "smb-qwen:"


def model_manifest():
    filename = "qwen-windows-models.json" if WINDOWS else "qwen-models.json"
    return json.loads((HERE / filename).read_text(encoding="utf-8"))


def require_models(data_dir):
    model_root = data_dir / "models"
    for key, entry in model_manifest().items():
        if not all(
            (model_root / key / filename).is_file() for filename in entry["files"]
        ):
            raise ValueError(f"Modell {key} fehlt. Zuerst setup-models ausführen.")
    return model_root


def provision_models(data_dir, source=None, cache=None):
    if source is None:
        from huggingface_hub import snapshot_download

    model_root = data_dir / "models"
    model_root.mkdir(parents=True, exist_ok=True)
    for key, entry in model_manifest().items():
        destination = model_root / key
        if destination.is_dir() and valid_model(destination, entry):
            continue
        if source is None:
            directory = Path(
                snapshot_download(
                    entry["repo"],
                    revision=entry["revision"],
                    cache_dir=cache,
                    allow_patterns=list(entry["files"]),
                    local_files_only=cache is not None,
                    token=False,
                )
            )
        else:
            directory = source / "models" / key
        with tempfile.TemporaryDirectory(
            prefix=f".{key}-", dir=model_root
        ) as temporary:
            staged = Path(temporary) / "model"
            staged.mkdir()
            for name in entry["files"]:
                shutil.copyfile(directory / name, staged / name)
            if not valid_model(staged, entry):
                raise ValueError(f"Prüfsummenfehler bei {key}.")
            previous = Path(temporary) / "previous"
            if destination.exists():
                destination.rename(previous)
            try:
                staged.rename(destination)
            except OSError:
                if previous.exists():
                    previous.rename(destination)
                raise


def valid_model(directory, entry):
    for name, expected in entry["files"].items():
        try:
            with (directory / name).open("rb") as handle:
                if hashlib.file_digest(handle, "sha256").hexdigest() != expected:
                    return False
        except FileNotFoundError:
            return False
    return True


def package_directory():
    packaged = HERE.parent / "QwenPackages"
    if packaged.is_dir():
        return packaged
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    return HERE / ".runtime" / "qwen-venv" / "lib" / version / "site-packages"


def transcribe(audio, *, data_dir, hardware, language, report):
    import numpy as np
    from aTrain_core.backends.common import words_to_segments

    model_root = require_models(data_dir)
    packages = package_directory()
    if not WINDOWS and not (packages / "mlx_audio").is_dir():
        raise RuntimeError(
            "Die Qwen-Laufzeit fehlt. Zuerst scripts/bootstrap.sh ausführen."
        )

    with tempfile.TemporaryDirectory(prefix="smb-qwen-") as temporary:
        work = Path(temporary)
        recording = work / "audio.npy"
        result = work / "result.json"
        np.save(recording, audio, allow_pickle=False)
        command = [
            sys.executable,
            "-BEs" if WINDOWS else "-BESs",
            "-Xutf8",
            str(Path(__file__).resolve()),
            str(packages),
            str(model_root),
            str(recording),
            str(result),
            hardware,
            language,
        ]
        env = {**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}
        detail = None
        with child_process(
            command,
            stdout=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=env,
            **process_options(),
        ) as child:
            try:
                for line in child.stdout:
                    if not line.startswith(EVENT):
                        continue
                    event = json.loads(line[len(EVENT) :])
                    if "error" in event:
                        detail = event["error"]
                    else:
                        report(event["phase"], event["fraction"])
            finally:
                if sys.exc_info()[0] and child.poll() is None:
                    child.terminate()
            if child.wait():
                raise RuntimeError(
                    detail or "Qwen wurde vor Abschluss beendet. Siehe Dienstprotokoll."
                )
        words = json.loads(result.read_text(encoding="utf-8"))
    return {"segments": words_to_segments(words)}


def emit(**event):
    print(EVENT + json.dumps(event, ensure_ascii=True), flush=True)


def align_words(aligner, audio, text, language, offset, duration, chunk_duration):
    """Restore punctuation from the ASR transcript while using measured word times."""
    items = aligner.generate(audio, text=text, language=language).items
    tokenizer = aligner.aligner_processor
    words = []
    prefix = []
    index = 0
    for surface in text.split():
        tokens = tokenizer.tokenize_space_lang(surface)
        if not tokens:
            if words:
                words[-1]["word"] += " " + surface
            else:
                prefix.append(surface)
            continue
        aligned = items[index : index + len(tokens)]
        if [item.text for item in aligned] != tokens:
            return []
        index += len(tokens)
        start = min(chunk_duration, max(0.0, aligned[0].start_time)) + offset
        end = min(chunk_duration, max(0.0, aligned[-1].end_time)) + offset
        if end <= start:
            end = min(offset + chunk_duration, start + 0.025)
        words.append(
            {
                "word": " " + " ".join([*prefix, surface]),
                "start": min(start, duration),
                "end": min(end, duration),
            }
        )
        prefix.clear()
    return words if index == len(items) else []


def recognize_words(asr, aligner, audio, language, split_audio, report):
    words = []

    def consume(samples, text, detected, start, end):
        words.extend(
            timed_words(aligner, samples, text, detected, start, end, len(audio))
        )

    recognize_chunks(asr, audio, language, split_audio, report, consume)
    return words


def timed_words(aligner, samples, text, language, start, end, total):
    aligned = []
    if aligner is not None and language and language.lower() in ALIGNER_LANGUAGES:
        aligned = align_words(
            aligner,
            samples,
            text,
            language,
            start / SAMPLE_RATE,
            total / SAMPLE_RATE,
            (end - start) / SAMPLE_RATE,
        )
    return aligned or [
        {"word": " " + text, "start": start / SAMPLE_RATE, "end": end / SAMPLE_RATE}
    ]


def recognize_chunks(asr, audio, language, split_audio, report, consume):
    duration = len(audio) / SAMPLE_RATE
    if not duration:
        return

    chunks = split_audio(audio, SAMPLE_RATE, chunk_duration=80.0)
    offsets = [round(offset * SAMPLE_RATE) for _, offset in chunks] + [len(audio)]
    requested_language = LANGUAGES.get(language)
    progress_label = "Transkribieren (Qwen)"

    def recognize(samples, start, end, retrying=False):
        offset = start / SAMPLE_RATE
        chunk_duration = (end - start) / SAMPLE_RATE
        # Bound the time spent on repeated output from short retries.
        retry_limit = min(MAX_TOKENS, max(128, int(48 * chunk_duration)))
        limit = retry_limit if retrying else MAX_TOKENS
        try:
            output = asr.generate(
                samples, language=requested_language, max_tokens=limit
            )
        except MemoryError:
            if end - start < 2 * MIN_RETRY_SAMPLES:
                raise
            output = None
        if output is None or output.generation_tokens >= limit:
            report(
                "Qwen versucht einen schwierigen Abschnitt erneut", start / len(audio)
            )
            if end - start >= 2 * MIN_RETRY_SAMPLES:
                midpoint = chunk_duration / 2
                search = min(2.0, midpoint - MIN_RETRY_SAMPLES / SAMPLE_RATE)
                parts = split_audio(
                    samples,
                    SAMPLE_RATE,
                    chunk_duration=midpoint,
                    search_expand_sec=search,
                )
                cut = start + round(parts[1][1] * SAMPLE_RATE)
                cut = min(end - MIN_RETRY_SAMPLES, max(start + MIN_RETRY_SAMPLES, cut))
                recognize(audio[start:cut], start, cut, retrying=True)
                recognize(audio[cut:end], cut, end, retrying=True)
                return
            output = asr.generate(
                samples,
                language=requested_language,
                max_tokens=retry_limit,
                repetition_penalty=1.15,
            )
            if output.generation_tokens >= retry_limit:
                raise RuntimeError(
                    f"Qwen konnte einen kurzen Abschnitt bei {offset:.1f} Sekunden "
                    "im verarbeiteten Audio auch nach mehreren Versuchen nicht vollständig erkennen."
                )

        text = output.text.strip()
        if text:
            detected = requested_language or output.segments[0].get("language")
            consume(samples, text, detected, start, end)
        report(progress_label, end / len(audio))

    report(progress_label, 0.0)
    for (samples, _), start, end in zip(chunks, offsets[:-1], offsets[1:], strict=True):
        recognize(samples, start, end)


def run(packages, model_root, recording, result, hardware, language):
    if WINDOWS:
        from qwen_cuda import run_windows

        return run_windows(model_root, recording, result, hardware, language)
    sys.path.insert(0, str(packages))

    import mlx.core as mx
    import numpy as np
    from mlx_audio.stt import load
    from mlx_audio.stt.models.qwen3_asr.qwen3_asr import split_audio_into_chunks

    device = mx.gpu if hardware == "metal" else mx.cpu
    if hardware == "metal" and not mx.metal.is_available():
        raise RuntimeError("Die Apple-GPU steht für Qwen nicht zur Verfügung.")
    mx.set_default_device(device)
    accelerator = "Apple-GPU" if hardware == "metal" else "CPU"
    emit(phase=f"Qwen-Modell laden ({accelerator})", fraction=None)
    asr = load(model_root / ASR)
    if hardware == 'cpu':
        # The pinned MLX BF16 quantized CPU kernel is scalar and extremely slow.
        # Keep packed integer weights; use native FP32 floating-point CPU math.
        asr.set_dtype(mx.float32)
    audio = np.load(recording, mmap_mode="r", allow_pickle=False)
    from gpu_budget import pace_mlx
    report = lambda phase, fraction: emit(phase=phase, fraction=fraction)
    chunks = []
    with pace_mlx(asr, hardware=hardware):
        recognize_chunks(asr, audio, language, split_audio_into_chunks, report,
                         lambda *chunk: chunks.append(chunk))
    del asr
    gc.collect()
    mx.synchronize()
    mx.clear_cache()
    words = []
    if chunks:
        report("Qwen-Wortzeiten berechnen", 0.0)
        aligner = load(model_root / ALIGNER)
        if hardware == 'cpu':
            aligner.set_dtype(mx.float32)
        with pace_mlx(aligner, hardware=hardware):
            for index, chunk in enumerate(chunks, start=1):
                words.extend(timed_words(aligner, *chunk, len(audio)))
                report("Qwen-Wortzeiten berechnen", index / len(chunks))
    result.write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("packages", "model_root", "recording", "result"):
        parser.add_argument(name, type=Path)
    parser.add_argument(
        "hardware", choices=("cuda", "cpu") if WINDOWS else ("metal", "cpu")
    )
    parser.add_argument("language")
    try:
        run(**vars(parser.parse_args()))
    except Exception as error:  # noqa: BLE001 - isolated process boundary
        emit(error=str(error) or type(error).__name__)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
