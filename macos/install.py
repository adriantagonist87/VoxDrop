"""Install an application folder while preserving user state and models."""

import argparse
import fcntl
import os
import plistlib
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path


def execute(*arguments):
    return subprocess.run(
        [str(value) for value in arguments],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


def bundle_identifier(app):
    with (app / "Contents/Info.plist").open("rb") as handle:
        return plistlib.load(handle)["CFBundleIdentifier"]


def worker_command(app, profile, data, *, utf8=True):
    resources = app / "Contents/Resources"
    return [
        str(resources / "Python/bin/python3.12"), "-BEs",
        *(["-Xutf8"] if utf8 else []),
        str(resources / "Engine/watch_service.py"),
        "--state-dir", str(profile / "service"),
        "--model-data", str(data), "run", str(profile / "config.json"),
    ]


def processes():
    output = execute("/bin/ps", "-xww", "-o", "pid=,command=")
    return {
        int(pid): command
        for line in output.splitlines()
        for pid, command in [line.strip().split(None, 1)]
    }


def stop_processes(commands):
    matching = {pid for pid, command in processes().items() if command in commands}
    for pid in matching:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    while matching.intersection(processes()):
        print("VoxDrop schließt den laufenden Auftrag ab …", flush=True)
        time.sleep(2)
    return bool(matching)


def migrate_models(profile, target):
    previous = profile / "data"
    if previous.is_symlink():
        if previous.resolve() != target.resolve():
            raise ValueError("Der bisherige Modellspeicher verweist auf einen anderen Ordner.")
        return False
    if not previous.exists():
        return False
    if target.exists():
        if any(target.iterdir()):
            raise ValueError("Beide Modellordner enthalten Daten. Die Bestände müssen zuerst geprüft werden.")
        target.rmdir()
    shutil.move(str(previous), str(target))
    try:
        previous.symlink_to(target, target_is_directory=True)
    except OSError:
        shutil.move(str(target), str(previous))
        raise
    return True


def start_service(app, profile, data):
    command = worker_command(app, profile, data)
    command[-2] = "start"
    execute(*command)


def install(source, applications, profile):
    destination = applications / "VoxDrop"
    app = destination / "VoxDrop.app"
    legacy = applications / "VoxDrop.app"
    data = destination / "Modelle"
    native_profile = Path.home() / "Library/Application Support/VoxDrop"
    agent = Path.home() / "Library/LaunchAgents/local.voxdrop.worker.plist"
    agent_bytes = agent.read_bytes() if profile == native_profile and agent.exists() else None
    candidates = (app, legacy)
    for candidate in (source, *candidates):
        if candidate.exists() and (
            candidate.is_symlink() or bundle_identifier(candidate) != "local.voxdrop"
        ):
            raise ValueError(f"Am App-Pfad liegt eine andere Anwendung: {candidate}")
    if destination.is_symlink() or data.is_symlink() or profile.is_symlink():
        raise ValueError("Der Installations- oder Datenordner ist ein unerwarteter Symlink.")
    commands = {
        " ".join(worker_command(candidate, profile, model_data, utf8=utf8))
        for candidate in candidates
        for model_data in (profile / "data", data)
        for utf8 in (True, False)
    }
    if agent_bytes:
        existing = plistlib.loads(agent_bytes)
        expected = [
            worker_command(candidate, profile, model_data, utf8=utf8)
            for candidate in candidates
            for model_data in (profile / "data", data)
            for utf8 in (True, False)
        ] + [[str(candidate / "Contents/MacOS/VoxDrop"), "--background"] for candidate in candidates]
        if existing.get("Label") != "local.voxdrop.worker" or existing.get("ProgramArguments") not in expected:
            raise ValueError("Die vorhandene Anmelderegistrierung hat eine andere Konfiguration.")

    applications.mkdir(parents=True, exist_ok=True)
    destination.mkdir(exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".voxdrop-install-", dir=applications))
    prepared = stage / "VoxDrop.app"
    closed = restart = moved_models = installed = succeeded = False
    backups = []
    lock = None
    try:
        execute("/usr/bin/ditto", source, prepared)
        execute("/usr/bin/codesign", "--verify", "--deep", "--strict", prepared)
        gui_commands = {
            str(candidate / "Contents/MacOS/VoxDrop") + arguments
            for candidate in candidates for arguments in ("", " --background")
        }
        before = set(processes().values())
        closed = bool(before.intersection(gui_commands))
        restart = bool(before.intersection(commands))
        if agent_bytes:
            subprocess.run(
                ["/bin/launchctl", "bootout", f"gui/{os.getuid()}/local.voxdrop.worker"],
                capture_output=True, check=False,
            )
        stop_processes(gui_commands)
        stop_processes(commands)
        if (profile / "service").is_dir():
            lock = (profile / "service/service.lock").open("a")
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        moved_models = migrate_models(profile, data)
        for index, candidate in enumerate(candidates):
            if candidate.exists():
                backup = stage / f"previous-{index}.app"
                candidate.rename(backup)
                backups.append((backup, candidate))
        prepared.rename(app)
        installed = True
        if agent_bytes:
            resources = app / "Contents/Resources"
            updated = execute(
                resources / "Python/bin/python3.12", "-BEs", resources / "Engine/watch_service.py",
                "--state-dir", profile / "service", "--model-data", data,
                "autostart", "preview", profile / "config.json",
            )
            staged_agent = stage / "agent.plist"
            staged_agent.write_bytes(plistlib.dumps(plistlib.loads(updated.encode())))
            staged_agent.chmod(0o600)
            staged_agent.replace(agent)
        if lock:
            lock.close()
            lock = None
        if restart:
            start_service(app, profile, data)
        succeeded = True
        if profile == native_profile:
            try:
                execute(
                    "/usr/bin/xcrun", "swift",
                    Path(__file__).with_name("UpdateDock.swift"), app, legacy,
                )
            except (OSError, subprocess.CalledProcessError):
                print("Die bisherige Dock-Verknüpfung konnte nicht aktualisiert werden.")
        print(app)
        return app
    except Exception:
        if lock:
            lock.close()
            lock = None
        if installed:
            stop_processes(commands)
            shutil.rmtree(app)
        for backup, previous in backups:
            backup.rename(previous)
        if moved_models:
            (profile / "data").unlink()
            shutil.move(str(data), str(profile / "data"))
        if agent_bytes:
            agent.write_bytes(agent_bytes)
        if restart:
            previous = next(candidate for candidate in candidates if candidate.exists())
            start_service(previous, profile, profile / "data")
        if closed:
            execute("/usr/bin/open", legacy if legacy.exists() else app)
        raise
    finally:
        if lock:
            lock.close()
        if succeeded or not any(stage.glob("previous-*.app")):
            shutil.rmtree(stage)
        else:
            print(f"Die bisherige App liegt zur Wiederherstellung unter {stage}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--applications", type=Path)
    parser.add_argument("--profile", type=Path, default=Path.home() / "Library/Application Support/VoxDrop")
    args = parser.parse_args()
    applications = args.applications
    if applications is None:
        personal = Path.home() / "Applications"
        applications = personal if (personal / "VoxDrop.app").exists() or (personal / "VoxDrop").exists() else Path("/Applications")
        if not os.access(applications, os.W_OK):
            applications = personal
    install(args.bundle.resolve(), applications.expanduser().absolute(), args.profile.expanduser().absolute())


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"VoxDrop konnte nicht installiert werden: {error}") from error
