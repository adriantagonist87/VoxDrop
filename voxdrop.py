"""Lokaler Einzellauf mit Qwen oder Whisper und aTrain-Sprecherzuordnung."""

import argparse
import gc
import os
import sys
import tempfile
import time
from pathlib import Path

import qwen_backend
from gpu_budget import pace_torch, pace_whisper
from model_inventory import model_use
from platform_io import WINDOWS, inference_cpu_threads
from silence import restore_timestamps, select_speech

WHISPER_MODEL = "large-v3-turbo"
DEFAULT_MODEL = qwen_backend.ASR
MODELS = (DEFAULT_MODEL, WHISPER_MODEL)
SPEAKER_MODEL = "speaker-detection"
MEDIA_EXTENSIONS = frozenset(
    [
        ".mp3",
        ".flv",
        ".mp4",
        ".mkv",
        ".ogg",
        ".opus",
        ".m4a",
        ".wav",
        ".flac",
        ".webm",
        ".avi",
        ".wma",
        ".aac",
        ".aiff",
        ".aif",
        ".mov",
    ]
)
DEFAULT_DATA = Path(__file__).resolve().parent / ".runtime" / "data"
HARDWARE = ("cuda", "cpu") if WINDOWS else ("metal", "cpu")
DEFAULT_HARDWARE = HARDWARE[0]


def configure_runtime(data_dir, *, setup=False):
    data_dir = data_dir.resolve()
    runtime = DEFAULT_DATA.parent
    python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    metal_packages = runtime / "metal-venv" / "lib" / python_version / "site-packages"
    if metal_packages.is_dir() and str(metal_packages) not in sys.path:
        sys.path.insert(0, str(metal_packages))
    os.environ.update(
        ATRAIN_USER_DIR=str(data_dir),
        HF_HOME=str(data_dir / "huggingface"),
        HF_HUB_OFFLINE="0" if setup else "1",
        HF_HUB_DISABLE_TELEMETRY="1",
        HF_HUB_DISABLE_IMPLICIT_TOKEN="1",
        PYANNOTE_METRICS_ENABLED="false",
        PYTORCH_ENABLE_MPS_FALLBACK="0",
        MPLCONFIGDIR=str(data_dir / "matplotlib"),
    )


def model_names(speakers, model):
    names = (WHISPER_MODEL,) if model == WHISPER_MODEL else ()
    return (*names, SPEAKER_MODEL) if speakers else names


def configured_models(speakers, model):
    from aTrain_core.globals import MODELS_DIR
    from aTrain_core.load_resources import load_model_config_file

    catalog = load_model_config_file()
    for name in model_names(speakers, model):
        yield name, MODELS_DIR / name, catalog[name]


def setup_models(data_dir, model=None, qwen_cache=None, *, speakers=True, report=None):
    from aTrain_core.integrity import verify_model
    from aTrain_core.load_resources import get_model

    with model_use(data_dir):
        for name, directory, entry in configured_models(speakers, model or WHISPER_MODEL):
            if report:
                report.model(name)
            print(f"Modell bereitstellen und verifizieren: {name}", file=sys.stderr)
            if get_model(name) != directory:
                raise ValueError(f"Unerwarteter Modellpfad für {name}.")
            if report:
                report.verifying(name)
            problems = verify_model(directory, entry["files"])
            if problems:
                raise ValueError(f"Prüfsummenfehler bei {name}: " + ", ".join(problems))
            if report:
                report.verified(name)

        if model in (None, DEFAULT_MODEL):
            if report:
                qwen_backend.provision_models(data_dir, cache=qwen_cache, report=report)
            else:
                qwen_backend.provision_models(data_dir, cache=qwen_cache)


def require_models(speakers, model):
    from aTrain_core.integrity import find_missing_files

    paths = {}
    for name, directory, entry in configured_models(speakers, model):
        if find_missing_files(directory, entry["files"]):
            raise ValueError(
                f"Modell {name} fehlt. Zuerst den Befehl setup-models ausführen."
            )
        paths[name] = directory
    return paths


