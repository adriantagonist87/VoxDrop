#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
runtime="$project_dir/.runtime"
reference="$runtime/aTrain"
commit=ea8a7057857220b4299c0ba0b2aaf6def2f35b87
url=https://github.com/aTrainTranscription/aTrain.git
uv_version=0.13.7
python_version=3.12.13
mkdir -p "$runtime"

if [ -n "${UV_BIN:-}" ]; then
    uv="$UV_BIN"
else
    uv="$runtime/uv-aarch64-apple-darwin/uv"
    if [ ! -x "$uv" ]; then
        archive=uv-aarch64-apple-darwin.tar.gz
        asset_url="https://github.com/astral-sh/uv/releases/download/$uv_version/$archive"
        (
            cd "$runtime"
            curl --fail --silent --show-error --location "$asset_url" --output "$archive"
            curl --fail --silent --show-error --location "$asset_url.sha256" --output "$archive.sha256"
            shasum -a 256 --check "$archive.sha256"
            tar -xzf "$archive"
        )
    fi
fi

if [ ! -d "$reference/.git" ]; then
    git init -q "$reference"
fi
if ! git -C "$reference" cat-file -e "$commit^{commit}" 2>/dev/null; then
    git -C "$reference" fetch --depth 1 "$url" "$commit"
fi
git -C "$reference" switch --detach "$commit"
if [ -n "$(git -C "$reference" status --porcelain --untracked-files=no)" ]; then
    printf '%s\n' 'Der aTrain-Referenzcode enthält lokale Änderungen.' >&2
    exit 1
fi

export UV_PYTHON_INSTALL_DIR="$runtime/python"
export UV_PYTHON_BIN_DIR="$runtime/bin"
export UV_CACHE_DIR="$runtime/uv-cache"
"$uv" python install "$python_version" --no-bin
"$uv" sync --directory "$reference" --locked --python "$python_version"
UV_PROJECT_ENVIRONMENT="$runtime/metal-venv" \
    "$uv" sync --directory "$project_dir/metal" --locked --python "$python_version"
UV_PROJECT_ENVIRONMENT="$runtime/qwen-venv" \
    "$uv" sync --directory "$project_dir/qwen" --locked --python "$python_version"
"$uv" pip install --python "$reference/.venv/bin/python" --target "$runtime/dover-packages" \
    --require-hashes --no-deps --no-binary spy-der -r "$project_dir/dover-requirements.txt"
# DOVER-Lap 1.3.1 needs pairwise broadcasting before reduction on NumPy 2.
"$reference/.venv/bin/python" -BEs - "$runtime/dover-packages" <<'PY'
import sys
from pathlib import Path

source = Path(sys.argv[1]) / "dover_lap/src/mapping/greedy.py"
code = source.read_text()
old = "cost_tensor = np.sum(list(pairwise_costs.values()))"
new = "cost_tensor = sum(pairwise_costs.values())"
if old in code:
    source.write_text(code.replace(old, new, 1))
elif new not in code:
    raise SystemExit("Unerwartete DOVER-Lap-Version bei der NumPy-Kompatibilitätskorrektur.")
PY
