# Übergabeauftrag für Codex auf dem Windows-PC

## Aktuell: Preview 6

Aktuell installierter App-Code `97cbfb81ed3b91b927f51db9d412adb6536387c9`, [Preview 6](https://github.com/adriantagonist87/VoxDrop/releases/tag/v1.3.2-windows-preview.6), SHA-256 `944ebeb82e89115bd148ba6099f73193a7b4735ce34126bd538d308074d53484`. Historische Detailangaben importierter Ergebnisse zeigen Modell/Sprecher nicht als neu ermittelt. 109 Tests (102 bestanden, sieben Skips), dazu abschließende sieben Qt-Regressionen bestanden. Alle 32 Engine-Dateien sind bytegleich mit dem darunter beschriebenen realen EXE-/CUDA-Prüfstand von Preview 5. Erneutes GitHub-Update mit Null-Aktiv-Guard und vollständiger Profil-/Codesicherung durchgeführt; Queue und Überwachung wieder fortgesetzt. Mac-Gegenprüfung weiter erforderlich.

## Funktionsentwicklung und native Engineprüfung: Preview 5

App-Code `94e333153db90dc57c917575a8ba39040716a170`, [GitHub-Preview 5](https://github.com/adriantagonist87/VoxDrop/releases/tag/v1.3.2-windows-preview.5), SHA-256 `c6ebc9d660e4ea9e2b9356bcc08023b28f73179f03f5d50b107f36dcf0c04d6c`. Vollständige bedienbare Warteschlange, OS-Standardöffner für TXT, Ergebnis-/Inhaltserkennung und Windows-Schreibschutzprüfung implementiert und produktiv installiert. [Detaillierte Übergabe](WARTESCHLANGE_UND_DATEISCHUTZ.md). 108 Tests (101 bestanden, sieben Skips); echtes EXE-/CUDA-Paket einschließlich Abbruch, Wiederverwendung, Neutranskription und Wiederanlauf bestanden. Bisherige 241 Aufträge erhalten; native Integrität/Fremdschlüssel und bestehende TXT bestätigt. Vorübergehende Updatepause beendet, produktive Überwachung aktiv.

Für den Mac zusätzlich `queue_control.py` und `media_history.py` im Paket prüfen, SQLite-Migration/Queue-Reihenfolge, persistente Abbruchanforderung/Unix-Prozessgruppe, QML-Liste/Drag-and-drop bei Mindestgröße, OS-TXT-Öffner und `onTextChanged` gegenprüfen. Windows prüft offene Schreibzugriffe nativ; der Mac behält bisherige Stabilitäts-/Versionsprüfung und braucht eine eigene Gegenprüfung für laufende Aufnahmen. Gemeinsamen Code weiter nicht ungeprüft nach main integrieren. Die folgenden Abschnitte dokumentieren frühere Prüfstände.

## Aktuelle Sitzung vom 18.11.2026

Neuinstallation und Betriebsprüfungen einschließlich Neustart/Standby sind durchgeführt, die App ist produktiv eingerichtet; verbleibende ungeprüfte Fälle stehen unten. Aktueller [GitHub-Vorabdownload Preview 4](https://github.com/adriantagonist87/VoxDrop/releases/tag/v1.3.2-windows-preview.4), App-Code `f35bff9f8f1222d176b987382d3214dfbd9148c1`, SHA-256 `1be623b71f02177e46f402b43a53cf4232bc5e8bae513b7263c1c12553ba241a`. Vollständige Bereinigung und leere Preview-2-Einrichtung beider Modelle bestanden, anschließend geprüfte GitHub-Updates. Acht getrennte Sprachfälle, lokale/UNC-Dateiabläufe und 48,9-minütige normale OPUS-Überwachung mit drei DOVER-Durchgängen bestanden. Suite: 94 Fälle, 87 bestanden, sieben Skips. Ergebnisse und noch offene Schritte stehen im [laufenden Bericht](WINDOWS_ABNAHME_2026-11-18.md); nachfolgende Nachtberichte sind historische Prüfstände.

Sleep/Resume und echter Neustart/Anmeldestart inzwischen bestanden: Windows-S3-Ereignisse mit Folgeauftrag sowie neuer Boot um 10:00:33,5 Uhr MEZ mit automatisch gestartetem GUI-/Supervisor-/Dienstbaum und neuem synthetischem Auftrag/TXT/Originalhash. Der einmalige Beobachter startete die App niemals selbst; seine Registrierung und lokalen Helfer sind entfernt. Produktiver Endzustand aktiv, 335 vorhandene Dateien vor Aktivierung hashgleich, zehn eigene Testdateien privat archiviert und Prüfordner entfernt. Der erste Aufräumversuch stoppte am leeren Ordner mit Sharing-Fehler 32, anschließend kontrolliert fortgesetzt; keine fremden Prozesse beendet. Reguläre Wiederöffnung derselben Instanz und Maximierung nach Neustart geprüft. UIA-SetValue änderte anschließend nur die Textdarstellung, nicht den durch `textEdited` gepflegten Controller-Entwurf; der falsch gespeicherte alte Prüfpfad wurde unabhängig erkannt, über die validierte Konfigurationsschnittstelle korrigiert und ausschließlich die GUI neu geladen. Dieses zusätzliche GUI-Speichern nicht als bestanden ausweisen; Details im Bericht.

Physischer Explorer-Drop bleibt wegen fensterübergreifender Drag-Grenze der Bedienhilfe ungeprüft; interner rekursiver Drop-Pfad separat bestanden. Physische Taskleisten-/Infobereichsklicks, systemweiter DPI-Wechsel, tatsächlicher SMB-Serverausfall und längere Echtzeitserien bleiben ungeprüft. Diese Grenzen sowie die Mac-Gegenprüfung verhindern eine pauschale vollständige Freigabe aller Fälle.

Deutsch und Englisch jeweils getrennt prüfen; Mischsprachigkeit ist laut Nutzer kein Abnahmekriterium. WIN-05 technisch offen lassen. Gemeinsamen Code erst nach Mac-Gegenprüfung integrieren; insbesondere Whisper/Metal-Entladung, Netzwerk-Warteanzeige, OPUS-Erkennung und Mac-Fensterverhalten prüfen. Bisherigen Mac-Prüfstand `df207f79aa812f70d090e4306443436d51d48952` bewahren. Keine vollständige Abnahme behaupten.

## Nachtrag: Modellphasen zur VRAM-Begrenzung

Der ausdrückliche Nutzerhinweis wurde im Code geprüft: Qwen/Aligner/anschließende Sprecherpipeline bereits getrennt; Whisper blieb dagegen bis nach der Sprecherzuordnung geladen. Whisper wird jetzt vor Eintritt in die Sprecherphase geschlossen und freigegeben. Neue Regressionen reproduzieren die alte Überlappung; 91 Fälle (84 erfolgreich, sieben Skips) bestanden. Native Paket-Gegenmessung auf `dbfcf833ef80617929101e321decac3219e76291` bestanden: vor Sprecherladen 4055 → 1943 MiB GPU-Gesamtbelegung, 2112 MiB weniger bei gleicher Desktop-Baseline. Echte Qwen-/Whisper-/DOVER-CUDA-Läufe und erneuter EXE-Wiederanlauf bestanden; Qwen gab ASR/Aligner vor Sprecherladen bis zur Desktop-Baseline frei. Dies bleibt eine Vorprüfung; vollständige GitHub-Neuinstallation und Produktivabnahme finden wie beauftragt nach Rückkehr des Nutzers statt. Auf dem Mac insbesondere Whisper-Entladung/Metal und Sprecherphase gegenprüfen.

## Nächste Sitzung: verbindliche Endabnahme

Nach Rückkehr des Nutzers die ausdrücklich beauftragte vollständige Deinstallation und Bereinigung durchführen, frisch direkt von GitHub installieren und sämtliche Funktionen über die normale Oberfläche im echten Arbeitsablauf prüfen. **Noch nicht durchgeführt; kein Abschluss allein anhand der Nachtprüfungen.** Konkreter Ablauf und vollständige Prüfliste: [Neuinstallations- und Produktivabnahme](WINDOWS_NEUINSTALLATION_ABNAHME.md). Vor der Bereinigung das passende GitHub-Asset mit Code-SHA und Prüfsumme festlegen; ältere stabile Assets enthalten die neuen Fixes nicht. Originalmedien und produktive Ergebnisse schützen, appbezogene Bestände einzeln zuordnen und Speicherfreigabe nachweisen. Sicherheitsdialoge und Anmeldung bedient der anwesende Nutzer. Nach bestandener Abnahme bleibt die neue Installation produktiv eingerichtet.

## Abschlussstatus und nächster Mac-Lauf

Abschluss der Nachtprüfung am 18.11.2026: **Final geprüfter Paket-Code `bfd4e8ade80c2973cb77541571fa99a374977589`**. 88 Regressionen mit sieben Skips bestanden. EXE-Qwen-Abbruchtest: null verwaiste Inferenzprozesse, temporäres dekodiertes Audio im Auftragsordner anschließend entfernt, automatische Wiederaufnahme bis `done`, TXT und unveränderter Originalhash bestätigt. Der 1803,7-s-EXE-Dauertest auf `2889268f52c9a69a42a3c4df38a0f029323ac9e8` bestand mit 21 Whisper- und einem Qwen-Auftrag sowie erwarteten Fehler-/Kollisionsfällen. Registry-Adapter, normaler EXE-Start mit gespeicherter Pause/Überwachung, 100.000 Verlaufseinträge und 300 QML-/CLI-Aktualisierungen geprüft. Die genauen Reproduktionen, korrigierten Testtreiberfehler und Messwerte stehen im Projektstatus. Keine Schutzregeln oder produktiven Autostarteinträge verändert. Echter Neustart/Anmeldung, Sleep/Resume und wochenlange Echtzeit bleiben **UNGEPRÜFT**; konkrete Neustartanleitung steht in der Entwicklung.

**Früherer geprüfter Abschluss vor der Nachtprüfung:** `8b80572b1fc8196f310a89b82b526fa2112098a3` auf [fix/windows-native-validation](https://github.com/adriantagonist87/VoxDrop/tree/fix/windows-native-validation), [Draft-PR #1](https://github.com/adriantagonist87/VoxDrop/pull/1). Das finale native Testpaket öffnet über EXE die GUI mit „Modelle installiert“ und Modellspeicher neben der EXE. 76 Tests bestanden, sieben explizite Skips. Die tatsächlichen Modell-/Datei-/UNC-Messungen bei `436616ce527d4bbae5ad9922a9f175a39882da09` sowie der Langlauf bei `284004ea5792cfee4c813cad5cb76df06a40487a` bleiben mit diesen SHAs dokumentiert; danach wurden ausschließlich Netzwerkmeldungen präzisiert.

Behoben sind Windows-Testannahmen, der native Vollbild-Minimierungsfehler, fehlender nativer Buildweg sowie die große Modell-/Laufzeitablage außerhalb neuer App-Ordner. WinError 10013 wurde konkret reproduziert; Freigaben erteilte der Nutzer selbst. Warte-/Retry-/Abbruchlogik und konkrete Protokolle ersetzen einen sofortigen Setup-Abbruch. Eine Meldung behauptet keine offene Firewall-Anfrage, wenn keine sichtbar ist.

Für Codex auf dem Mac:

1. `git fetch origin`, PR-Branch prüfen; gemeinsame Codeänderungen bleiben bis zur Gegenprüfung im PR. Den bisherigen Mac-Prüfstand `df207f79aa812f70d090e4306443436d51d48952` bewahren.
2. Vollständige Suite einschließlich `test_desktop_window.py` nativ auf Cocoa ausführen. Bewusste Normalgröße, Maximierung, Vollbild, Minimierung, Dock-/Menüleisten- und Einzelinstanz-Wiederöffnung gegenprüfen.
3. Mac-Modellablage neben der signierten App und isolierte Profile prüfen; die neue Windows-Paketerkennung darf das Mac-Verhalten nicht ändern. QML-Netzwerk-Warteanzeige und Abbruch prüfen, ohne Sicherheitsregeln zu verändern.
4. Die neue persistente Retry-Tabelle, Scanner-Wiederöffnung, leere Arbeitsordnerbereinigung und Paketaufnahme von `runtime_logs.py` prüfen. Mac-Startpfad und manuelle Mac-Wiederaufnahme erhalten; Windows-Prozessgruppen sind plattformspezifisch.
5. WIN-05 eingrenzen: gemischtsprachiger synthetischer Dialog mit und ohne Stilleüberspringen, Roh-ASR und Aligner-Ergebnis vergleichen. Die realen Langlaufwerte ersetzen keine vollständige Inhaltsabnahme.
6. Anschließend gemeinsame Integration/Release entscheiden. Bestehende Release-Dateien wurden nicht überschrieben.

Offen auf Windows: echter Neustart/Anmeldestart, Sleep/Resume und mehrstündige/wochenlange Echtzeitserien, physischer Explorer-Drop, physische Taskleisten-/Infobereichsklicks, systemweiter DPI-Wechsel, tatsächlicher SMB-Serverausfall, native erfolgreiche Retry-Bedienung nach künstlicher Installationsverweigerung und gesicherte Migration/Bereinigung älterer externer Bestände. Jeweils **UNGEPRÜFT**. Die neuen großen Downloads liegen vollständig im App-Ordner; alte Bestände wurden nicht heimlich gelöscht. Alle gemeinsamen Änderungen dieses PRs sind **UNGEPRÜFT unter macOS**.

Weiterer Nachtbefund: Nach hartem Worker-Abbruch konnten dekodierte temporäre Audiodaten außerhalb des Auftragsordners zurückbleiben. Windows-Prozesse bekommen deshalb TMPDIR/TEMP/TMP innerhalb des bereinigbaren `transcription-*`-Ordners. Regression mit echtem Kindprozess und `os._exit` reproduziert den alten Fehler. Finale Qwen-Abbruch-/Wiederanlaufprüfung auf `bfd4e8ade80c2973cb77541571fa99a374977589` bestanden; der abgeschlossene 30-Minuten-Test verwendete ausdrücklich Code `2889268f52c9a69a42a3c4df38a0f029323ac9e8`.

## Fortschritt im Windows-Arbeitsbranch

`fix/windows-native-validation` beginnt bei `4162030e17dc0b6d9a95a0356e6cd0dfac2a16c9`. Release v1.3.1 wurde über die EXE reproduziert; vollständige Modell-Setups sowie echte Qwen-/Aligner-/pyannote-/DOVER-Lap-CUDA-Verarbeitung auf RTX 5060 bestanden. Messwerte, historische Fehlversuche und Grenzen stehen im neuen Windows-Arbeitsblock des Projektstatus.

Der Nutzer hat Modelle im App-Ordner präzisiert. Neue Pakete halten Modelle/Download-Cache in `Modelle` und Python/CUDA/uv-Cache in `Laufzeit` neben der EXE. Bestehende ältere externe Bestände sind bisher erhalten. Ein nativer Windows-Builder mit geprüften Vendorquellen wurde ergänzt. Die Paketabnahme und das finale SHA-Statusupdate folgen nach den Tests.

Eine tatsächliche Firewall-Freigabe wurde beim neuen Laufzeitpfad vom Nutzer verlangt und von ihm selbst erteilt. Danach bestand der normale EXE-Start. Neuer Launcher: Setup-Log im App-Ordner und wartender Wiederholen-/Abbrechen-Dialog. Neuer Modelldownload: WinError-10013-Wartezustand, automatische echte Download-Wiederholung und Abbruchknopf. Regressionen prüfen simulierte Verweigerung, spätere Freigabe und Abbruch; die neue native Interaktion muss zusätzlich am finalen Paket geprüft werden. Gemeinsame QML-/Controller-Änderung auf dem Mac gegenprüfen.

Zusätzlich wurde WinError 10013 mit dem neuen Python-Pfad beim tatsächlichen Modelldownload reproduziert. Der Nutzer erteilte die Python-Freigabe gesondert; danach wurden die Modelle im App-Ordner bereitgestellt. Keine Firewall wurde automatisch geändert. WIN-04: echte QML-Vollbild-Minimierung verlor unter Windows den gespeicherten Modus über ein kurzzeitiges `Windowed`-Ereignis. Neue Regression scheitert am alten Code und besteht nach der Korrektur; native Gesamtsuite zuletzt 76 Tests, sieben explizite Skips. Mac-Gegenprüfung für `window_state.py` einschließlich bewusst gewähltem Normalmodus erforderlich. Eine freigegebene 48,9-minütige Besprechung wurde mit Qwen/Aligner, CUDA und Stilleüberspringen erfolgreich in 320,172 s verarbeitet; Originalschutz bestätigt, keine persönlichen Inhalte veröffentlicht.

[Draft-PR #1](https://github.com/adriantagonist87/VoxDrop/pull/1) enthält die gemeinsame Windows-Arbeit. Echte lokale Dateiabläufe mit fünf GPU-Aufträgen und ein freigegebener UNC-End-to-End-Test sind inzwischen bestanden; genaue Grenzen stehen im Projektstatus. Ein künstlicher Installer-Fehlertest wurde wegen Verwechslung mit einer echten Firewall-Anfrage beendet. Meldungen unterscheiden deshalb ausdrücklich verweigerten Netzwerkzugriff von einer tatsächlich sichtbaren Freigabeanfrage. Keine weiteren Firewall-Anfragen werden für abgeschlossene Downloads behauptet. Die native erfolgreiche Wiederholen-Bedienung dieses synthetischen Fehlertests bleibt **UNGEPRÜFT**.

Nächste Prüfungen: neues Paket wirklich über EXE installieren, Modellpfade und Speicherfreigabe bestätigen, echte Dateiabläufe/GUI mit isoliertem Profil, längere Aufnahme mit Stille. Der Nutzer hat einen lokalen Besprechungsordner für Tests freigegeben. Nur Testkopien verwenden; keine persönlichen Dateinamen, Inhalte oder Logs veröffentlichen. Den offenen Textverlust bei Qwen mit Stilleüberspringen im gemischten synthetischen Dialog getrennt untersuchen.

Mac-Gegenprüfung: gemeinsame Tests einschließlich separierter Symlinkfälle, bisherige Modellablage und isolierte Profile, QML/Fensteraktivierung sowie Qwen mit langen Pausen. Bisherige Mac-Prüfstände bewahren. Alle gemeinsamen Änderungen dieses Branches sind bis dahin **UNGEPRÜFT unter macOS**. Code bleibt im Pull Request; nur der separate Dokumentationsstatus wird nach dem Remote-Abgleich auf `main` übergeben.

## Auftrag und Ausgangspunkt

Untersuche und behebe die vom Nutzer gemeldete funktionsgestörte Windows-Ausgabe von VoxDrop. Verwende zuerst das aktuelle Windows-Paket v1.3.1 und halte den Fehler mit Umgebung und Logs reproduzierbar fest. Arbeite anschließend auf einem eigenen Fix-Branch von `main` weiter und aktualisiere die gemeinsame Dokumentation.

Lies vor Beginn `AGENTS.md`, `docs/PROJEKTSTATUS.md` und `docs/ENTWICKLUNG.md`. Dieser Auftrag gilt für eine eigenständige Windows-App mit lokaler KI auf dem Büro-PC, auch in einem anderen Netzwerk als der Mac mini.

| Ausgangspunkt | Wert |
| --- | --- |
| Repository | `https://github.com/adriantagonist87/VoxDrop.git` |
| Gemeinsame Basis | Aktueller `origin/main`, Tag `v1.3.1`. Letzter getesteter Code-SHA gemäß Projektstatus. |
| Windows-Asset | `VoxDrop-1.3.1-Windows-x64.zip` plus gleichnamige `.sha256` |
| Zielgerät | Windows 11 x64, NVIDIA RTX 5060 mit 8 GB oder kompatibel leistungsfähiger |
| Bisherige Windows-Prüfung | **UNGEPRÜFT unter Windows**. EXE-Cross-Build, Archivprüfung und Lockfile-Prüfung auf dem Mac durchgeführt. |
| Bekannte Nutzermeldung | Frühere Ausgabe mit Darstellungsfehlern und Modell-Setup-Abbruch bei `speaker-detection`, `httpcore.ConnectError`, `WinError 10013`. Genaue Testversion offen. |

## 1. Stand erfassen

1. Im vorhandenen Clone zuerst `git status --short --branch`, `git remote -v` und `git rev-parse HEAD` erfassen. Lokale Änderungen erhalten.
2. `git fetch origin` ausführen, `main` auschecken und mit `git merge --ff-only origin/main` aktualisieren. Einen Fix-Branch wie `fix/windows-start-diagnose` darauf anlegen.
3. Windows-Version/Build, PowerShell-Version, GPU, Treiber, Benutzer-/Installationspfad und tatsächlich verwendetes Paket erfassen. Öffentlich geteilte Pfade anonymisieren.

```powershell
git status --short --branch
git rev-parse HEAD
$PSVersionTable.PSVersion
Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber
nvidia-smi
```

Der geladene Treiber und ein angezeigter CUDA-Wert in `nvidia-smi` sind erste Diagnosedaten. Die tatsächlichen Torch- und CTranslate2-Operationen werden gesondert geprüft.

## 2. Das ausgelieferte Paket reproduzieren

1. Das ZIP und seine Prüfsumme aus dem öffentlichen Release laden. SHA-256 prüfen und beide Namen dokumentieren. Das ZIP vollständig in einen eigenen lokalen Testordner entpacken.
2. Die EXE normal ausführen und den sichtbaren Ablauf festhalten. Prüfe getrennt Laufzeitinstallation, Öffnen des Fensters und Modelleinrichtung.
3. Ein neues Profil verwenden. Folgender PowerShell-Ablauf nimmt an, dass das entpackte Verzeichnis `VoxDrop` im aktuellen Verzeichnis liegt. Auch diese Befehle sind bis zur Ausführung **UNGEPRÜFT unter Windows**.

```powershell
$app = (Resolve-Path .\VoxDrop).Path
$lab = Join-Path (Get-Location).Path 'voxdrop-testprofil'
New-Item -ItemType Directory -Force $lab | Out-Null
$env:VOXDROP_PROFILE = $lab
Start-Process -FilePath (Join-Path $app 'VoxDrop.exe') -Wait
Start-Process -FilePath (Join-Path $app 'VoxDrop.exe') -ArgumentList '--diagnose' -Wait
```

`VOXDROP_PROFILE` isoliert Desktop-Konfiguration und Dienstzustand. Der C-Launcher installiert seine Python-/CUDA-Laufzeit weiterhin unter `%LOCALAPPDATA%\VoxDrop`. Das ist bei Prüfung eines frischen Setups zu berücksichtigen.

Die Python-Laufzeit für genau dieses Paket wird aus dem Lockfile-Hash bestimmt. Nach einem erfolgreichen Launcher-Setup lassen sich verdeckte Startfehler über die Konsole erfassen.

```powershell
$lock = Join-Path $app 'windows\uv.lock'
$hash = (Get-FileHash $lock -Algorithm SHA256).Hash.Substring(0, 12).ToLowerInvariant()
$runtime = Join-Path $env:LOCALAPPDATA "VoxDrop\runtime-$hash"
$py = Join-Path $runtime 'Scripts\python.exe'
$engine = Join-Path $app 'Engine\watch_service.py'
$state = Join-Path $lab 'service'
$data = Join-Path $lab 'data'
& $py -BEs -Xutf8 (Join-Path $app 'Desktop\desktop.py') 2>&1 |
    Tee-Object (Join-Path $lab 'gui-start.log')
```

Für den direkten Start vorher die Test-GUI regulär beenden, damit die Einzelinstanz-Weiterleitung den neuen Konsolenlauf übernehmen kann. Einen erkannten Fehler zuerst mit vollständiger lokaler Ausgabe untersuchen. In GitHub nur bereinigte Auszüge übernehmen.

## 3. WinError 10013 und Modell-Setup untersuchen

- Stelle fest, welcher Prozess, Zielhost und Einrichtungsschritt fehlschlagen. Der Screenshot belegt den historischen Fehler bei `speaker-detection`. Er legt die Ursache auf diesem PC noch offen.
- Vergleiche den Aufruf aus der EXE, aus dem zugehörigen `python.exe` und aus einer interaktiven PowerShell. Prüfe benutzerspezifische Proxy-/Netzwerkeinstellungen und vorhandene Ereignisse des Endpoint-Schutzes anhand des konkreten Fehlers.
- Erfasse die vollständige Fehlermeldung lokal. Prüfe den betroffenen Modell-Download gezielt statt einer allgemeinen Änderung von Schutzfunktionen.
- Führe den tatsächlichen Modell-Setup-Befehl für das isolierte Profil aus. Er lädt und verifiziert die Gewichte.

Als erste Verbindungsmessung kann `Test-NetConnection huggingface.co -Port 443` dienen. Bei weitergeleiteten Modelldownloads ist anschließend der im Fehler tatsächlich genannte Host zu untersuchen. Passwörter, Tokens und Proxy-Zugangsdaten bleiben aus dem öffentlichen Bericht heraus.

```powershell
& $py -BEs -Xutf8 $engine --state-dir $state --model-data $data setup-models --model qwen3-asr-1.7b
& $py -BEs -Xutf8 $engine --state-dir $state --model-data $data setup-models --model large-v3-turbo
& $py -BEs -Xutf8 $engine --state-dir $state --model-data $data status --limit 10
```

Beide Setup-Befehle schließen standardmäßig `speaker-detection` ein. `--no-speakers` dient zum gezielten Isolieren des ASR-Downloads. Das Ergebnis des vollständigen Setups gehört ebenfalls in den Prüfbericht.

## 4. Lokale Modelle und Oberfläche prüfen

1. `windows/diagnose.py` beziehungsweise die EXE-Diagnose ausführen. Die Diagnose enthält einen echten kleinen Torch-CUDA-Aufruf, das Abfragen der CTranslate2-Compute-Typen und einen Dienststatus.
2. Mit einer synthetischen kurzen Sprachaufnahme zuerst Qwen ohne Sprecher, dann mit pyannote und mit DOVER-Lap prüfen. Whisper entsprechend separat ausführen. GPU-Aktivität, Laufzeit, RAM und VRAM beobachten.
3. Den Quellstart aus `docs/ENTWICKLUNG.md` bei Bedarf für die Fehlerbehebung einrichten. Das ausgelieferte Paket bleibt als reproduzierbare Ausgangsbasis erhalten.
4. Die bestehende Testsuite starten. Plattformbedingte Test-Importe und Annahmen aus TEST-01 korrigieren oder gezielt plattformspezifisch kennzeichnen. Gemeinsame Regressionstests ausführbar halten.
5. Das aktuelle dunkle GUI mit 100 %, 125 % und 150 % Anzeige-Skalierung, Mindestfenstergröße, beiden Spaltentrennern, langen Unicode-Dateinamen und Auftragsdetails prüfen. Die zuletzt eingestellten Spaltenbreiten müssen nach Neustart wiederkehren.
6. Taskleisten-Wiederöffnung, ausgeblendetes/minimiertes Fenster, Infobereichssymbol und den beauftragten Anmeldestart auf Windows tatsächlich prüfen. v1.3.1 enthält eine gemeinsame Korrektur in `desktop/window_state.py`: erneutes Öffnen muss Maximierung und Vollbild erhalten; nach Minimieren muss der vorherige Modus zurückkehren. Unter Cocoa geprüft, **UNGEPRÜFT unter Windows**. Dabei auch eine bewusst gewählte normale Benutzergröße überprüfen.

## 5. Dateiverhalten abnehmen

Verwende synthetische Testmedien in eigenen lokalen Verzeichnissen. Nutze freigegebene SMB-Testordner anschließend, sofern auf diesem PC eingerichtet und beauftragt.

| Fall | Erwartetes Ergebnis |
| --- | --- |
| Zwei überwachte Ordner, einer fällt aus | Andere erreichbare Ordner werden weiter bearbeitet. Fehler erscheint beim Pfad und zentral, Refresh kann neu prüfen. |
| Reguläre Überwachung mit Zielunterordner | Verifiziertes TXT und zugehöriges Medium werden gemeinsam im gewählten Unterordner abgelegt. |
| „Unterordner mit einbeziehen“ aktiv | Zielunterordner ist gesperrt. Verschachtelte Aufnahmen erhalten ihr TXT am eigenen Originalpfad. Originale und Hierarchie bleiben erhalten. |
| Ein oder mehrere Ordner aus Explorer fallen lassen | Alle enthaltenen regulären Aufnahmen samt Unterordnern einmalig eingereiht. TXT neben jedem Original, auch bei gesetzter Archivoption und pausierter Überwachung. |
| Drop-Aktion und Reihenfolge | Explorer bestätigt den Drop ohne Quellverschiebung. Aktive/wartefähige Aufträge werden konsistent behandelt. |
| Eine neue Datei nach abgeschlossenem Drop hinzufügen | Die neue Datei kommt durch diesen einmaligen Drop allein noch nicht in die Warteschlange. |
| Vorhandene TXT, gleiche Datei erneut, Unterbrechung | Bestehende Ausgabe geschützt, persistenter Status und kontrollierter Retry. Duplikate werden erkannt. |
| Neutranskription aus dem Verlauf | Eigene Ergebnisdatei mit aktuellen Einstellungen, Original bleibt erhalten. |
| SMB/UNC, Unicode und lange Pfade | Erfolg oder konkrete verständliche Pfadfehlermeldung, konsistenter Auftragsstatus. |

## Abschluss und Rückgabe an den Mac

- Pushe den beauftragten Windows-Fix auf einen eigenen Branch und liefere Branch sowie vollständige Commit-SHAs zurück.
- Aktualisiere `docs/PROJEKTSTATUS.md` mit dem tatsächlich getesteten Code-SHA, Windows-Version, GPU/Treiber, Testfällen und Ergebnissen. Kennzeichne noch offene Funktionen weiter mit **UNGEPRÜFT unter Windows**.
- Halte Ursache und Korrektur von WIN-01 getrennt von weiteren Befunden fest. Ergänze Regressionstests und dokumentiere notwendige Abhängigkeits- oder Buildänderungen in `docs/ENTWICKLUNG.md`.
- Gib die auf dem Mac nachzuprüfenden gemeinsamen Codewege an. Der Mac-Codex liest diese Dokumentation nach `git fetch` bei der nächsten Aufgabe.
- Ein erfolgreicher Windows-Abschluss umfasst den tatsächlichen EXE-Start, die lokale Transkription beider Modelle auf CUDA, Sprecherzuordnung, die wesentlichen Dateiabläufe und die GUI-Prüfungen. Verbleibende Punkte werden einzeln ausgewiesen.

## Rückgabe vom Windows-PC am 17.11.2026

Die Arbeit liegt auf [fix/windows-native-validation](https://github.com/adriantagonist87/VoxDrop/tree/fix/windows-native-validation), [Draft-PR #1](https://github.com/adriantagonist87/VoxDrop/pull/1). Final geprüfter Code: `8b80572b1fc8196f310a89b82b526fa2112098a3`. Der [separate Übergabestatus auf main](WINDOWS_STATUS_2026-11-17.md) enthält vollständige SHAs, bestätigte Windows-Ergebnisse, offene Probleme und die nächsten Mac-Prüfungen. Der aktuelle Commit integriert ausschließlich Dokumentation; gemeinsame Codeänderungen bleiben bis zur Mac-Gegenprüfung im PR.
