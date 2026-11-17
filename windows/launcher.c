/* Windows GUI launcher. Keeps the locked runtime inside the portable app. */
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

static int install_runtime(const wchar_t *uv, wchar_t *command,
                           const wchar_t *directory, const wchar_t *log_path) {
    SECURITY_ATTRIBUTES security = { sizeof(security), NULL, TRUE };
    HANDLE reader = NULL, writer = NULL;
    HANDLE log = CreateFileW(log_path, GENERIC_WRITE, FILE_SHARE_READ, NULL,
                             CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (log == INVALID_HANDLE_VALUE || !CreatePipe(&reader, &writer, &security, 0)) {
        if (log != INVALID_HANDLE_VALUE) CloseHandle(log);
        return 1;
    }
    SetHandleInformation(reader, HANDLE_FLAG_INHERIT, 0);
    HANDLE input = CreateFileW(L"NUL", GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
                               &security, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    BOOL console = AllocConsole();
    if (console) {
        SetConsoleOutputCP(CP_UTF8);
        SetConsoleTitleW(L"VoxDrop – Einrichtung");
        const wchar_t *notice = L"VoxDrop wird eingerichtet. Windows kann eine Netzwerkfreigabe anzeigen.\n"
                                L"Bitte diese Freigabe selbst bestätigen und die Einrichtung abwarten.\n\n";
        DWORD written;
        WriteConsoleW(GetStdHandle(STD_OUTPUT_HANDLE), notice, (DWORD)wcslen(notice), &written, NULL);
    }
    STARTUPINFOW startup = { .cb = sizeof(startup), .dwFlags = STARTF_USESTDHANDLES,
                             .hStdInput = input, .hStdOutput = writer, .hStdError = writer };
    PROCESS_INFORMATION process = {0};
    BOOL created = input != INVALID_HANDLE_VALUE &&
        CreateProcessW(uv, command, NULL, NULL, TRUE, CREATE_NO_WINDOW, NULL,
                        directory, &startup, &process);
    DWORD process_error = created ? 0 : GetLastError();
    CloseHandle(writer);
    if (input != INVALID_HANDLE_VALUE) CloseHandle(input);
    DWORD status = 1;
    if (created) {
        char buffer[8192];
        DWORD count, written;
        while (ReadFile(reader, buffer, sizeof(buffer), &count, NULL) && count) {
            WriteFile(log, buffer, count, &written, NULL);
            if (console) WriteFile(GetStdHandle(STD_OUTPUT_HANDLE), buffer, count, &written, NULL);
        }
        WaitForSingleObject(process.hProcess, INFINITE);
        if (!GetExitCodeProcess(process.hProcess, &status)) status = 1;
        CloseHandle(process.hThread);
        CloseHandle(process.hProcess);
    } else {
        char details[80];
        DWORD written;
        int length = snprintf(details, sizeof(details), "CreateProcessW error: %lu\n", process_error);
        WriteFile(log, details, (DWORD)length, &written, NULL);
    }
    CloseHandle(reader);
    CloseHandle(log);
    if (console) FreeConsole();
    return (int)status;
}

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
    wchar_t cache[PATH_LENGTH];
    wchar_t setup_log[PATH_LENGTH];
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
    swprintf(profile, PATH_LENGTH, L"%ls\\Laufzeit", root);
    swprintf(runtime, PATH_LENGTH, L"%ls\\%ls", profile, VOXDROP_RUNTIME);
    swprintf(managed_python, PATH_LENGTH, L"%ls\\python", profile);
    swprintf(cache, PATH_LENGTH, L"%ls\\cache", profile);
    swprintf(setup_log, PATH_LENGTH, L"%ls\\setup.log", profile);
    swprintf(project, PATH_LENGTH, L"%ls\\windows", root);
    swprintf(uv, PATH_LENGTH, L"%ls\\tools\\uv.exe", root);
    swprintf(ready, PATH_LENGTH, L"%ls\\ready", runtime);
    swprintf(python, PATH_LENGTH, L"%ls\\Scripts\\%ls", runtime,
             diagnose ? L"python.exe" : L"pythonw.exe");

    if (!SetEnvironmentVariableW(L"UV_PROJECT_ENVIRONMENT", runtime) ||
        !SetEnvironmentVariableW(L"UV_PYTHON_INSTALL_DIR", managed_python) ||
        !SetEnvironmentVariableW(L"UV_CACHE_DIR", cache) ||
        !SetEnvironmentVariableW(L"VOXDROP_LAUNCHER", executable)) {
        return error_dialog(L"Die Laufzeitpfade konnten nicht gesetzt werden.");
    }
    if (!CreateDirectoryW(profile, NULL) && GetLastError() != ERROR_ALREADY_EXISTS) {
        return error_dialog(L"Der VoxDrop-Programmordner ist nicht beschreibbar. "
                            L"Entpacke die gesamte App in einen beschreibbaren lokalen Ordner. "
                            L"Laufzeit und Modelle werden dort gespeichert.");
    }
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
    BOOL cancelled = FALSE;
    if (!installed && !background) {
        if (swprintf(command, PATH_LENGTH,
                     L"\"%ls\" sync --locked --no-dev --managed-python --python 3.12.13", uv) < 0) {
            status = 1;
        } else {
            do {
                swprintf(command, PATH_LENGTH,
                         L"\"%ls\" sync --locked --no-dev --managed-python --python 3.12.13", uv);
                status = install_runtime(uv, command, project, setup_log);
                if (!status) break;
                int retry = MessageBoxW(NULL,
                    L"Die Einrichtung konnte den Download noch nicht abschließen.\n\n"
                    L"Falls Windows eine Firewall- oder Netzwerkfreigabe anzeigt, bestätige sie dort selbst. "
                    L"Wähle danach Wiederholen. Die bisherigen Downloads bleiben erhalten.\n\n"
                    L"Prüfe außerdem Internet und freien Speicherplatz. "
                    L"Details stehen im Programmordner unter Laufzeit\\setup.log.",
                    L"VoxDrop – Auf Netzwerkfreigabe warten", MB_RETRYCANCEL | MB_ICONINFORMATION);
                if (retry != IDRETRY) {
                    cancelled = TRUE;
                    break;
                }
            } while (TRUE);
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
    if (cancelled) return 1;
    if (!installed || status) {
        if (background) {
            return 1;
        }
        return error_dialog(L"Die VoxDrop-Laufzeit konnte nicht eingerichtet werden. "
                            L"Beim ersten Start sind Internet und freier Speicherplatz erforderlich.");
    }

    const wchar_t *script = diagnose ? L"windows\\diagnose.py" : L"Desktop\\desktop.py";
    if (swprintf(command, PATH_LENGTH, L"\"%ls\" -BEs -Xutf8 \"%ls\\%ls\"%ls",
                 python, root, script, background ? L" --background" : L"") < 0) {
        return error_dialog(L"Der Installationspfad ist zu lang.");
    }
    status = launch(python, command, root, diagnose ? CREATE_NEW_CONSOLE : 0, FALSE);
    return status ? error_dialog(L"VoxDrop konnte nicht gestartet werden.") : 0;
}
