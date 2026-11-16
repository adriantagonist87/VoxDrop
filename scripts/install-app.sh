#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
runtime="$project_dir/.runtime"
app="$runtime/package/VoxDrop.app"
support="$HOME/Library/Application Support/VoxDrop"
resources="$app/Contents/Resources"
python="$resources/Python/bin/python3.12"
engine="$resources/Engine"

bundle_id() {
    /usr/bin/plutil -extract CFBundleIdentifier raw -o - "$1/Contents/Info.plist"
}

metadata() {
    "$python" -BEs - "$engine" "$1" <<'PY'
import sys

sys.path.insert(0, sys.argv[1])
import app_upgrade

print(getattr(app_upgrade, sys.argv[2]))
PY
}

exists() { [ -e "$1" ] || [ -L "$1" ]; }

/usr/bin/codesign --verify --strict "$app"
new_id=$(bundle_id "$app")
old_id=$(metadata PREVIOUS_BUNDLE_ID)
old_name="$(metadata PREVIOUS_NAME).app"
if exists "$HOME/Applications/VoxDrop.app" || exists "$HOME/Applications/$old_name"; then
    apps="$HOME/Applications"
elif exists /Applications/VoxDrop.app || exists "/Applications/$old_name" || [ -w /Applications ]; then
    apps=/Applications
else
    apps="$HOME/Applications"
fi
target="$apps/VoxDrop.app"
previous="$apps/$old_name"

for existing in "$target" "$previous"; do
    if exists "$existing"; then
        existing_id=$(bundle_id "$existing") || exit 1
        if [ -L "$existing" ] || { [ "$existing_id" != "$new_id" ] && [ "$existing_id" != "$old_id" ]; }; then
            printf 'Am Installationsort liegt bereits eine andere App: %s\n' "$existing" >&2
            exit 1
        fi
    fi
done

mkdir -p "$apps"
stage=$(mktemp -d "$apps/.voxdrop-install.XXXXXX")
trap 'rm -rf "$stage"' EXIT
/usr/bin/ditto "$app" "$stage/VoxDrop.app"
/usr/bin/codesign --verify --strict "$stage/VoxDrop.app"

resume=$("$python" -BEs "$engine/app_upgrade.py" "$support" "$target")
"$python" -BEs - "$runtime" "$support" "$engine" <<'PY'
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
    with tempfile.TemporaryDirectory(prefix='.voxdrop-', dir=support.parent) as directory:
        staged = Path(directory) / 'data'
        staged.mkdir(mode=0o700)
        history = source / 'service'
        if history.is_dir():
            with (history / 'service.lock').open('a') as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as error:
                    raise SystemExit('Der Projektdienst verarbeitet noch Aufträge.') from error
                shutil.copytree(history, staged / 'service', ignore=shutil.ignore_patterns('service.lock'))
        shutil.copytree(source / 'data/models', staged / 'data/models')
        settings = source / 'config.json'
        if settings.is_file():
            shutil.copy2(settings, staged / 'config.json')
        staged.rename(support)
else:
    provision_models(support / 'data', source=source / 'data')
PY

if [ -e "$previous" ]; then
    mv "$previous" "$stage/previous-name.app"
fi
if [ -e "$target" ] && ! mv "$target" "$stage/previous.app"; then
    if [ -e "$stage/previous-name.app" ]; then
        mv "$stage/previous-name.app" "$previous"
    fi
    exit 1
fi
if ! mv "$stage/VoxDrop.app" "$target"; then
    if [ -e "$stage/previous.app" ]; then
        mv "$stage/previous.app" "$target"
    fi
    if [ -e "$stage/previous-name.app" ]; then
        mv "$stage/previous-name.app" "$previous"
    fi
    exit 1
fi

if [ "$resume" = "resume" ]; then
    installed="$target/Contents/Resources"
    config="$support/config.json"
    if [ ! -f "$config" ]; then
        config="$installed/Engine/airdrop.example.json"
    fi
    "$installed/Python/bin/python3.12" -BEs "$installed/Engine/watch_service.py" \
        --state-dir "$support/service" --model-data "$support/data" start "$config"
fi
printf '%s\n' "$target"
