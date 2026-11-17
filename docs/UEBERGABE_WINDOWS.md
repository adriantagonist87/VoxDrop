# Übergabeauftrag für Codex auf dem Windows-PC

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
