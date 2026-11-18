#!/bin/sh
set -eu

project=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
runtime="$project/.runtime"
zig="${1:?Pfad zu Zig angeben}"
uv="${2:?Pfad zum offiziellen uv-Archiv für Windows x64 angeben}"
python="$runtime/aTrain/.venv/bin/python"
package="$runtime/package"
version=$(/usr/bin/plutil -extract CFBundleShortVersionString raw -o - "$project/macos/Info.plist")
reference=$(sed -n 's/^commit=//p' "$project/scripts/bootstrap.sh")
name="VoxDrop-$version-Windows-x64"

mkdir -p "$package"
stage=$(mktemp -d "$package/.windows.XXXXXX")
trap 'rm -rf "$stage"' EXIT
app="$stage/VoxDrop"
mkdir -p "$app/windows" "$app/Engine" "$app/assets" "$app/tools" "$app/DoverPackages" "$app/Quellcode"

checksum=$(cut -d ' ' -f 1 "$uv.sha256")
printf '%s  %s\n' "$checksum" "$uv" | shasum -a 256 -c -
unzip -p "$uv" '*uv.exe' > "$app/tools/uv.exe"
cp "$uv.sha256" "$app/tools/uv-download.sha256"
for filename in diagnose.py launcher.c pyproject.toml uv.lock; do
    cp "$project/windows/$filename" "$app/windows/"
done
cp "$project/windows/README.md" "$app/Installation.md"
cp "$project/LICENSE" "$app/LICENSE"
rsync -a --exclude='__pycache__/' --exclude='*.pyc' "$project/desktop/" "$app/Desktop/"
cp "$project/macos/VoxDropLogo.png" "$app/assets/"
cp "$project/assets/VoxDrop.ico" "$app/assets/"
for source in watch_service.py voxdrop.py transcription_worker.py silence.py smb_paths.py platform_io.py queue_control.py media_history.py history_store.py app_lifecycle.py runtime_logs.py login_agent.py \
    qwen_backend.py qwen_cuda.py qwen-models.json qwen-windows-models.json speaker_diarization.py; do
    cp "$project/$source" "$app/Engine/"
done
rsync -a --exclude='__pycache__/' --exclude='*.pyc' "$runtime/aTrain/aTrain_core" "$app/Engine/"
cp "$runtime/aTrain/LICENSE" "$app/Engine/aTrain-LICENSE.txt"
rsync -a --exclude='__pycache__/' --exclude='*.pyc' \
    "$runtime/dover-packages/dover_lap" "$runtime/dover-packages"/dover_lap-*.dist-info "$app/DoverPackages/"
git -C "$runtime/aTrain" archive --format=tar.gz --prefix="aTrain-$reference/" \
    -o "$app/Quellcode/aTrain-$reference.tar.gz" "$reference"

"$python" - "$app/assets/VoxDrop.ico" "$stage" "$app/DoverPackages" <<'PY'
from pathlib import Path
import struct
import sys

icon, stage, dover = (Path(arg) for arg in sys.argv[1:])

def resource(kind, name, data, language=0x0407):
    header = struct.pack("<IIHHHHIHHII", len(data), 32, 0xFFFF, kind,
                         0xFFFF, name, 0, 0x1030 if kind else 0, language, 0, 0)
    return header + data + bytes((-len(data)) % 4)

# Windows .res with one icon group and one resource per image size.
data = icon.read_bytes()
count = struct.unpack_from("<H", data, 4)[0]
resources = [resource(0, 0, b"", 0)]
group = bytearray(data[:6])
for index in range(count):
    entry = 6 + index * 16
    size, offset = struct.unpack_from("<II", data, entry + 8)
    group.extend(data[entry:entry + 12] + struct.pack("<H", index + 1))
    resources.append(resource(3, index + 1, data[offset:offset + size]))
resources.append(resource(14, 1, group))
(stage / "voxdrop.res").write_bytes(b"".join(resources))

# Only DOVER-Lap's greedy mapper is used. Load its unrelated native DER
# extension on demand, so Windows needs no C++ compiler at installation.
hungarian = dover / "dover_lap/src/mapping/hungarian.py"
text = hungarian.read_text()
text = text.replace("from spyder import DER\n", "", 1)
text = text.replace("        N = len(self.turns_list)",
                    "        from spyder import DER\n\n        N = len(self.turns_list)", 1)
text = text.replace("        metrics = DER(ref, sys)",
                    "        from spyder import DER\n\n        metrics = DER(ref, sys)", 1)
hungarian.write_text(text)
PY
export ZIG_GLOBAL_CACHE_DIR="${ZIG_GLOBAL_CACHE_DIR:-$runtime/zig-global}"
export ZIG_LOCAL_CACHE_DIR="${ZIG_LOCAL_CACHE_DIR:-$runtime/zig-local}"
hash=$(shasum -a 256 "$project/windows/uv.lock" | cut -c 1-12)
"$zig" cc -target x86_64-windows-gnu -O2 -municode -Wl,--subsystem,windows \
    "-DVOXDROP_RUNTIME=L\"runtime-$hash\"" "$project/windows/launcher.c" "$stage/voxdrop.res" \
    -luser32 -lshell32 -o "$app/VoxDrop.exe"
file "$app/VoxDrop.exe"
(cd "$stage" && zip -qr "$name.zip" VoxDrop)
unzip -tq "$stage/$name.zip"
mv "$stage/$name.zip" "$package/$name.zip"
(cd "$package" && shasum -a 256 "$name.zip" > "$name.zip.sha256")
printf '%s\n' "$package/$name.zip"
