# Entwicklung auf macOS und Windows

Aktuell installiert: [Windows Preview 10](https://github.com/adriantagonist87/VoxDrop/releases/tag/v1.3.2-windows-preview.10), App-Code `4e565d426167b55a900a2c35d449ae0f29a98493`, ZIP-SHA-256 `4bcdc831057c93227530f73a08b553c4a725a78962945097dc3dd91cb0bd6e0d`. [Icon-/Layoutübergabe](APP_ICON_UND_LAYOUT.md). Kanonischer PNG-Master `macos/VoxDropLogo.png`, Windows-ICO `assets/VoxDrop.ico` und README-Vorschau `docs/images/voxdrop-icon.png`. Beide Windows-Builder verwenden das aktuelle ICO aus dem Checkout; der native Builder übernimmt kein altes Referenz-Icon mehr. Mac-Icongenerator zeichnet die bereits gestaltete Vorlage ohne zusätzliche Kachel. QML-Header vollständig entfernt; Statuswellen im Controller unverändert. 15 Qt-Fälle und native finale Paket-/Icon-/SQLite-Prüfung bestanden. Mac-Swift/ICNS/Dock nativ nachprüfen.

Vorangegangener installierter Stand: [Windows Preview 9](https://github.com/adriantagonist87/VoxDrop/releases/tag/v1.3.2-windows-preview.9), App-Code `c434d5c4921873d387cefc8cdc55f23f201e61de`, ZIP-SHA-256 `7dd6e52dadff40a73f8ce9b79c09609f2d2cd21ed3a6917d338af10937422da4`. Queue-Reihenfolge auch bei Suchfilter bedienbar. `move-queue-relative JOB_ID first|up|down|last` bestimmt die vollständige aktuelle Reihenfolge innerhalb einer SQLite-Schreibtransaktion. `move-queue JOB_ID ANCHOR_ID --after` fügt unmittelbar hinter dem Zieleintrag ein; ohne Flag weiterhin davor, Anker 0 bedeutet Ende. QML verwendet globale Positionen für Grenzen und konkrete Zielanker für gefiltertes Drag-and-drop. Keine Migration, neue Abhängigkeit oder ASR-/Exportänderung. 135 Windows-Fälle (128 bestanden, sieben Skips); native Paket-/QML-/SQLite-Prüfung in 8,584 s bestanden. [Details und Mac-Gegenprüfung](SUCHE_UND_DROP_KONFLIKTE.md).

Vorangegangener installierter Stand: [Windows Preview 8](https://github.com/adriantagonist87/VoxDrop/releases/tag/v1.3.2-windows-preview.8), App-Code `d40b00526494155979d19d6b0b67fcf1853d618f`. [Suche, Drop-Konflikte und Explorer-Auswahl](SUCHE_UND_DROP_KONFLIKTE.md). Neue Desktopmodule `file_actions.py`, `transcript_search.py` und QML-Komponenten `SearchToggle.qml`, `DropConflictDialog.qml` werden durch die rekursive Desktop-Paketaufnahme mitgeliefert. `status --search` und optionale tokengebundene `--content-results/--content-token`; `prepare-drop CONFIG`, `resolve-drop TOKEN queue|front|retranscribe|immediate|ignore`. Additive Tabellen `drop_batches`, `preemptions`, `immediate_jobs` und Dateiversionsindizes; lokale Datenbank/Originale erhalten. Volltextcache erst auf ausdrücklichen Start, eigener abbrechbarer Prozess im vorhandenen OS-Prozessadapter. Bestehende Queuepause wird durch Sofort-Auswahl nicht global aufgehoben. Modelle, Lockfiles und ASR-Pipeline unverändert. Native Mac-Gegenprüfung erforderlich.

Vorangegangener installierter Stand: [Windows Preview 7](https://github.com/adriantagonist87/VoxDrop/releases/tag/v1.3.2-windows-preview.7), App-Code `f4f5287679652579a74ec244255f5b7872fbe265`. `status --filter all|errors|done` filtert den Verlauf vor `--limit` und liefert globale `history_counts`; laufende/wartefähige normale Aufträge gehören weiter in die Queue. Controller-Refresh berücksichtigt Filterwechsel während einer laufenden Abfrage. `layout.ini` speichert `queueCompact` (Standard true); QML bietet zusätzlich einzelne Zeilen zum Aufklappen und ein Aktionsmenü. Keine Datenbankmigration oder neue Abhängigkeit. ASR-/Exportcode unverändert. [Prüf-/Updatebericht](WARTESCHLANGE_UND_DATEISCHUTZ.md). Mac-Gegenprüfung für neue QML-Layouts, Zähler/Filter und Ansichtsspeicherung erforderlich.

Vorangegangener Windows-Funktionsstand: [Preview 6](https://github.com/adriantagonist87/VoxDrop/releases/tag/v1.3.2-windows-preview.6), App-Code `97cbfb81ed3b91b927f51db9d412adb6536387c9`; native vollständige Engine-Abnahme auf bytegleichem Preview-5-Stand `94e333153db90dc57c917575a8ba39040716a170`. [Warteschlange, Transkriptöffnung und Dateierkennung](WARTESCHLANGE_UND_DATEISCHUTZ.md). Neue Module `queue_control.py` und `media_history.py` gehören in alle Engine-Paketlisten. SQLite wird additiv um Queuezustand, Reihenfolge, Abbruchanforderungen und Ergebnisbeziehungen erweitert; lokale Datenbank/Arbeitskopien und vorhandene Historie erhalten.

Zusätzliche Dienst-CLI-Aktionen: `move-queue JOB_ID BEFORE_ID` (0 bedeutet Ende), `queue-pause on|off`, `cancel-job JOB_ID`, `cancel-queue`. `status` liefert `queue` vollständig und unabhängig vom begrenzten terminalen Verlauf sowie `queue_paused` und `cancel_requested` am aktuellen Auftrag. Testoberfläche niemals mit produktiven Abbruchaktionen prüfen. Produktivupdates nach Null-Aktiv-Guard und vollständiger verifizierter Profil-/Codesicherung durchführen; Modelle/Laufzeit unverändert lassen. Echte QML-Interaktion und native Paketprüfung stehen im Funktionsbericht. Gemeinsame Änderungen unter macOS ungeprüft.

### Vorherige Neuinstallationsabnahme

Die Windows-Neuinstallationsabnahme vom 18.11.2026 verwendet aktuell den [Preview-4-Download](https://github.com/adriantagonist87/VoxDrop/releases/tag/v1.3.2-windows-preview.4). Interne Paketversion 1.3.1, App-Code `f35bff9f8f1222d176b987382d3214dfbd9148c1`; ZIP-SHA-256 `1be623b71f02177e46f402b43a53cf4232bc5e8bae513b7263c1c12553ba241a`. Vollständige leere Einrichtung von Preview 2 und anschließende reguläre GitHub-Updates auf Preview 3/4 mit Profilsicherung und erhaltenen Modellen unterscheiden. [Laufender Bericht und genaue Prüfstände](WINDOWS_ABNAHME_2026-11-18.md). Keine gemeinsame Integration vor Mac-Gegenprüfung.

`scripts/check-windows-login.py PRIVATE_CONFIG.json` ist ein einmaliger Beobachter für die echte Windows-Anmeldung. Er startet die App nicht selbst, verlangt einen neuen Boot gegenüber `prepared_boot_time`, prüft genau einen Hintergrund-GUI-/Supervisor-/Dienstprozess des erwarteten Pakets und legt erst danach eine synthetische Aufnahme im isolierten Prüfordner ab. Die private Konfiguration enthält `app`, `profile`, `incoming`, `fixture`, `report`, `prepared_boot_time`, `code_commit` und den exakten `observer_run_value`. Ein eigener HKCU-Run-Wert `VoxDropAcceptanceObserver` startet den Beobachter; nach neuem Boot entfernt er nur diesen Wert und nur bei übereinstimmendem Befehl. Der produktive VoxDrop-Anmeldestart bleibt erhalten. Das Skript und seine Registrierung allein belegen noch keinen bestandenen Neustart.

Für den temporären Run-Wert einen kurzen lokalen Bootstrap verwenden: Windows dokumentiert höchstens 260 Zeichen pro [Run-Befehlszeile](https://learn.microsoft.com/en-us/windows/win32/setupapi/run-and-runonce-registry-keys). Der ursprünglich vorbereitete lange Arbeitsordneraufruf hatte 298 Zeichen und wurde vor dem echten Neustart durch einen 151-Zeichen-Aufruf ersetzt. Der Beobachter verweigert inzwischen längere Befehle. Ein nativer Aufruf des tatsächlichen kurzen Bootstrap im selben Boot bestätigt: keine App gestartet, keine Produktivänderung, keine falsche Anmeldung bestanden und Registrierung erhalten. Private Pfade/Konfiguration/Bootstrap und Ergebnisse nicht veröffentlichen.

Für den Bootnachweis zusätzlich `prepared_windows_boot` aus `Win32_OperatingSystem.LastBootUpTime` speichern; der Beobachter liest denselben nativen Wert verborgen über PowerShell/CIM und vergleicht die UTC-Zeitpunkte. `psutil.boot_time()` bleibt Diagnosewert: dessen berechneter Fließkommawert variierte beim Vorcheck um weniger als eine Mikrosekunde und ist für exakte Gleichheit ungeeignet. Der korrigierte native Negativtest und die anschließende Sicherungsvorprüfung bestanden. Sicherheits- und Windows-Anmeldedialoge werden nicht automatisiert.

Vor jeder Aufgabe gelten die verbindlichen Arbeitsregeln. Der Projektstatus enthält die nachgewiesenen Prüfstände und offenen Fehler. [Arbeitsregeln](../AGENTS.md) · [Projektstatus](PROJEKTSTATUS.md)

## Repository und Zusammenarbeit

Das gemeinsame Repository ist `https://github.com/adriantagonist87/VoxDrop.git`. Für einen neuen Rechner genügt ein normaler Clone.

```sh
git clone https://github.com/adriantagonist87/VoxDrop.git
cd VoxDrop
git fetch origin
git switch main
git status --short --branch
git rev-parse HEAD
```

`main` ist die gemeinsame geprüfte Basis für macOS und Windows. Neue Aufgaben beginnen auf dem aktuellen `origin/main`. Vorhandene Branches werden regulär ausgecheckt. In gemeinsam genutzten Arbeitskopien prüft Codex vor dem Wechsel lokale Änderungen.

```sh
git fetch origin
git switch main
git merge --ff-only origin/main
git switch -c fix/windows-start-diagnose
```

Commits und Statusupdates auf dem Aufgabenbranch machen Änderungen für den anderen Rechner nachvollziehbar. Nach Push folgt die Integration über den üblichen GitHub-Review-/Merge-Ablauf im beauftragten Umfang. Beim nächsten Codex-Lauf wird der Remote-Stand erneut abgeglichen.

Die Mac-Arbeitskopie wurde für diese Zusammenarbeit an die öffentliche Historie angebunden. Ihre frühere lokale Historie war zunächst im lokalen Branch `archive/macos-local-before-shared-github` gesichert. Bei der ausdrücklich beauftragten vollständigen Deinstallation einschließlich alter Arbeitskopien am 17.11.2026 wurde dieser lokale Branch entfernt und das Repository frisch von GitHub geklont. Für neue Arbeiten dienen `origin/main` und die freigegebenen Aufgabenbranches als gemeinsame Basis.

## Architektur und Rolle des Mac mini

Der Nutzer hat das Betriebsmodell am 17.11.2026 bestätigt. VoxDrop läuft als eigenständige macOS-App auf dem Mac mini und als eigenständige Windows-App beispielsweise auf einem Büro-PC in einem anderen Netzwerk. Jede App führt die KI-Verarbeitung auf ihrem eigenen Rechner aus und erreicht lokale Ordner beziehungsweise SMB-Freigaben aus ihrem jeweiligen Netzwerk.

Der Mac mini ist gleichzeitig Entwicklungs-, Test- und Build-Rechner. Die Bezeichnung „Mac als KI-Server“ ist für diesen Stand als lokale KI-Laufzeit einzuordnen. Die implementierte Schnittstelle zwischen Desktop-App und KI ist eine lokale Prozessschnittstelle. GitHub führt den gemeinsamen Quellstand zusammen.

```mermaid
flowchart TD
    M["macOS · Swift-Launcher"] --> Q["Gemeinsame Qt-/QML-Desktop-App"]
    W["Windows · C-Launcher und uv-Laufzeit"] --> Q
    Q --> C["controller.py · lokale CLI-Unterprozesse"]
    C --> S["watch_service.py · Ordnerprüfung und Warteschlange"]
    S <--> D["Lokale SQLite-Historie und Arbeitskopien"]
    S --> T["transcription_worker.py · Prozess pro Aufnahme"]
    T --> V["voxdrop.py · Dekodierung und Transkription"]
    V --> A["Qwen oder Whisper auf dem jeweiligen Rechner"]
    V --> P["pyannote und optional DOVER-Lap"]
    S <--> F["Lokale Medienordner oder SMB-Freigaben"]
```

- `desktop/desktop.py` startet Qt, Fenster und Einzelinstanz-Erkennung. `QLocalServer`/`QLocalSocket` dienen zum Wiederöffnen derselben lokalen Profilinstanz.
- `desktop/window_state.py` aktiviert das vorhandene Fenster und erhält dessen normalen, maximierten oder Vollbildmodus. Für erneutes Anzeigen `setVisible(True)` verwenden; `QWindow.show()` setzt auf Desktop-Systemen den Standardmodus und kann eine vorhandene Maximierung aufheben. Minimierte Fenster kehren in ihren zuletzt sichtbaren Modus zurück.
- `desktop/controller.py` ruft `watch_service.py` per `subprocess` auf. Einstellungen und Status werden als JSON übertragen.
- `watch_service.py` verwaltet Dateiversionen, SQLite-Aufträge, eine serielle Verarbeitung, Fehler, Wiederholungen und die Ergebnisveröffentlichung. Hängende Ordnerprüfungen sind in zeitbegrenzten Unterprozessen isoliert.
- `transcription_worker.py` führt eine Aufnahme im eigenen Prozess aus und misst Spitzenbelegung. Fortschrittsereignisse kommen über Standardausgabe mit dem Präfix `smb-transcription:`.
- `voxdrop.py` verwendet aTrain/PyAV für Audio, Qwen oder Whisper für ASR, optional pyannote und DOVER-Lap für Sprecher. `silence.py` hält die Rückrechnung der Zeitstempel bei ausgelassenen Pausen vor.
- `qwen_backend.py` startet den Qwen-Unterprozess. Auf macOS nutzt er MLX. Unter Windows verzweigt er in `qwen_cuda.py` mit Transformers/PyTorch.
- `smb_paths.py` und `platform_io.py` kapseln Pfadauflösung, Dateioperationen, Sperren und Prozessflags.

Die produktive Funktion kann bei geschlossenem Hauptfenster weiterlaufen. Die GUI liest den lokalen Dienststatus. Für geschlossene oder minimierte Fenster sind die native Wiederöffnung und das Statussymbol plattformspezifisch angebunden.

## Plattformabhängigkeiten

| Bereich | macOS | Windows |
| --- | --- | --- |
| Ziel | Apple Silicon, Bundle-Mindestversion macOS 26.2 | Windows 11 x64, NVIDIA RTX 5060 mit 8 GB oder kompatibel leistungsfähiger |
| App-Einstieg | `macos/Launcher.swift` lädt `libpython3.12.dylib` und ruft `Py_BytesMain` auf. Der native App-Prozess bleibt erhalten. | `windows/launcher.c` setzt Benutzerpfade, richtet per uv die gesperrte Laufzeit ein und startet `pythonw.exe`. `--diagnose` startet `python.exe`. |
| Gemeinsames GUI | PySide6 Essentials/Shiboken6 6.10.2, QML, Basic-Stil, gebündeltes Inter | Dieselben QML-/Controller-Dateien, **UNGEPRÜFT unter Windows** |
| Qwen | MLX-Audio 0.6.5, separate Qwen-Packages, Metal/CPU | Transformers 5.22.0, PyTorch 2.9.1+cu128, CUDA/CPU. ASR und Aligner werden nacheinander geladen. **UNGEPRÜFT unter Windows**. |
| Whisper | CTranslate2 4.9.0 aus `metal/`, Gerät `mps`, FP16 | CTranslate2 4.8.0, CUDA FP16, Torch-DLL-Pfad. **UNGEPRÜFT unter Windows**. |
| Modelle | `qwen-models.json` | `qwen-windows-models.json`, eigener Format-/Dateibestand |
| DOVER-Lap | Separate `.runtime/dover-packages`, NumPy-2-Anpassung im Bootstrap | Cross-Build übernimmt diese Packages und lädt den unbenutzten nativen DER-Import erst bei Bedarf. **UNGEPRÜFT unter Windows**. |
| Anmeldestart | `login_agent.py`, `~/Library/LaunchAgents/local.voxdrop.worker.plist`, App-Launcher mit `--background` für Menüleiste und Dienst | HKCU `Software\Microsoft\Windows\CurrentVersion\Run`, Wert `VoxDrop`, EXE mit `--background`. Registry-Adapter isoliert geprüft; echter Windows-Neustart weiterhin **UNGEPRÜFT**. |
| SMB | Bereits eingehängte Freigabe, Auflösung über `/sbin/mount -t smbfs` | Netzlaufwerk, UNC oder SMB-URL mit Windows-Zugangsdaten. **UNGEPRÜFT unter Windows**. |
| Dateischutz | `fcntl`, `O_NOFOLLOW`, exklusives `renamex_np` | `msvcrt`, Reparse-Point-Prüfung, Windows-Prozessflags und Umbenennung. **UNGEPRÜFT unter Windows**. |
| RAM-Messung | Physischer Footprint über `proc_pid_rusage` | Prozess-RSS über psutil, **UNGEPRÜFT unter Windows**. Die Kennzahl ist plattformabhängig. |
| Pakete | Swift, AppKit/Icon-Werkzeuge, codesign, hdiutil, DMG | Vorhandener Build auf macOS mit Zig, Windows-EXE und portablem ZIP |

Linux ist eine offene Portierungsaufgabe. Die aktuelle Hardwareauswahl und mehrere POSIX-/macOS-Zweige benötigen dafür Anpassung und Zielsystemtests.

## Daten und Konfiguration

Das Desktop-Standardprofil liegt unter `~/Library/Application Support/VoxDrop` beziehungsweise `%LOCALAPPDATA%\VoxDrop`. Unter macOS liegen in einer Ordnerinstallation Modellgewichte und Download-Cache im gemeinsamen Programmordner unter `VoxDrop/Modelle`. Einstellungen, Verlauf und temporäre Medien bleiben im Benutzerprofil. Ein für die GUI gesetztes `VOXDROP_PROFILE` wählt ein isoliertes Profil samt eigenem Modellspeicher. `VOXDROP_MODEL_DATA` kann für einen gezielten Installationstest einen separaten Modellspeicher wählen. CLI-Werkzeuge erhalten die Pfade ausdrücklich über `--state-dir`, `--model-data` oder `--data-dir`.

| Pfad im Profil | Inhalt |
| --- | --- |
| `config.json` | Ordner und Verarbeitungseinstellungen |
| `layout.ini` | Spaltenbreiten und weitere GUI-Einstellungen |
| `data/models/` | Modellgewichte bei Windows und isolierten Profilen |
| `data/huggingface/` | Modell-Cache bei Windows und isolierten Profilen |
| `service/jobs.sqlite3` | Historie und Warteschlange, SQLite mit WAL |
| `service/jobs/<id>/` | Temporäre Medien-/Transkript-Arbeitsdateien |
| `service/service.log` | Dienstdiagnose |
| `service/desktop.log` | Details zu CLI-Fehlern aus dem Controller |

Unter Windows liegen die verwaltete Python-Installation zusätzlich unter `python/` und die vom Lockfile-Hash abhängige virtuelle Umgebung unter `runtime-<hash>/`. Der `ready`-Marker und die Windows-Installationssperre gehören zum Launcher. Der Launcher setzt außerdem `VOXDROP_LAUNCHER` auf seinen EXE-Pfad. Diesen Wert benötigt die GUI zur Einrichtung des Windows-Anmeldestarts.

Die zentrale Konfiguration enthält `folders`, `include_subfolders`, `create_output_subfolder`, `output_subfolder`, `interval_seconds`, `monitoring`, `model`, `hardware`, `language`, `speakers`, `speaker_count`, `dover_lap` und `skip_silence`. Historische `input_dir`/`completed_dir`-Konfigurationen haben einen Kompatibilitätspfad.

Abgelegte Ordner lösen einen einmaligen Scan aus und erzeugen persistente Aufträge mit `folder_drop` in ihren gespeicherten Einstellungen. Die dauerhafte Konfiguration behält ihre bisherigen Ordner. Für die Ablage gilt stets TXT neben Original. Bei rekursiver Überwachung sperrt die GUI den Zielunterordner, und der Dienst erzwingt dieselbe Regel. Versteckte Ordner, Symlinks/Reparse-Points und abweichende Dateisystemgeräte werden beim rekursiven Scan übersprungen.

Modell-Downloads benötigen Internet. Die eigentliche Verarbeitung schaltet Hugging Face in den Offline-Modus. SMB-Verbindungen werden durch das Betriebssystem bereitgestellt. Die Mac-Installation legt Downloads unter `VoxDrop/Modelle/models` und `VoxDrop/Modelle/huggingface` ab. Beim beauftragten Update übernimmt `macos/install.py` die bisherigen Modelle aus dem Benutzerprofil und setzt dort einen Kompatibilitätsverweis auf den neuen Speicher.

## macOS einrichten und starten

Voraussetzungen sind Git, Xcode Command Line Tools einschließlich Swift und ein geeigneter Apple-Silicon-Mac. Alle Befehle werden im Repository-Root ausgeführt.

```sh
sh scripts/bootstrap.sh
sh scripts/build-app.sh
```

Der Bootstrap lädt uv 0.13.7, Python 3.12.13 und den gepinnten aTrain-Commit. Er richtet aTrain, Metal, Qwen, DOVER-Lap und die Qt-Packages getrennt unter `.runtime/` ein. Der Entwicklungsbuild startet für GUI-Tests mit isoliertem Profil.

```sh
trial=$(mktemp -d "${TMPDIR:-/tmp}/voxdrop-dev.XXXXXX")
VOXDROP_PROFILE="$trial" \
  .runtime/package/VoxDrop.app/Contents/MacOS/VoxDrop
```

Beim ersten Test im leeren Profil die gewünschten Modelle über „Modelle herunterladen“ bereitstellen. Die installierte produktive App kann parallel ihr eigenes Profil verwenden.

### macOS-Tests und Diagnose

```sh
mkdir -p .runtime/test-mpl
MPLCONFIGDIR="$PWD/.runtime/test-mpl" \
  .runtime/aTrain/.venv/bin/python -m unittest discover -s tests
git diff --check
sh -n scripts/bootstrap.sh scripts/build-app.sh scripts/build-dmg.sh scripts/build-windows.sh
```

Ein direkter Dienststatus mit Testprofil verwendet den Interpreter aus dem App-Bundle.

```sh
res="$PWD/.runtime/package/VoxDrop.app/Contents/Resources"
"$res/Python/bin/python3.12" -BEs -Xutf8 "$res/Engine/watch_service.py" \
  --state-dir "$trial/service" --model-data "$trial/data" status --limit 10
```

Die `tests/`-Suite testet teilweise mit Mock-Engines. Zusätzlich sind GUI-Ereignisse, Ordnerablage, beide Modellpfade und Ausgabeorte mit synthetischen Sprachaufnahmen durch den normalen App-Einstieg zu prüfen.

Die Fensterregressionen in `tests/test_window_state.py` verwenden echte Qt-Fensterobjekte. Für eine Prüfung ohne sichtbare Fenster kann `QT_QPA_PLATFORM=offscreen` gesetzt werden. Die native Cocoa-Prüfung erfolgt ohne diese Variable in einer angemeldeten macOS-Sitzung. Ein erfolgreicher Offscreen-Test belegt noch kein natives Dock-/Taskleistenverhalten. Bei Änderungen an der Aktivierung zusätzlich das vollständige QML-Fenster über Controller-Signal, Einzelinstanz-Socket und Plattformaktivierung prüfen.

### macOS-Pakete und Installation

```sh
sh scripts/build-app.sh
codesign --verify --deep --strict .runtime/package/VoxDrop.app
sh scripts/build-dmg.sh
cd .runtime/package
shasum -a 256 VoxDrop-1.3.0-macOS-arm64.dmg > VoxDrop-1.3.0-macOS-arm64.dmg.sha256
shasum -a 256 -c VoxDrop-1.3.0-macOS-arm64.dmg.sha256
```

Für andere Versionen die aus `macos/Info.plist` erzeugten Dateinamen verwenden. Das DMG enthält den Programmordner `VoxDrop`, einen Applications-Link und den aTrain-Quellstand. Bei einer Neuinstallation wird der ganze VoxDrop-Ordner nach Programme gezogen. Bei einem manuellen Update wird die App innerhalb des bestehenden VoxDrop-Ordners ersetzt, sodass der Modellspeicher erhalten bleibt. Der zugehörige Qt-/PySide-Quellcode wird als separates Release-Asset bereitgestellt.

Die Distribution ist ad hoc signiert. Der Nutzer hat die Verwendung eines kostenpflichtigen Apple-Developer-Kontos abgelehnt. Auf einem neuen Mac gehört daher die einmalige Bestätigung unter „Systemeinstellungen → Datenschutz & Sicherheit → Dennoch öffnen“ zum Installationsablauf. [Apples Anleitung](https://support.apple.com/de-de/102445)

Bei der ersten macOS-Warnung „Fertig“ wählen und anschließend die App unter „Datenschutz & Sicherheit“ freigeben. „In den Papierkorb“ entfernt die installierte App. Den gesamten Ordner aus der DMG mit dem Finder nach Programme kopieren und die darin enthaltene App öffnen. Ein Start direkt aus der DMG oder aus einem von macOS geschützten Zwischenpfad kann den vorgesehenen beschreibbaren Modellspeicher verfehlen. In der Oberfläche muss bei einer Ordnerinstallation `VoxDrop/Modelle` als Modellspeicher erscheinen.

Für überwachte Ordner unter „Dokumente“, auf dem Schreibtisch oder auf Netzvolumes kann macOS eine zusätzliche Dateizugriffsfreigabe verlangen. Diese im normalen Einrichtungsablauf bestätigen und den Ordner vor dem unbeaufsichtigten Betrieb prüfen. Bei einem Login-Test die App nicht selbst öffnen: erst den tatsächlichen automatischen App-/Dienststart nachweisen, danach eine neue Testaufnahme in einem freigegebenen überwachten Ordner ablegen.

Für eine Abnahme ohne Entwicklerlaufzeit kann die Testsuite auch mit dem Interpreter des installierten Bundles ausgeführt werden. Dabei den separaten DOVER-Paketpfad ausdrücklich ergänzen, wie es die App für ihre Verarbeitung selbst übernimmt:

```sh
res="$HOME/Applications/VoxDrop/VoxDrop.app/Contents/Resources"
MPLCONFIGDIR="${TMPDIR:-/tmp}/voxdrop-test-mpl" \
  "$res/Python/bin/python3.12" -BEs - "$res/DoverPackages" <<'PY'
import sys, unittest
sys.path.append(sys.argv[1])
suite = unittest.defaultTestLoader.discover("tests")
result = unittest.TextTestRunner().run(suite)
raise SystemExit(not result.wasSuccessful())
PY
```

Für ein beauftragtes Update aus der Entwicklungsumgebung dient `sh scripts/install-app.sh`. Das Script ruft den Installer `macos/install.py` auf. Er prüft das Bundle, beendet die eigenen App-/Dienstprozesse geordnet, wartet auf laufende Aufträge, übernimmt Modelle, erhält Konfiguration/Historie und aktualisiert eine vorhandene eigene Anmelderegistrierung. Der Swift-Helfer `macos/UpdateDock.swift` setzt eine vorhandene VoxDrop-Dock-Verknüpfung vom früheren Pfad auf den neuen App-Pfad. Danach lässt sich die ausgegebene App öffnen.

Für einen isolierten Installationstest sind `--applications <Testverzeichnis>` und `--profile <Testprofil>` verfügbar. Zum Entfernen aller Modelle wird der gesamte installierte VoxDrop-Ordner gelöscht. Einstellungen, Verlauf und eine eingerichtete Anmelderegistrierung werden gesondert im Benutzerkonto verwaltet.

Windows-Inferenzprozesse erhalten TMPDIR/TEMP/TMP im lokalen `transcription-*`-Verzeichnis ihres Auftrags. Damit erfasst die Auftragsbereinigung auch Qwen-Numpy-Audiodaten und Bibliotheks-Temporärdateien nach Prozessabbrüchen. Der Test `test_transcription_temp.py` verwendet einen echten kleinen abstürzenden Kindprozess und bestätigt, dass keine dekodierte Audiodatei im sonstigen System-Temp liegen bleibt. Mac-Umgebung unverändert.

## Modellphasen und GPU-Speicher

Die großen Pipelinephasen werden nacheinander ausgeführt: Qwen-ASR → ASR-Gewichte freigeben → Forced Aligner → Qwen-Prozess beenden → Sprecherpipeline; alternativ Whisper → `close()` und Referenzfreigabe/Garbage Collection → Sprecherpipeline. Die drei DOVER-Lap-Durchgänge verwenden dieselbe Sprecherpipeline nacheinander. Der Auftragsprozess endet nach dem Export des Ergebnisses; der Dienst wartet darauf, bevor der nächste Auftrag beginnt. Dadurch bleiben keine Modelle zwischen Aufträgen absichtlich im GPU-Speicher.

`tests/test_model_lifetime.py` prüft Whisper-Entladung vor Eintritt in die Sprecherphase sowie ASR- und Sprecherfehler. Hardwaremessungen müssen an den Phasengrenzen erfolgen und die übrige Desktop-GPU-Belegung berücksichtigen. Cachefreigabe allein ersetzt keine Freigabe der Modellreferenzen. Die echte Neuinstallationsabnahme umfasst beide ASR-Modelle, den Aligner, Sprecherzuordnung/DOVER und VRAM-Rückgang nach Abschluss/Abbruch.

Reproduzierbare VRAM-Phasenmessung mit vorhandenen lokalen Modellen und synthetischer Aufnahme:

```powershell
& $py -BEs -Xutf8 scripts/check-windows-model-memory.py '<App>' '<kuenstliche.wav>' '<neuer Messordner>' --model large-v3-turbo
& $py -BEs -Xutf8 scripts/check-windows-model-memory.py '<App>' '<kuenstliche.wav>' '<anderer neuer Messordner>' --model qwen3-asr-1.7b
```

Der Prüfer misst synchron vor/nach Whisper-Entladung und vor Sprecherladen bzw. nach Qwen-Prozessende, verwendet tatsächliche CUDA-/DOVER-Verarbeitung und prüft die Phasenreihenfolge. Er zeichnet GPU-Gesamtwerte inklusive Desktop auf, keinen isolierten Modellverbrauch und keinen lückenlosen Inferenzspitzenwert. Native Prüfungen auf `dbfcf833ef80617929101e321decac3219e76291` bestanden; Neuinstallation bleibt separat offen.

## Geplante Windows-Endabnahme nach Bereinigung

Für die nächste gemeinsame Sitzung ist die [Neuinstallations- und Produktivabnahme](WINDOWS_NEUINSTALLATION_ABNAHME.md) verbindlich beauftragt: zugeordnete App-/Testbestände samt Modellen, Laufzeiten, Profilen und eigenen Autostarteinträgen bereinigen; Speicherfreigabe belegen; ein passendes SHA-verifiziertes Paket direkt von GitHub vollständig frisch über EXE einrichten; alle Funktionen im tatsächlichen Produktivablauf einschließlich echtem Windows-Neustart prüfen. Keine übernommenen Modelle/Laufzeiten oder lokalen Quellüberlagerungen als saubere Neuinstallation zählen. Aktuell **GEPLANT, NICHT DURCHGEFÜHRT**.

## Windows einrichten und starten

### Windows-Arbeitsbranch: portable Daten und nativer Build

Für den unbeaufsichtigten Windows-Betrieb startet `start` jetzt einen lokalen Supervisor, der `run` nach unerwartetem Ende mit 2 Sekunden bis maximal 5 Minuten Abstand neu startet. `supervisor.lock` verhindert doppelte Supervisoren, `service.lock` weiterhin parallele Verarbeitung. Aktive unterbrochene Windows-Aufträge werden erneut eingereiht; bestehende Resultate und verifizierte Export-Arbeitsstände bleiben geschützt. Temporäre I/O-Fehler verwenden zusätzlich die persistente Tabelle `job_retries` mit 10 Sekunden bis 15 Minuten Backoff. Dauerhafte Modellfehler und Ergebniskollisionen bleiben sichtbar und erfordern eine bewusste Entscheidung.

`service.log` rotiert im laufenden Windows-Supervisor bei rund 4 MiB mit zwei Sicherungen. `bootstrap.log` enthält frühe Startfehler. `runtime_logs.py` ist Bestandteil beider Paketbuilder. Das bisherige Mac-Startverfahren bleibt erhalten. Tests für Windows-Job-Objects verwenden echte eigene Kind-/Enkelprozesse und benötigen keine neuen Systemfreigaben. Ein Ausfalltest ist keine Abnahme eines tatsächlichen Windows-Neustarts.

Reproduzierbare native Ausfallprüfung mit vorhandenen Modellen und einer künstlichen WAV-Datei:

```powershell
& $py -BEs -Xutf8 scripts/check-windows-recovery.py '<App>' '<neues lokales Testverzeichnis>' '<kuenstliche.wav>'
# Qwen einschließlich tatsächlicher dekodierter Audiodatei und Abbruchbereinigung:
& $py -BEs -Xutf8 scripts/check-windows-recovery.py '<App>' '<anderes neues lokales Testverzeichnis>' '<kuenstliche.wav>' qwen3-asr-1.7b
```

Der Prüfer verwendet ein neues isoliertes Profil, beendet ausschließlich dessen Testprozesse und prüft Dienst-Wiederanlauf, Inferenzbereinigung und Auftragswiederaufnahme. Er startet den PC nicht neu und verändert keinen produktiven Anmeldestart. Windows-CRT-Dateisperren können als errno 13 ohne WinError erscheinen; auch dieser I/O-Fehler erhält einen begrenzten Retry, ohne Rechte zu ändern.

Für den längeren Pakettest steht `scripts/check-windows-soak.py` zur Verfügung:

```powershell
& $py -BEs -Xutf8 scripts/check-windows-soak.py '<App>' '<neues lokales Testverzeichnis>' '<kuenstliche-15s.wav>' 1800
```

Der Prüfer startet die echte EXE mit neuem Profil, überwacht zwei eigene Ordner und injiziert Dateisperre, ungültiges Medium, GUI-/Dienst-/Supervisorende, Ordnerausfälle, Pause/Fortsetzen, langsames Kopieren, doppelte Startaufrufe, kurze ungültige Konfiguration und abschließenden Qwen-Modellwechsel. Er verwendet vorhandene Modelle, keine neue Einrichtung. JSON-Berichte bleiben privat, weil sie lokale Pfade enthalten. Parameter unter 1800 Sekunden sind unzulässig, damit alle geplanten Fälle stattfinden. Ein erneuter Start nach beendetem Test-Supervisor prüft den gleichen `--background`-Einstieg wie die Anmeldung, ersetzt keinen Betriebssystem-Neustart.

Nachholen der **UNGEPRÜFTEN echten Windows-Neustartabnahme**, sobald eine passende Nutzersitzung möglich ist:

1. Test-App in ihrem endgültigen beschreibbaren lokalen Ordner belassen; vorhandene Laufzeit/Modelle und eine isolierte synthetische Überwachungsablage verwenden.
2. Anmeldestart bewusst aktivieren und in Windows prüfen, dass VoxDrop als Autostart-App zugelassen ist. Pfad und gespeicherte Überwachungseinstellungen festhalten.
3. Windows tatsächlich neu starten und normal anmelden. VoxDrop dabei nicht manuell öffnen. Sichtbarkeit im Infobereich, genau einen Supervisor/Dienst und die letzte Ordnerprüfung belegen.
4. Erst nach diesem Nachweis eine neue künstliche Aufnahme ablegen; automatische Verarbeitung, TXT neben Original und unveränderten SHA-256 prüfen. Testregistrierung danach gezielt zurücknehmen und vorherige produktive Einstellungen erhalten.

Der bisherige Registry-Test verwendet stattdessen nur einen temporären HKCU-Testschlüssel und verändert keinen produktiven Run-Wert. Die vorbereitete Prüfanleitung richtet auch keinen zukünftigen Startauftrag ein. Finales Paket `bfd4e8ade80c2973cb77541571fa99a374977589`: 88 Regressionen mit sieben expliziten Skips bestanden. Der 1803,7-s-Überwachungstest auf `2889268f52c9a69a42a3c4df38a0f029323ac9e8` bestand mit 22 erfolgreichen CUDA-Aufträgen; der finale Qwen-Abbruchtest bestätigte Prozess- und temporäre Audiobereinigung sowie automatische Fertigstellung.

Im Branch `fix/windows-native-validation` liegen heruntergeladene Modelle und Hugging-Face-Cache bei einer Windows-Paketinstallation unter `VoxDrop/Modelle`. `VoxDrop/Laufzeit` enthält Python, die virtuelle CUDA-Umgebung und den uv-Cache. Der gesamte entpackte Programmordner muss beschreibbar sein. Entfernen dieses Ordners entfernt diese großen Bestände; Konfiguration/Verlauf unter `%LOCALAPPDATA%/VoxDrop` bleiben erhalten. Ein Update ersetzt App-Dateien unter Erhalt von `Modelle` und `Laufzeit`. Ältere Pakete verwendeten externe Verzeichnisse; diese werden nicht stillschweigend gelöscht oder als migriert behauptet.

`VOXDROP_PROFILE` isoliert Konfiguration/Verlauf. Beim neuen Windows-Paket bleiben Modelle trotzdem neben der EXE. `VOXDROP_MODEL_DATA` ist die ausdrückliche Überschreibung für Entwicklerprüfungen. Quellstarts ohne Paketmarker behalten ihren bisherigen Profilspeicher. Der Mac-Speicherpfad bleibt unverändert; Gegenprüfung **UNGEPRÜFT unter macOS**.

Ein nativer Entwicklungsbuild benötigt Python 3.12 und Zig 0.15.2 sowie den unveränderten, geprüften Referenz-Download v1.3.1. Zig stammt aus dem [offiziellen Downloadindex](https://ziglang.org/download/index.json); Windows-x64-ZIP-SHA-256 `3a0ed1e8799a2f8ce2a6e6290a9ff22e6906f8227865911fb7ddedc3cc14cb0c`. Aus dem sauberen, committeten Repository:

```powershell
& $py -BEs -Xutf8 scripts/build-windows.py --zig C:/Tools/zig/zig.exe `
  --base-zip C:/Downloads/VoxDrop-1.3.1-Windows-x64.zip `
  --base-sha256 b6ab4c819d9fe48db52633ab80eccf4829750e1384ae215582e2503c1ba2b897
```

Der Builder benötigt keine Mac-Werkzeuge. Er erhält Vendor-Lizenzen und Quellarchive, normalisiert Textzeilenenden für einen identischen Lockfile-Hash und schreibt `build-info.json` mit vollständigem Code-SHA, aTrain-Pin und Referenzprüfsumme. Ausgabe: `.runtime/package/VoxDrop-<Version>-Windows-x64-<SHA>.zip` samt SHA-256. Keine Veröffentlichung oder Ersetzung stabiler Assets. Native Prüfung und endgültige Ergebnisse stehen im Projektstatus.

Bei einer Windows-Netzwerkfreigabe entscheidet der Nutzer im Systemdialog selbst. Der Launcher wartet nach einem fehlgeschlagenen Setup mit „Wiederholen/Abbrechen“ und protokolliert uv unter `Laufzeit/setup.log`. Nach der Freigabe „Wiederholen“ wählen. Für Modellfehler WinError 10013 wartet die QML-Oberfläche und wiederholt den tatsächlichen Download alle fünf Sekunden, bis er gelingt oder „Warten abbrechen“ gewählt wird. Dieser reale Download ist gleichzeitig die Verbindungsprüfung für den betroffenen Python-Prozess und seine Modellziele; ein curl-Test in einem anderen Prozess wäre dafür kein Ersatz. Bei anderen Fehlern Details im privaten Desktop-/Setup-Log prüfen.

Die Meldung setzt keine offene Firewall-Anfrage voraus: „Einrichtung unterbrochen“ nennt zuerst das Setup-Protokoll; bei Fehler 10013 verweist die Oberfläche ohne sichtbare Freigabeanfrage ebenfalls auf das Protokoll. Bereits erteilte Freigaben müssen nicht pauschal erneut gesetzt werden. Ein Test mit künstlich verweigertem Download ist von einer tatsächlichen Systemanfrage zu unterscheiden.

Die Testsuite kann mit dem Release-Interpreter laufen. Beim Quellcheckout die im Referenzpaket enthaltenen `Engine`- und `DoverPackages`-Verzeichnisse an `sys.path` anhängen, damit die unveränderten Vendor-Abhängigkeiten gefunden werden. `QT_QPA_PLATFORM=offscreen` prüft Qt-Logik; native Fenster zusätzlich ohne diese Variable prüfen. Mac-Migrationstests sind unter Windows explizit übersprungen; Symlinktests melden WinError 1314 als fehlendes Recht, während rekursive und normale Dateiabläufe weiter geprüft werden. Keine Aktivierung von Entwicklermodus oder Änderung von Sicherheitsrichtlinien erforderlich.

`tests/test_desktop_window.py` lädt zusätzlich das vollständige QML-Fenster mit isolierten Einstellungen. Die Vollbild-Minimierungsregression wartet auf native Fensterereignisse; der frühere unmittelbar abgefragte Qt-Zustand allein verfehlte den Windows-Zwischenzustand. Für native Abnahme `QT_QPA_PLATFORM` entfernen; für kontrollierte Skalierung `QT_SCALE_FACTOR=1`, `1.25` oder `1.5` vor dem jeweiligen Prozessstart setzen. Windows behandelt den kurzzeitigen `Windowed`-Zustand beim Minimieren erst nach Abschluss des Ereigniswechsels als bewusste Normalmoduswahl. Den Mac-Ablauf separat gegenprüfen.

Die folgenden ursprünglichen Release-/Quellstartbefehle beschreiben v1.3.1. Die tatsächlich ausgeführten Windows-Prüfungen und die neue portable Ablage stehen oben und im Projektstatus; nicht aufgeführte Varianten bleiben **UNGEPRÜFT unter Windows**.

Die ZIP vollständig entpacken und `VoxDrop.exe` öffnen. Der Launcher führt im Ordner `windows/` folgenden Einrichtungsschritt mit dem mitgelieferten `tools/uv.exe` aus.

```text
uv sync --locked --no-dev --managed-python --python 3.12.13
```

Danach startet er `Desktop/desktop.py` mit der eingerichteten `pythonw.exe`. Voraussetzung ist eine passende Windows-x64-/NVIDIA-Umgebung gemäß `windows/README.md`. Der Diagnoseeinstieg ist `VoxDrop.exe --diagnose`. [Windows-Paket](../windows/README.md) · [Diagnoseauftrag](UEBERGABE_WINDOWS.md)

### Windows-Quellstart in einer isolierten Entwicklungsumgebung

Diese Schritte sind ein aus dem Code abgeleiteter, **UNGEPRÜFTER Windows-Einrichtungsweg**. Benötigt werden Git und uv. PowerShell steht im Repository-Root. Prüfe nach jedem Programmaufruf den Exitcode.

```powershell
$repo = (Get-Location).Path
New-Item -ItemType Directory -Force .runtime | Out-Null
$env:UV_PROJECT_ENVIRONMENT = Join-Path $repo '.runtime\windows-venv'
uv sync --directory windows --locked --no-dev --managed-python --python 3.12.13
if ($LASTEXITCODE -ne 0) { throw 'Windows-Laufzeit konnte nicht eingerichtet werden.' }
$py = Join-Path $env:UV_PROJECT_ENVIRONMENT 'Scripts\python.exe'

git clone https://github.com/aTrainTranscription/aTrain.git .runtime/aTrain
git -C .runtime/aTrain checkout --detach ea8a7057857220b4299c0ba0b2aaf6def2f35b87
uv pip install --python $py --no-deps .runtime/aTrain
if ($LASTEXITCODE -ne 0) { throw 'aTrain konnte nicht installiert werden.' }

$env:VOXDROP_PROFILE = Join-Path $repo '.runtime\dev-profile-windows'
& $py -BEs -Xutf8 desktop/desktop.py
```

Bei vorhandenem aTrain-Checkout dessen Änderungen und Pin prüfen, bevor er weiterverwendet wird. Für DOVER-Lap zusätzlich die im passenden Windows-Release enthaltenen `DoverPackages` nach `.runtime/dover-packages` der Quell-Arbeitskopie übernehmen. Das Paket enthält die Build-Anpassungen aus `scripts/bootstrap.sh` und `scripts/build-windows.sh`. Den Quellstart zunächst mit deaktiviertem DOVER-Lap isolieren, anschließend dessen vollständigen Lauf prüfen.

### Windows-Tests und Logs

```powershell
New-Item -ItemType Directory -Force .runtime/test-mpl | Out-Null
$env:MPLCONFIGDIR = Join-Path $repo '.runtime\test-mpl'
& $py -m unittest discover -s tests
git diff --check
```

Der Gesamtlauf hat bekannte Plattformannahmen unter TEST-01. Importfehler, fehlende Voraussetzungen, übersprungene Tests und echte Funktionsfehler im Ergebnis getrennt erfassen. Gemeinsame Tests lassen sich zur Diagnose dateiweise ausführen.

```powershell
& $py -m unittest discover -s tests -p test_multi_folders.py
& $py -m unittest discover -s tests -p test_watch_service.py
& $py -m unittest discover -s tests -p test_qwen_backend.py
```

Für ein entpacktes Release benutzt der Controller das Profil und die Laufzeit des Launchers. Die vollständige Abfrage dieses Interpreters sowie Befehle für Diagnose und Modell-Setup stehen im Übergabeauftrag.

### Windows-Paket bauen

Der vorhandene reproduzierte Build läuft auf dem Mac nach dem Bootstrap. Benötigt werden ein ausführbares Zig und das offizielle Windows-x64-uv-Archiv zusammen mit seiner `.sha256`-Datei.

```sh
sh scripts/build-windows.sh /pfad/zu/zig /pfad/zu/uv-x86_64-pc-windows-msvc.zip
```

Das Script prüft die uv-Prüfsumme, erstellt Icon-Ressourcen und ein `x86_64-windows-gnu`-GUI-Programm. Es bündelt dieselben Desktop-/Engine-Quellen sowie `windows/uv.lock`, DOVER-Lap und den aTrain-Quellstand im ZIP. Die Paketversion folgt `macos/Info.plist`. Halte `windows/pyproject.toml` und den Eintrag `voxdrop-windows` in `windows/uv.lock` synchron dazu.

Ein nativer Windows-Buildweg ist als BUILD-01 offen. Änderungen am Windows-Code können zunächst über den beschriebenen Quellstart getestet und über den bestehenden Mac-Build paketiert werden. Die Tests auf dem Windows-PC bestimmen die Plattformfreigabe.

BUILD-01 ist auf dem Windows-Arbeitsbranch durch `scripts/build-windows.py` umgesetzt und nativ geprüft. Der vorstehende Mac-Cross-Build bleibt erhalten. Abschluss-Code `8b80572b1fc8196f310a89b82b526fa2112098a3`: 76 Tests, sieben explizite Skips; abschließender Lauf mit `QT_QPA_PLATFORM=offscreen` in 13,143 s. Native Tests wurden zuvor ohne diese Variable ausgeführt. Beispiel für den Quellcheckout mit paketierten Vendor-Abhängigkeiten:

```powershell
$env:MPLCONFIGDIR = Join-Path (Get-Location).Path '.runtime/test-mpl'
& $py -BEs -Xutf8 -c "import sys,unittest; sys.path.append(r'<App>/Engine'); sys.path.append(r'<App>/DoverPackages'); r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover('tests')); raise SystemExit(not r.wasSuccessful())"
```

Zusätzlich wurden echte Dienstaufträge über `enqueue-folders`, `next_job`, `retranscribe`, `retry` und `probe_pending_folders` mit neuen lokalen Testverzeichnissen sowie einer ausdrücklich freigegebenen UNC-Testablage ausgeführt. Modelle sind dabei lokal unter `<App>/Modelle`, Auftragsdatenbanken/Arbeitskopien außerhalb des öffentlichen Repositorys. Die genauen geprüften Fälle und Messwerte stehen im Projektstatus; persönliche Testpfade und Inhalte gehören nicht in öffentliche Befehlsbeispiele.

## Dokumentation und Veröffentlichung

Nach relevanten Änderungen Projektstatus und betroffene Anleitung aktualisieren. Für Plattformtests jeweils den vollständigen getesteten Code-SHA erfassen. Die Lizenzhinweise und erforderlichen Quellcode-Assets bleiben Teil des Releaseumfangs. [Qt-Lizenzhinweise](../desktop/Qt-Lizenzen.md)

Quellcode, gemeinsame Dokumentation und der geprüfte Mac-Build werden auf `main` zusammengeführt. Windows-Prüfstände bleiben nach tatsächlich durchgeführten Tests gekennzeichnet.

### Windows-Übergabe am 18.11.2026

Der [Windows-Übergabestatus](WINDOWS_STATUS_2026-11-17.md) verweist auf PR #1 und den installierten Preview-10-Code `4e565d426167b55a900a2c35d449ae0f29a98493`. Auch im Suchfilter bedienbare Queue-Menü-/Drag-Reihenfolge, schnelle Metadaten-/optionale FTS-Inhaltssuche, Batch-Konfliktentscheidungen und native Explorer-Auswahl ergänzen die bisherigen Queue-/Dateischutz-/Windows-Korrekturen. Modelle/Lockfiles unverändert, neue additive Tabellen für Droppläne, Unterbrechung und begrenzte Sofort-Auswahl. Implementierung, exakte native Prüfstände und Mac-Checkliste stehen im Aufgabenbranch. Icon-Master/ICO/README-Vorschau und Dokumentation auf Main aktualisiert. Funktionaler App-Code noch nicht integriert; vorher auch Swift-ICNS/Dock und headerloses Fenster sowie Cocoa-/Paket-/SQLite-/Suchprozess-/Queuepause-Gegenprüfung ausführen und bisherigen Mac-Prüfstand bewahren.
