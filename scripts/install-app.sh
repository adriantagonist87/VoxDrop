#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
runtime="$project_dir/.runtime"
app="$runtime/package/VoxDrop.app"
support="$HOME/Library/Application Support/SMB Transcriber"
if [ -e "$HOME/Applications/VoxDrop.app" ] || [ -L "$HOME/Applications/VoxDrop.app" ] \
    || [ -e "$HOME/Applications/SMB Transcriber.app" ] || [ -L "$HOME/Applications/SMB Transcriber.app" ]; then
    apps="$HOME/Applications"
elif [ -e /Applications/VoxDrop.app ] || [ -e "/Applications/SMB Transcriber.app" ] || [ -w /Applications ]; then
    apps=/Applications
else
    apps="$HOME/Applications"
fi
target="$apps/VoxDrop.app"
previous_name="$apps/SMB Transcriber.app"

/usr/bin/codesign --verify --strict "$app"
for existing in "$target" "$previous_name"; do
    if [ -e "$existing" ] || [ -L "$existing" ]; then
        if [ -L "$existing" ] || [ "$(plutil -extract CFBundleIdentifier raw -o - "$existing/Contents/Info.plist")" != local.smb-transcriber ]; then
            printf 'Am Installationsort liegt bereits eine andere App: %s\n' "$existing" >&2
            exit 1
        fi
    fi
done

"$app/Contents/Resources/Python/bin/python3.12" -BEs - "$runtime" "$support" "$app/Contents/Resources/Engine" <<'PY'
import fcntl
import shutil
import sys
import tempfile
from pathlib import Path

source, support, engine = (Path(value) for value in sys.argv[1:])
sys.path.insert(0, str(engine))
from qwen_backend import provision_models, require_models

require_models(source / 'data')
if support.is_symlink():
    raise SystemExit('Das Laufzeitverzeichnis ist ein unerwarteter Symlink.')
if not support.exists():
    support.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.SMBTranscriber-', dir=support.parent) as directory:
        staged = Path(directory) / 'data'
        staged.mkdir(mode=0o700)
        history = source / 'service'
        if history.is_dir():
            with (history / 'service.lock').open('a') as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as error:
                    raise SystemExit('Die alte App verarbeitet noch Aufträge. Bitte den Dienst zuerst beenden.') from error
                shutil.copytree(history, staged / 'service', ignore=shutil.ignore_patterns('service.lock'))
        model_dir = source / 'data' / 'models'
        shutil.copytree(model_dir, staged / 'data' / 'models')
        settings = source / 'config.json'
        if settings.is_file():
            shutil.copy2(settings, staged / 'config.json')
        staged.rename(support)
else:
    provision_models(support / 'data', source=source / 'data')
PY

mkdir -p "$apps"
stage=$(mktemp -d "$apps/.SMBTranscriber-install.XXXXXX")
trap 'rm -rf "$stage"' EXIT
/usr/bin/ditto "$app" "$stage/VoxDrop.app"
/usr/bin/codesign --verify --strict "$stage/VoxDrop.app"

relocate_login_agent() {
    "$target/Contents/Resources/Python/bin/python3.12" -BEs - "$previous_name" "$target" <<'PY'
import os
import plistlib
import sys
import tempfile
from pathlib import Path

old, new = (Path(value) for value in sys.argv[1:])
label = "local.smb-transcriber.worker"
path = Path.home() / "Library/LaunchAgents" / (label + ".plist")
if path.is_symlink():
    raise SystemExit("Die Login-Konfiguration ist ein unerwarteter Symlink.")
if not path.is_file():
    raise SystemExit(0)
agent = plistlib.loads(path.read_bytes())
arguments = agent.get("ProgramArguments", [])
resources = Path("Contents/Resources")
python = resources / "Python/bin/python3.12"
worker = resources / "Engine/watch_service.py"
if agent.get("Label") != label or arguments[:3] != [str(old / python), "-BEs", str(old / worker)]:
    raise SystemExit("Die vorhandene Login-Konfiguration verwendet einen anderen Dienstpfad.")
arguments[0] = str(new / python)
arguments[2] = str(new / worker)
with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".voxdrop-", delete=False) as handle:
    staged = Path(handle.name)
    try:
        plistlib.dump(agent, handle)
        handle.flush()
        os.fsync(handle.fileno())
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)
PY
}

if [ -e "$target" ]; then
    mv "$target" "$stage/previous.app"
fi
if ! mv "$stage/VoxDrop.app" "$target"; then
    if [ -e "$stage/previous.app" ]; then
        mv "$stage/previous.app" "$target"
    fi
    exit 1
fi
if [ -e "$previous_name" ]; then
    if ! mv "$previous_name" "$stage/previous-name.app" || ! relocate_login_agent; then
        mv "$target" "$stage/VoxDrop.app"
        if [ -e "$stage/previous.app" ]; then
            mv "$stage/previous.app" "$target"
        fi
        if [ -e "$stage/previous-name.app" ]; then
            mv "$stage/previous-name.app" "$previous_name"
        fi
        exit 1
    fi
fi

legacy="$project_dir/SMB Transcriber.app"
if [ -d "$legacy" ] && [ ! -e "$runtime/previous-project-build.app" ]; then
    legacy_id=$(plutil -extract CFBundleIdentifier raw -o - "$legacy/Contents/Info.plist")
    if [ "$legacy_id" = local.smb-transcriber ]; then
        mv "$legacy" "$runtime/previous-project-build.app"
    fi
fi
printf '%s\n' "$target"
