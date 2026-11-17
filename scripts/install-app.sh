#!/bin/sh
set -eu

project=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
app="$project/.runtime/package/VoxDrop.app"
python="$app/Contents/Resources/Python/bin/python3.12"

"$python" -BEs "$project/macos/install.py" "$app" "$@"
