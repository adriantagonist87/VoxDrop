"""One-time migration from pre-1.0 macOS installations."""

import fcntl
import os
import plistlib
import signal
import subprocess
import sys
import time
from pathlib import Path

import login_agent

PREVIOUS_NAME = "SMB Transcriber"
PREVIOUS_BUNDLE_ID = "local.smb-transcriber"
PREVIOUS_LABEL = PREVIOUS_BUNDLE_ID + ".worker"
RESOURCES = Path("Contents/Resources")
PYTHON = RESOURCES / "Python/bin/python3.12"
WORKER = RESOURCES / "Engine/watch_service.py"
DEFAULT_SETTINGS = RESOURCES / "Engine/airdrop.example.json"


def previous_registration(path, support):
    if path.is_symlink():
        raise ValueError("Die bisherige Login-Konfiguration ist ein Symlink.")
    if not path.exists():
        return False
    with path.open("rb") as handle:
        agent = plistlib.load(handle)
    args = agent.get("ProgramArguments", [])
    if (
        agent.get("Label") != PREVIOUS_LABEL
        or not isinstance(args, list)
        or len(args) != 9
        or not isinstance(args[0], str)
        or not isinstance(args[-1], str)
        or len(Path(args[0]).parents) < 5
    ):
        raise ValueError(
            "Die bisherige Login-Konfiguration kann nicht übernommen werden."
        )
    app = Path(args[0]).parents[4]
    if app.name not in (
        "VoxDrop.app",
        PREVIOUS_NAME + ".app",
    ) or args not in worker_commands(app, support):
        raise ValueError(
            "Die bisherige Login-Konfiguration verwendet einen anderen Dienstpfad."
        )
    return True


def worker_commands(app, support):
    command = [
        str(app / PYTHON),
        "-BEs",
        str(app / WORKER),
        "--state-dir",
        str(support / "service"),
        "--model-data",
        str(support / "data"),
        "run",
    ]
    return [
        command + [str(config)]
        for config in (
            support / "config.json",
            app / DEFAULT_SETTINGS,
        )
    ]


def stop_detached_worker(app, support):
    apps = {app}
    for parent in (Path("/Applications"), Path.home() / "Applications"):
        apps.update(parent / (name + ".app") for name in ("VoxDrop", PREVIOUS_NAME))
    known = {
        " ".join(command)
        for candidate in apps
        for command in worker_commands(candidate, support)
    }
    process_list = subprocess.check_output(
        ["/bin/ps", "-xww", "-o", "pid=", "-o", "command="], text=True
    )
    for line in process_list.splitlines():
        pid, _, command = line.strip().partition(" ")
        command = command.lstrip()
        if command in known:
            try:
                os.kill(int(pid), signal.SIGTERM)
            except ProcessLookupError:
                pass


def launchctl(*args):
    return subprocess.run(
        ["/bin/launchctl", *args], capture_output=True, text=True, check=False
    )


def migrate_preferences():
    def defaults(*args, value=None):
        return subprocess.run(
            ["/usr/bin/defaults", *args], input=value, capture_output=True, check=False
        )

    previous = defaults("export", PREVIOUS_BUNDLE_ID, "-")
    if previous.returncode:
        return
    current = defaults("export", login_agent.BUNDLE_IDENTIFIER, "-")
    preferences = plistlib.loads(previous.stdout)
    if current.returncode == 0:
        preferences.update(plistlib.loads(current.stdout))
    imported = defaults(
        "import", login_agent.BUNDLE_IDENTIFIER, "-", value=plistlib.dumps(preferences)
    )
    if imported.returncode == 0:
        defaults("delete", PREVIOUS_BUNDLE_ID)


def acquire_previous_service(lock, app, support, service_target, registered):
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return False
    except BlockingIOError:
        if registered:
            launchctl("kill", "SIGTERM", service_target)
        stop_detached_worker(app, support)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        time.sleep(0.1)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            pass
    raise RuntimeError(
        "Der bisherige Dienst ist noch aktiv. Warte auf den Abschluss und prüfe erneut."
    )


def migrate(support, app):
    previous = support.with_name(PREVIOUS_NAME)
    previous_agent = login_agent.agent_path().with_name(PREVIOUS_LABEL + ".plist")
    preferences = Path.home() / "Library/Preferences" / (PREVIOUS_BUNDLE_ID + ".plist")
    if not any(
        path.exists() or path.is_symlink()
        for path in (previous, previous_agent, preferences)
    ):
        return False
    if (
        support.is_symlink()
        or previous.is_symlink()
        or (previous.exists() and not previous.is_dir())
    ):
        raise ValueError("Die App-Daten können nicht sicher übernommen werden.")
    if previous.exists() and support.exists():
        raise ValueError(
            "Es gibt bereits zwei Ordner mit App-Daten. Beide wurden beibehalten."
        )

    registered = previous_registration(previous_agent, previous)
    service_target = f"gui/{os.getuid()}/{PREVIOUS_LABEL}"
    migrated_service = False
    if previous.is_dir():
        service = previous / "service"
        if service.is_symlink():
            raise ValueError("Der bisherige Dienstordner ist ein Symlink.")
        service.mkdir(exist_ok=True)
        lock_path = service / "service.lock"
        with os.fdopen(
            os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600), "a"
        ) as lock:
            migrated_service = acquire_previous_service(
                lock, app, previous, service_target, registered
            )
            if registered and launchctl("print", service_target).returncode == 0:
                result = launchctl("bootout", service_target)
                if result.returncode:
                    raise RuntimeError(result.stderr.strip())
                migrated_service = True
            previous.rename(support)

    if registered:
        settings = support / "config.json"
        if not settings.is_file():
            settings = app / DEFAULT_SETTINGS
        login_agent.update(
            True,
            login_agent.definition(
                app / WORKER,
                settings,
                support / "service",
                support / "data",
                python=app / PYTHON,
            ),
        )
        previous_agent.unlink()
    if preferences.is_file() and not preferences.is_symlink():
        migrate_preferences()
    return migrated_service


if __name__ == "__main__":
    try:
        if migrate(Path(sys.argv[1]), Path(sys.argv[2])):
            print("resume")
    except (OSError, RuntimeError, ValueError) as error:
        sys.exit(str(error))
