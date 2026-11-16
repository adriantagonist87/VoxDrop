#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
runtime="$project_dir/.runtime"
reference="$runtime/aTrain"
python="$reference/.venv/bin/python"
metal_python="$runtime/metal-venv/bin/python"
qwen_python="$runtime/qwen-venv/bin/python"
dover_packages="$runtime/dover-packages"
output="$runtime/package/VoxDrop.app"
if [ ! -x "$python" ] || [ ! -x "$metal_python" ] || [ ! -x "$qwen_python" ] || [ ! -d "$dover_packages/dover_lap" ]; then
    printf '%s\n' 'Bitte zuerst scripts/bootstrap.sh ausführen.' >&2
    exit 1
fi

mkdir -p "$runtime/package" "$runtime/swift-cache"
stage=$(mktemp -d "$runtime/package/.build.XXXXXX")
trap 'rm -rf "$stage"' EXIT
app="$stage/VoxDrop.app"
bundle="$app/Contents"
resources="$bundle/Resources"
mkdir -p "$bundle/MacOS" "$resources/Engine" "$resources/Python" "$resources/QwenPackages" "$stage/AppIcon.iconset"
mkdir -p "$resources/DoverPackages"
cp "$project_dir/macos/Info.plist" "$bundle/Info.plist"
cp "$project_dir/macos/VoxDropLogo.png" "$resources/VoxDropLogo.png"
minimum=$(/usr/bin/plutil -extract LSMinimumSystemVersion raw -o - "$bundle/Info.plist")
xcrun swiftc -parse-as-library -O -target "arm64-apple-macos$minimum" \
    -module-cache-path "$runtime/swift-cache" \
    -o "$bundle/MacOS/VoxDrop" "$project_dir/macos/TranscriberApp.swift"
xcrun swift -module-cache-path "$runtime/swift-cache" "$project_dir/macos/AppIcon.swift" \
    "$resources/VoxDropLogo.png" "$stage/AppIcon.iconset"
iconutil -c icns "$stage/AppIcon.iconset" -o "$resources/AppIcon.icns"

python_home=$("$python" -BEs -c 'import sys; print(sys.base_prefix)')
packages=$("$python" -BEs -c 'import sysconfig; print(sysconfig.get_path("purelib"))')
metal_packages=$("$metal_python" -BEs -c 'import sysconfig; print(sysconfig.get_path("purelib"))')
qwen_packages=$("$qwen_python" -BEs -c 'import sysconfig; print(sysconfig.get_path("purelib"))')
bundled_packages="$resources/Python/lib/python3.12/site-packages"
rsync -a --exclude='__pycache__/' --exclude='*.pyc' "$python_home/" "$resources/Python/"
rsync -a --exclude='__pycache__/' --exclude='*.pyc' --exclude='__editable__*' \
    --exclude='ctranslate2' --exclude='ctranslate2-*.dist-info' \
    "$packages/" "$bundled_packages/"
rsync -a --exclude='__pycache__/' --exclude='*.pyc' \
    "$metal_packages/ctranslate2" "$metal_packages"/ctranslate2-*.dist-info \
    "$reference/aTrain_core" "$bundled_packages/"

rsync -a --exclude='__pycache__/' --exclude='*.pyc' "$qwen_packages/" "$resources/QwenPackages/"
rsync -a --exclude='__pycache__/' --exclude='*.pyc' --exclude='bin/' "$dover_packages/" "$resources/DoverPackages/"
for file in watch_service.py voxdrop.py transcription_worker.py silence.py smb_paths.py login_agent.py app_upgrade.py airdrop.example.json qwen_backend.py qwen-models.json speaker_diarization.py; do
    cp "$project_dir/$file" "$resources/Engine/"
done
cp "$reference/LICENSE" "$resources/Engine/aTrain-LICENSE.txt"
"$resources/Python/bin/python3.12" -BEs -c 'import av, ctranslate2, torch; from aTrain_core.engine import decode; assert ctranslate2.__version__ == "4.9.0"'
"$resources/Python/bin/python3.12" -BES -c '
import sys
sys.path.insert(0, sys.argv[1])
import mlx.core
from mlx_audio.stt import load
' "$resources/QwenPackages"
"$resources/Python/bin/python3.12" -BEs -c '
import sys
sys.path.append(sys.argv[1])
from dover_lap.src.doverlap import DOVERLap
' "$resources/DoverPackages"
/usr/bin/codesign --force --sign - --timestamp=none "$app"
/usr/bin/codesign --verify --strict "$app"

if [ -e "$output" ]; then
    mv "$output" "$stage/previous.app"
fi
if ! mv "$app" "$output"; then
    if [ -e "$stage/previous.app" ]; then
        mv "$stage/previous.app" "$output"
    fi
    exit 1
fi
printf '%s\n' "$output"
