/* Windows GUI launcher. Installs the locked runtime for the current user. */
#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#include <windows.h>
#include <shellapi.h>
#include <stdio.h>
#include <wchar.h>

#ifndef VOXDROP_RUNTIME
#define VOXDROP_RUNTIME L"win-x64"
#endif

#define PATH_LENGTH 32768

static int launch(const wchar_t *application, wchar_t *command,
                  const wchar_t *directory, DWORD flags, BOOL wait) {
    STARTUPINFOW startup = { .cb = sizeof(startup) };
    PROCESS_INFORMATION process = {0};
    if (!CreateProcessW(application, command, NULL, NULL, FALSE, flags, NULL,
                        directory, &startup, &process)) {
        return 1;
    }
    DWORD status = 0;
    if (wait) {
        WaitForSingleObject(process.hProcess, INFINITE);
        if (!GetExitCodeProcess(process.hProcess, &status)) {
            status = 1;
        }
    }
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    return (int)status;
}

static int error_dialog(const wchar_t *message) {
    MessageBoxW(NULL, message, L"VoxDrop", MB_ICONERROR | MB_OK);
    return 1;
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, PWSTR parameters, int show) {
    (void)instance;
    (void)previous;
    (void)parameters;
    (void)show;
    wchar_t executable[PATH_LENGTH];
    wchar_t root[PATH_LENGTH];
    wchar_t local[PATH_LENGTH];
    wchar_t profile[PATH_LENGTH];
    wchar_t runtime[PATH_LENGTH];
    wchar_t managed_python[PATH_LENGTH];
    wchar_t project[PATH_LENGTH];
    wchar_t python[PATH_LENGTH];
    wchar_t uv[PATH_LENGTH];
    wchar_t ready[PATH_LENGTH];
    wchar_t command[PATH_LENGTH];

    DWORD home_length = GetEnvironmentVariableW(L"LOCALAPPDATA", local, PATH_LENGTH);
    DWORD app_length = GetModuleFileNameW(NULL, executable, PATH_LENGTH);
    if (!app_length || app_length >= PATH_LENGTH - 1024 ||
        !home_length || home_length >= PATH_LENGTH - 1024) {
        return error_dialog(L"VoxDrop konnte seinen Installations- oder Datenordner nicht ermitteln.");
    }

    int argc = 0;
    LPWSTR *argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    BOOL background = argc == 2 && wcscmp(argv[1], L"--background") == 0;
    BOOL diagnose = argc == 2 && wcscmp(argv[1], L"--diagnose") == 0;
    LocalFree(argv);

    wcscpy(root, executable);
    *wcsrchr(root, L'\\') = L'\0';
    swprintf(profile, PATH_LENGTH, L"%ls\\VoxDrop", local);
    swprintf(runtime, PATH_LENGTH, L"%ls\\%ls", profile, VOXDROP_RUNTIME);
    swprintf(managed_python, PATH_LENGTH, L"%ls\\python", profile);
    swprintf(project, PATH_LENGTH, L"%ls\\windows", root);
    swprintf(uv, PATH_LENGTH, L"%ls\\tools\\uv.exe", root);
    swprintf(ready, PATH_LENGTH, L"%ls\\ready", runtime);
    swprintf(python, PATH_LENGTH, L"%ls\\Scripts\\%ls", runtime,
             diagnose ? L"python.exe" : L"pythonw.exe");

    if (!SetEnvironmentVariableW(L"UV_PROJECT_ENVIRONMENT", runtime) ||
        !SetEnvironmentVariableW(L"UV_PYTHON_INSTALL_DIR", managed_python) ||
        !SetEnvironmentVariableW(L"VOXDROP_LAUNCHER", executable)) {
        return error_dialog(L"Die Laufzeitpfade konnten nicht gesetzt werden.");
    }
    CreateDirectoryW(profile, NULL);
    HANDLE mutex = CreateMutexW(NULL, FALSE, L"Local\\VoxDrop.Runtime.Install");
    if (!mutex) {
        return error_dialog(L"Die Installation konnte nicht gesperrt werden.");
    }
    DWORD lock = WaitForSingleObject(mutex, INFINITE);
    if (lock != WAIT_OBJECT_0 && lock != WAIT_ABANDONED) {
        CloseHandle(mutex);
        return error_dialog(L"Die Installation konnte nicht gestartet werden.");
    }
    BOOL installed = GetFileAttributesW(python) != INVALID_FILE_ATTRIBUTES &&
                     GetFileAttributesW(ready) != INVALID_FILE_ATTRIBUTES;
    int status = 0;
    if (!installed && !background) {
        if (swprintf(command, PATH_LENGTH,
                     L"\"%ls\" sync --locked --no-dev --managed-python --python 3.12.13", uv) < 0) {
            status = 1;
        } else {
            status = launch(uv, command, project, CREATE_NEW_CONSOLE, TRUE);
        }
        if (!status) {
            HANDLE marker = CreateFileW(ready, GENERIC_WRITE, 0, NULL,
                                        CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
            installed = marker != INVALID_HANDLE_VALUE;
            if (installed) {
                CloseHandle(marker);
            }
        }
    }
    ReleaseMutex(mutex);
    CloseHandle(mutex);
    if (!installed || status) {
        if (background) {
            return 1;
        }
        return error_dialog(L"Die VoxDrop-Laufzeit konnte nicht eingerichtet werden. "
                            L"Beim ersten Start sind Internet und freier Speicherplatz erforderlich.");
    }

    const wchar_t *script = diagnose ? L"diagnose.py" : L"desktop.py";
    if (swprintf(command, PATH_LENGTH, L"\"%ls\" -BEs -Xutf8 \"%ls\\%ls\"%ls",
                 python, project, script, background ? L" --background" : L"") < 0) {
        return error_dialog(L"Der Installationspfad ist zu lang.");
    }
    status = launch(python, command, root, diagnose ? CREATE_NEW_CONSOLE : 0, FALSE);
    return status ? error_dialog(L"VoxDrop konnte nicht gestartet werden.") : 0;
}
