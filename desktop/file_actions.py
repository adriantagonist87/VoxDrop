"""Native file actions for the desktop interface."""

from pathlib import Path


def reveal_in_explorer(path):
    """Select one file through the Windows Shell, without command-line parsing.

    Call from a worker: resolving a Shell item on a network share can block.
    """
    path = Path(path).absolute()
    if not path.is_file():
        raise FileNotFoundError(
            "Die TXT-Datei ist nicht mehr am gespeicherten Ausgabeort vorhanden."
        )

    import ctypes
    from ctypes import wintypes

    shell = ctypes.WinDLL("shell32")
    ole = ctypes.WinDLL("ole32")
    shell.SHParseDisplayName.argtypes = [
        wintypes.LPCWSTR, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p),
        wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
    ]
    shell.SHParseDisplayName.restype = ctypes.c_long
    shell.SHOpenFolderAndSelectItems.argtypes = [
        ctypes.c_void_p, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p), wintypes.DWORD,
    ]
    shell.SHOpenFolderAndSelectItems.restype = ctypes.c_long
    ole.CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    ole.CoInitializeEx.restype = ctypes.c_long
    ole.CoUninitialize.argtypes = []
    ole.CoUninitialize.restype = None
    ole.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    ole.CoTaskMemFree.restype = None

    def check(result):
        if result < 0:
            raise OSError(
                "Die Datei konnte im Windows-Explorer nicht markiert werden "
                f"(HRESULT 0x{result & 0xffffffff:08X})."
            )

    check(ole.CoInitializeEx(None, 2))  # COINIT_APARTMENTTHREADED
    item = ctypes.c_void_p()
    try:
        check(shell.SHParseDisplayName(str(path), None, ctypes.byref(item), 0, None))
        if not item.value:
            raise OSError("Windows konnte den gespeicherten Dateipfad nicht auflösen.")
        # With cidl=0, the absolute PIDL identifies the item in its parent folder.
        check(shell.SHOpenFolderAndSelectItems(item, 0, None, 0))
    finally:
        if item.value:
            ole.CoTaskMemFree(item)
        ole.CoUninitialize()
