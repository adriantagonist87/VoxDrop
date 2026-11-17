"""Build the per-user launchd registration for the next macOS login."""

import os
import plistlib
import sys
import tempfile
from pathlib import Path

LABEL = "local.voxdrop.worker"
BUNDLE_IDENTIFIER = "local.voxdrop"


def agent_path():
    return Path.home() / "Library" / "LaunchAgents" / (LABEL + ".plist")


def definition(worker, config, state, model_data, *, python=None):
    log = str(state / "service.log")
    arguments = [
        str(python) if python is not None else sys.executable,
        "-BEs", str(worker), "--state-dir", str(state),
        "--model-data", str(model_data), "run", str(config),
    ]
    if len(worker.parents) > 3:
        app = worker.parents[3]
        launcher = app / "Contents/MacOS/VoxDrop"
        if app.suffix == ".app" and launcher.is_file():
            arguments = [str(launcher), "--background"]
    return {
        "Label": LABEL,
        "AssociatedBundleIdentifiers": [BUNDLE_IDENTIFIER],
        "ProgramArguments": arguments,
        "RunAtLoad": True,
        "StandardOutPath": log,
        "StandardErrorPath": log,
        "ExitTimeOut": 60,
    }


def update(enabled, settings):
    path = agent_path()
    try:
        if path.is_symlink():
            raise ValueError("Die Login-Konfiguration ist ein unerwarteter Symlink.")
        with path.open("rb") as handle:
            existing = plistlib.load(handle)
    except FileNotFoundError:
        existing = None
    legacy_settings = {
        key: value
        for key, value in settings.items()
        if key != "AssociatedBundleIdentifiers"
    }
    if existing is not None and existing not in (settings, legacy_settings):
        raise ValueError(
            "Unter dem Login-Dienstnamen existiert eine andere Konfiguration."
        )
    if enabled and existing is None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".voxdrop-") as handle:
            plistlib.dump(settings, handle)
            handle.flush()
            os.fsync(handle.fileno())
            os.link(handle.name, path)
    elif not enabled and existing is not None:
        path.unlink()