def local_media(path):
    if path.suffix.lower() not in MEDIA_EXTENSIONS:
        raise ValueError(
            f"Nicht unterstütztes Medienformat: {path.suffix or path.name}"
        )
    if not path.is_file():
        raise ValueError(f"Mediendatei nicht gefunden: {path}")
    return path.absolute()


def decode_media(path):
    from aTrain_core.engine import decode
    from aTrain_core.globals import SAMPLING_RATE

    try:
        audio, _ = decode(path, log=lambda _: None)
    except Exception as error:
        raise ValueError(
            f"Tonspur kann nicht dekodiert werden: {error.__cause__ or error}"
        ) from error
    if not audio.size:
        raise ValueError("Die Tonspur enthält keine Audiodaten.")
    return audio, len(audio) / SAMPLING_RATE


def timestamp(seconds):
    hours, remainder = divmod(int(seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"[{hours:02d}:{minutes:02d}:{seconds:02d}]"


def format_transcript(cues, *, speakers):
    labels = {}
    paragraphs = []
    for cue in cues:
        words = cue["text"].strip()
        if not words:
            continue
        label = ""
        if speakers:
            speaker = cue.get("speaker")
            if speaker is None:
                label = " Sprecher unbekannt:"
            else:
                number = labels.setdefault(speaker, len(labels) + 1)
                label = f" Sprecher {number}:"
        paragraphs.append(f"{timestamp(cue['start'])}{label} {words}")
    if not paragraphs:
        raise ValueError("Keine Sprache erkannt.")
    return "\n\n".join(paragraphs) + "\n"


def publish_text(target, transcript):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=target.parent,
            prefix=".transcript-",
            suffix=".partial",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(transcript)
            handle.flush()
            os.fsync(handle.fileno())
        if WINDOWS:
            temporary.rename(target)
        else:
            os.link(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class Progress(dict):
    def __init__(self, phase, report):
        super().__init__()
        self.phase = phase
        self.report = report
        self.last_report = float("-inf")
        report(phase, None)

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        now = time.monotonic()
        current, total = self.get("current"), self.get("total")
        if (
            key in {"current", "total"}
            and current is not None
            and total
            and now - self.last_report >= 1
        ):
            self.report(self.phase, min(1.0, current / total))
            self.last_report = now


def console_progress(phase, fraction):
    detail = " …" if fraction is None else f": {fraction:.0%}"
    print(f"{phase}{detail}", file=sys.stderr, flush=True)


def load_whisper(path, hardware):
    from aTrain_core import engine
    from aTrain_core.settings import ComputeType, Device, ModelKey

    if hardware == "cpu":
        return engine.load_transcriber(
            ModelKey(WHISPER_MODEL, Device.CPU, ComputeType.INT8, inference_cpu_threads() if WINDOWS else 0), path
        )
    if hardware == "cuda":
        import torch

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA ist nicht verfügbar. Prüfe den NVIDIA-Treiber.")
        dll_directory = str(Path(torch.__file__).parent / "lib")
        os.environ["PATH"] = dll_directory + os.pathsep + os.environ.get("PATH", "")
        return pace_whisper(engine.load_transcriber(
            ModelKey(WHISPER_MODEL, Device.GPU, ComputeType.FLOAT16, 0), path
        ))

    from ctranslate2 import get_supported_compute_types
    from faster_whisper import WhisperModel

    try:
        compute_types = get_supported_compute_types("mps")
    except (ValueError, RuntimeError) as error:
        raise RuntimeError(
            "Apple Metal für Whisper fehlt. Das Projekt-Setup richtet CTranslate2 4.9 ein."
        ) from error
    if "float16" not in compute_types:
        raise RuntimeError(
            "Die Apple-GPU meldet keine Metal-Unterstützung für Whisper in FP16."
        )

    class MetalWhisper(engine.FasterWhisperTranscriber):
        def __init__(self, model_path):
            self._model_type = engine.load_model_config_file()[WHISPER_MODEL]["type"]
            self._model = WhisperModel(
                model_path.as_posix(), device="mps", compute_type="float16"
            )

    return pace_whisper(MetalWhisper(path), hardware='metal')


def transcribe(
    media,
    *,
    language,
    speakers,
    speaker_count,
    hardware=DEFAULT_HARDWARE,
    model=DEFAULT_MODEL,
    report=console_progress,
    measurements=None,
    skip_silence=False,
    dover_lap=False,
):
    if model not in MODELS:
        raise ValueError(f"Unbekanntes Transkriptionsmodell: {model}")
    paths = require_models(speakers, model)
    report("Audio dekodieren", None)
    audio, duration = decode_media(media)
    if measurements is not None:
        measurements["audio_seconds"] = duration
    accelerator = {"metal": "Apple GPU", "cuda": "NVIDIA CUDA", "cpu": "CPU"}[hardware]
    whisper = None
    speech_started = time.monotonic()
    speech, mapping = audio, None
    if skip_silence:
        report("Lange Stille erkennen", None)
        speech, mapping = select_speech(audio)
    try:
        if model == DEFAULT_MODEL:
            result = qwen_backend.transcribe(
                speech,
                data_dir=Path(os.environ.get("ATRAIN_USER_DIR", DEFAULT_DATA)),
                hardware=hardware,
                language=language,
                report=report,
            )
            backend = (
                "faster-whisper"  # Both backends preserve whitespace in timed words.
            )
        else:
            report(
                f"Whisper {WHISPER_MODEL} laden ({duration:.1f} s Audio, {accelerator})",
                None,
            )
            whisper = load_whisper(paths[WHISPER_MODEL], hardware)
            result = whisper.transcribe(
                speech,
                language=language,
                initial_prompt=None,
                temperature=None,
                progress=Progress("Transkribieren (Whisper)", report),
                log=lambda _: None,
            )
            backend = whisper.backend
        if mapping is not None:
            restore_timestamps(result, mapping, len(speech) / mapping.sampling_rate)
        if measurements is not None:
            measurements["speech_seconds"] = time.monotonic() - speech_started
        if not result["segments"]:
            raise ValueError("Das gewählte Modell hat keine Sprache erkannt.")
    finally:
        if whisper is not None:
            whisper.close()
            whisper = None
            gc.collect()

    # The ASR weights must be gone before loading the speaker pipeline.
    # Qwen already exits its isolated model process before returning above.
    return assign_speakers(
        audio,
        result,
        backend,
        hardware,
        speakers,
        speaker_count,
        report,
        measurements,
        dover_lap=dover_lap,
    )


def assign_speakers(
    audio,
    result,
    backend,
    hardware,
    speakers,
    speaker_count,
    report,
    measurements=None,
    *,
    dover_lap=False,
):
    from aTrain_core import engine
    from aTrain_core.outputs import finalize
    from aTrain_core.settings import Device

    if speakers:
        speaker_started = time.monotonic()
        accelerator = {"metal": "Apple GPU", "cuda": "NVIDIA CUDA", "cpu": "CPU"}[
            hardware
        ]
        report(f"Sprechermodell laden ({accelerator})", None)
        if hardware == "cuda":
            import torch

            if not torch.cuda.is_available():
                raise RuntimeError(
                    "CUDA steht für die Sprechererkennung nicht zur Verfügung."
                )
        diarizer = engine.load_diarizer(
            Device.GPU if hardware == "cuda" else Device.CPU, log=lambda _: None
        )
        if hardware == "metal":
            import torch

            if not torch.backends.mps.is_available():
                raise RuntimeError(
                    "Die Apple-GPU steht für die Sprechererkennung nicht zur Verfügung."
                )
            diarizer.to(torch.device("mps"))
        models = (diarizer._segmentation.model, diarizer._embedding.model_) if hardware in ('cuda','metal') else ()
        with pace_torch(*models, hardware=hardware):
            if dover_lap:
                from speaker_diarization import apply_annotation, run_multiple

                passes = run_multiple(diarizer, audio, speaker_count, report)
                result = apply_annotation(passes.selected, result)
                if measurements is not None:
                    measurements["speaker_details"] = passes.details()
            else:
                result = engine.diarize(
                    diarizer,
                    audio,
                    result,
                    speaker_count=speaker_count,
                    progress=Progress("Sprecher zuordnen", report),
                    log=lambda _: None,
                )
        if measurements is not None:
            measurements["speaker_seconds"] = time.monotonic() - speaker_started
    return format_transcript(finalize(result, backend)["segments"], speakers=speakers)


def parser():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    subparsers = cli.add_subparsers(dest="command", required=True)
    setup = subparsers.add_parser(
        "setup-models", help="Gepinnte Modelle herunterladen und prüfen."
    )
    setup.add_argument("--model", choices=MODELS)
    setup.add_argument(
        "--qwen-cache", type=Path, help="Qwen aus einem vorhandenen HF-Cache laden."
    )
    probe = subparsers.add_parser(
        "probe", help="Audiospur lokal dekodieren und Dauer ermitteln."
    )
    probe.add_argument("media", type=Path)
    job = subparsers.add_parser("transcribe", help="Eine lokale Datei transkribieren.")
    job.add_argument("media", type=Path)
    job.add_argument("--output-dir", required=True, type=Path)
    job.add_argument("--language", choices=("auto", "de", "en"), default="auto")
    job.add_argument("--hardware", choices=HARDWARE, default=DEFAULT_HARDWARE)
    job.add_argument("--model", choices=MODELS, default=DEFAULT_MODEL)
    job.add_argument(
        "--skip-silence",
        action="store_true",
        help="Lange Stille bei der Spracherkennung überspringen.",
    )
    job.add_argument(
        "--dover-lap",
        action="store_true",
        help="Drei Varianten der Sprecherzuordnung zusammenführen.",
    )
    speakers = job.add_mutually_exclusive_group()
    speakers.add_argument(
        "--speaker-count", type=int, choices=range(1, 9), metavar="1–8"
    )
    speakers.add_argument("--no-speakers", action="store_true")
    return cli


def main(argv=None):
    args = parser().parse_args(argv)
    configure_runtime(args.data_dir, setup=args.command == "setup-models")
    started = time.monotonic()
    try:
        if args.command == "setup-models":
            setup_models(args.data_dir.resolve(), args.model, args.qwen_cache)
            return 0
        media = local_media(args.media)
        if args.command == "probe":
            _, duration = decode_media(media)
            print(f"Audiospur dekodiert. Dauer {duration:.3f} s.")
            return 0

        if not args.output_dir.is_dir():
            raise ValueError(f"Ausgabeordner fehlt: {args.output_dir}")
        target = args.output_dir / media.with_suffix(".txt").name
        if os.path.lexists(target):
            raise FileExistsError(f"Die Zieldatei existiert bereits: {target}")
        with model_use(args.data_dir):
            result = transcribe(
                media,
                language="auto-detect" if args.language == "auto" else args.language,
                speakers=not args.no_speakers,
                speaker_count=args.speaker_count,
                hardware=args.hardware,
                model=args.model,
                skip_silence=args.skip_silence,
                dover_lap=args.dover_lap,
            )
        print("Ergebnis schreiben …", file=sys.stderr, flush=True)
        publish_text(target, result)
        print(
            f"Laufzeit {timestamp(time.monotonic() - started)[1:-1]}", file=sys.stderr
        )
        print(target.absolute())
        return 0
    except Exception as error:  # noqa: BLE001 - command boundary for third-party failures
        print(f"Fehler ({type(error).__name__}): {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
