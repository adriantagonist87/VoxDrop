"""Build a Windows test ZIP natively using verified release dependencies and Zig.

The reference ZIP supplies uv, pinned aTrain and patched DOVER-Lap.
All first-party application sources come from the clean current checkout.
"""

import argparse
import hashlib
import json
import plistlib
import re
import shutil
import struct
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
ENGINE = (
    "watch_service.py voxdrop.py transcription_worker.py silence.py smb_paths.py "
    "platform_io.py gpu_budget.py queue_control.py media_history.py history_store.py app_lifecycle.py runtime_logs.py login_agent.py qwen_backend.py qwen_cuda.py qwen-models.json "
    "qwen-windows-models.json speaker_diarization.py"
).split()


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def resource(kind, name, data, language=0x0407):
    header = struct.pack("<IIHHHHIHHII", len(data), 32, 0xFFFF, kind,
                         0xFFFF, name, 0, 0x1030 if kind else 0, language, 0, 0)
    return header + data + bytes((-len(data)) % 4)


def icon_resources(icon):
    data = icon.read_bytes()
    count = struct.unpack_from("<H", data, 4)[0]
    result = [resource(0, 0, b"", 0)]
    group = bytearray(data[:6])
    for index in range(count):
        entry = 6 + index * 16
        size, offset = struct.unpack_from("<II", data, entry + 8)
        group.extend(data[entry:entry + 12] + struct.pack("<H", index + 1))
        result.append(resource(3, index + 1, data[offset:offset + size]))
    result.append(resource(14, 1, group))
    return b"".join(result)


def copy_source(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.suffix in {".py", ".qml", ".md", ".json", ".c", ".toml", ".lock"}:
        destination.write_bytes(source.read_bytes().replace(b"\r\n", b"\n"))
    else:
        shutil.copyfile(source, destination)


def build(args):
    if digest(args.base_zip) != args.base_sha256.lower():
        raise ValueError("Reference ZIP checksum mismatch")
    subprocess.run(["git", "diff", "--exit-code", "HEAD", "--"], cwd=ROOT, check=True)
    untracked = subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT, text=True
    ).strip()
    if untracked:
        raise ValueError("Commit untracked sources before building: " + untracked)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    version = plistlib.loads((ROOT / "macos/Info.plist").read_bytes())["CFBundleShortVersionString"]
    reference = re.search(r"^commit=(\w+)$", (ROOT / "scripts/bootstrap.sh").read_text(), re.M)[1]
    args.output.mkdir(parents=True, exist_ok=True)
    name = f"VoxDrop-{version}-Windows-x64-{commit[:12]}"
    target = args.output / (name + ".zip")
    if target.exists():
        raise FileExistsError(target)
    with tempfile.TemporaryDirectory(prefix="windows-", dir=args.output) as temporary:
        stage = Path(temporary)
        app = stage / "VoxDrop"
        # Extract only vendor dependencies and licensed sources, never old app code.
        prefixes = ("VoxDrop/tools/", "VoxDrop/DoverPackages/", "VoxDrop/Quellcode/",
                    "VoxDrop/Engine/aTrain_core/", "VoxDrop/Engine/aTrain-LICENSE.txt")
        with ZipFile(args.base_zip) as archive:
            for item in archive.infolist():
                path = PurePosixPath(item.filename)
                if (path.is_absolute() or ".." in path.parts or "\\" in item.filename
                        or (item.external_attr >> 16) & 0o170000 == 0o120000):
                    raise ValueError("Unsafe reference ZIP entry")
                if item.filename.startswith(prefixes) and not item.is_dir():
                    destination = stage.joinpath(*path.parts)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(archive.read(item))
        with tarfile.open(app / f"Quellcode/aTrain-{reference}.tar.gz") as archive:
            core = f"aTrain-{reference}/aTrain_core/"
            expected = set()
            for item in archive.getmembers():
                if item.name.startswith(core) and item.isfile():
                    relative = PurePosixPath(item.name[len(core):])
                    if relative.is_absolute() or ".." in relative.parts:
                        raise ValueError("Unsafe aTrain archive entry")
                    file = app / "Engine/aTrain_core" / relative
                    if file.read_bytes() != archive.extractfile(item).read():
                        raise ValueError(f"aTrain differs from pinned source: {relative}")
                    expected.add(relative.as_posix())
            actual = {p.relative_to(app / "Engine/aTrain_core").as_posix()
                      for p in (app / "Engine/aTrain_core").rglob("*") if p.is_file()}
            if not expected or expected != actual:
                raise ValueError("Incomplete pinned aTrain source")
        for source in (ROOT / "desktop").rglob("*"):
            if source.is_file() and "__pycache__" not in source.parts and source.suffix != ".pyc":
                copy_source(source, app / "Desktop" / source.relative_to(ROOT / "desktop"))
        for filename in ENGINE:
            copy_source(ROOT / filename, app / "Engine" / filename)
        for filename in ("diagnose.py", "launcher.c", "pyproject.toml", "uv.lock"):
            copy_source(ROOT / "windows" / filename, app / "windows" / filename)
        copy_source(ROOT / "windows/README.md", app / "Installation.md")
        copy_source(ROOT / "LICENSE", app / "LICENSE")
        copy_source(ROOT / "macos/VoxDropLogo.png", app / "assets/VoxDropLogo.png")
        copy_source(ROOT / "assets/VoxDrop.ico", app / "assets/VoxDrop.ico")
        resources = stage / "voxdrop.res"
        resources.write_bytes(icon_resources(app / "assets/VoxDrop.ico"))
        runtime_hash = digest(app / "windows/uv.lock")[:12]
        subprocess.run([str(args.zig), "cc", "-target", "x86_64-windows-gnu", "-O2",
                        "-municode", "-Wl,--subsystem,windows",
                        f'-DVOXDROP_RUNTIME=L"runtime-{runtime_hash}"',
                        str(app / "windows/launcher.c"), str(resources),
                        "-luser32", "-lshell32", "-o", str(app / "VoxDrop.exe")], check=True)
        (app / "build-info.json").write_text(json.dumps({
            "code_commit": commit, "version": version,
            "base_zip_sha256": args.base_sha256.lower(), "atrain_commit": reference,
            "runtime": f"runtime-{runtime_hash}",
            "zig_version": subprocess.check_output([str(args.zig), "version"], text=True).strip(),
        }, indent=2) + "\n", encoding="utf-8")
        shutil.make_archive(str(stage / name), "zip", stage, "VoxDrop")
        with ZipFile(stage / (name + ".zip")) as archive:
            if archive.testzip() is not None:
                raise ValueError("Output ZIP integrity failure")
        (stage / (name + ".zip")).rename(target)
    target.with_suffix(".zip.sha256").write_text(f"{digest(target)}  {target.name}\n", encoding="utf-8")
    print(target)


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--zig", type=Path, required=True)
    cli.add_argument("--base-zip", type=Path, required=True)
    cli.add_argument("--base-sha256", required=True)
    cli.add_argument("--output", type=Path, default=ROOT / ".runtime/package")
    args = cli.parse_args()
    args.zig = args.zig.resolve(strict=True)
    args.base_zip = args.base_zip.resolve(strict=True)
    args.output = args.output.resolve()
    build(args)
