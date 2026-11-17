"""Measure one transcription in its own process and forward its progress."""

import ctypes
import json
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from platform_io import WINDOWS, child_process, process_options
from voxdrop import DEFAULT_DATA, configure_runtime, transcribe

EVENT = "smb-transcription:"
SAMPLE_INTERVAL = 0.2


class ProcessUsage(ctypes.Structure):
    # macOS sys/resource.h, struct rusage_info_v0.
    _fields_ = [
        ("uuid", ctypes.c_uint8 * 16),
        ("counters", ctypes.c_uint64 * 7),
        ("physical_bytes", ctypes.c_uint64),
        ("process_times", ctypes.c_uint64 * 2),
    ]


def sample_peak(pid, stop, peaks):
    import psutil

    if not WINDOWS:
        try:
            usage_info = ctypes.CDLL("/usr/lib/libSystem.B.dylib").proc_pid_rusage
        except (OSError, AttributeError):
            return
        usage_info.argtypes = (ctypes.c_int, ctypes.c_int, ctypes.c_void_p)
        usage_info.restype = ctypes.c_int
    try:
        process = psutil.Process(pid)
    except psutil.Error:
        return
    usage = ProcessUsage()

    def footprint(child):
        if WINDOWS:
            try:
                return child.memory_info().rss
            except psutil.Error:
                return 0
        if usage_info(child.pid, 0, ctypes.byref(usage)) == 0:
            return usage.physical_bytes
        return 0

    while not stop.is_set():
        try:
            children = process.children(recursive=True)
        except (psutil.AccessDenied, PermissionError):
            children = []
        except psutil.Error:
            break
        total = footprint(process) + sum(footprint(child) for child in children)
        if total:
            peaks[0] = max(peaks[0], total)
        stop.wait(SAMPLE_INTERVAL)


def emit(**event):
    print(EVENT + json.dumps(event), flush=True)


def run_transcription(media, *, report, measurements, **settings):
    data_dir = os.environ.get("ATRAIN_USER_DIR", str(DEFAULT_DATA))
    with tempfile.TemporaryDirectory(
        dir=media.parent, prefix="transcription-"
    ) as directory:
        result = Path(directory) / "result.json"
        command = [
            sys.executable,
            "-BEs",
            "-Xutf8",
            str(Path(__file__).resolve()),
            data_dir,
            str(media),
            str(result),
            json.dumps(settings),
        ]
        error = None
        peak = [0]
        with child_process(
            command,
            stdout=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            **process_options(),
        ) as child:
            stop = threading.Event()
            sampler = threading.Thread(target=sample_peak, args=(child.pid, stop, peak))
            sampler.start()
            try:
                for line in child.stdout:
                    if line.startswith(EVENT):
                        event = json.loads(line[len(EVENT) :])
                        if "error" in event:
                            error = event["error"]
                        else:
                            report(event["phase"], event["fraction"])
                if child.wait():
                    raise RuntimeError(
                        error or "Transkriptionsprozess vor Abschluss beendet."
                    )
            finally:
                stop.set()
                sampler.join()
                if child.poll() is None:
                    child.terminate()
                    child.wait()
        output = json.loads(result.read_text(encoding="utf-8"))
        measurements.update(output["measurements"], peak_memory_bytes=peak[0] or None)
        return output["text"]


def main(data_dir, media, result, options):
    configure_runtime(Path(data_dir))
    measurements = {}
    try:
        text = transcribe(
            Path(media),
            **json.loads(options),
            report=lambda phase, fraction: emit(phase=phase, fraction=fraction),
            measurements=measurements,
        )
        Path(result).write_text(
            json.dumps(
                {"text": text, "measurements": measurements}, ensure_ascii=False
            ),
            encoding="utf-8",
        )
    except Exception as error:  # noqa: BLE001 - isolated process boundary
        emit(error=str(error))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
