"""Resolve network folders through the operating system's SMB client."""

import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit

from platform_io import WINDOWS


def smb_mounts():
    if WINDOWS:
        return []
    try:
        output = subprocess.check_output(
            ["/sbin/mount", "-t", "smbfs"], text=True, timeout=10
        )
    except subprocess.SubprocessError as error:
        raise OSError(
            "Die gemounteten SMB-Freigaben können nicht abgefragt werden."
        ) from error
    mounts = []
    for line in output.splitlines():
        remote, separator, details = line.partition(" on ")
        mount, mount_type, _ = details.rpartition(" (smbfs")
        if separator and mount_type and remote.startswith("//"):
            address = urlsplit("smb:" + remote)
            mounts.append(
                (address.hostname, unquote(address.path).strip("/"), Path(mount))
            )
    return mounts


def on_network_volume(path, mounts=None):
    if WINDOWS:
        import ctypes

        return (
            path.drive.startswith("\\")
            or ctypes.windll.kernel32.GetDriveTypeW(path.anchor) == 4
        )
    return any(
        path.is_relative_to(root)
        for _, _, root in (smb_mounts() if mounts is None else mounts)
    )


def smb_address(value):
    address = urlsplit(value)
    parts = [unquote(part) for part in address.path.strip("/").split("/")]
    if (
        not address.hostname
        or address.username is not None
        or address.password is not None
        or address.port is not None
        or address.query
        or address.fragment
        or any(
            part in {"", ".", ".."} or "/" in part or "\\" in part or "\0" in part
            for part in parts
        )
    ):
        raise ValueError("Ungültiger SMB-Pfad. Format: smb://server/freigabe/ordner")
    return address.hostname, parts


def validate_folder_path(value):
    if value.lower().startswith("smb://"):
        smb_address(value)
    elif "\0" in value or not Path(value).expanduser().is_absolute():
        raise ValueError("Ein absoluter Ordnerpfad oder ein SMB-Pfad ist erforderlich.")


def resolve_folder(value, mounts, *, require_smb):
    if value.lower().startswith("smb://"):
        hostname, parts = smb_address(value)
        share, *subdirectory = parts
        if WINDOWS:
            if any(c in hostname for c in "\\/:") or any(
                c in part for part in parts for c in ':*?"<>|'
            ):
                raise ValueError(
                    "Der SMB-Pfad enthält unter Windows ungültige Zeichen."
                )
            root = Path(f"\\\\{hostname}\\{share}\\").resolve(strict=True)
            folder = root.joinpath(*subdirectory).resolve(strict=True)
            if not folder.is_relative_to(root):
                raise ValueError("Der Ordner liegt außerhalb der SMB-Freigabe.")
            if not folder.is_dir():
                raise NotADirectoryError(folder)
            return folder
        matches = [
            path
            for server, mounted_share, path in mounts
            if server == hostname and mounted_share.casefold() == share.casefold()
        ]
        if len(matches) != 1:
            raise OSError("SMB-Freigabe ist nicht eindeutig eingehängt.")
        root = matches[0].resolve(strict=True)
        folder = root.joinpath(*subdirectory).resolve(strict=True)
        if not folder.is_relative_to(root):
            raise ValueError("Der Ordner liegt außerhalb der SMB-Freigabe.")
    else:
        folder = Path(value).expanduser()
        if not folder.is_absolute():
            raise ValueError("Es ist ein absoluter Ordnerpfad erforderlich.")
        folder = folder.resolve(strict=True)
        if require_smb and not on_network_volume(folder, mounts):
            raise OSError(
                f"Der Ordner liegt nicht auf einer eingehängten SMB-Freigabe: {folder}"
            )
    if not folder.is_dir():
        raise NotADirectoryError(folder)
    return folder
