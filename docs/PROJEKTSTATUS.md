# Projektstatus VoxDrop

Stand vom 17. November 2026. Für jede Weiterentwicklung sind zusätzlich die Arbeitsregeln und die Entwicklungsanleitung zu lesen. [Arbeitsregeln](../AGENTS.md) · [Entwicklung](ENTWICKLUNG.md) · [Windows-Übergabeauftrag](UEBERGABE_WINDOWS.md)

## Gemeinsamer Stand

| Gegenstand | Stand |
| --- | --- |
| Öffentliches Repository | `adriantagonist87/VoxDrop`, Hauptbranch `main` |
| Aktuelles Release | `v1.2.0`, macOS-Build 21, Windows-x64-ZIP |
| Öffentlicher Code-Commit | `140eb934ae78ebcbc5b5c608ece7f0487ef81b38` |
| Code-Tree dieses Release | `4879a3f6adae84a92bfb9806fffa2befacba2be4` |
| Dokumentationsübergabe | Branch `docs/codex-macos-windows-handoff`, auf dem öffentlichen Release-Commit aufgebaut |
| Betriebsmodell | Eigenständige lokale macOS- und Windows-Apps, auch in verschiedenen Netzwerken |
| Referenzbibliothek | aTrain `ea8a7057857220b4299c0ba0b2aaf6def2f35b87` |

Die ursprüngliche Mac-Historie mit Code-Commit `19c8084193ec96717d878e6912334b3c28759c93` ist lokal unter `archive/macos-local-before-shared-github` erhalten. Ihr letzter Code-Tree stimmt mit dem öffentlichen Release-Commit überein. Die aktive Mac-Arbeitskopie hat jetzt `origin` zum gemeinsamen GitHub-Repository. Ihr `main` verfolgt `origin/main`, und der Übergabebranch basiert auf derselben öffentlichen Historie wie künftige Windows-Clones. Plattformübergreifende Übergaben verwenden die vollständigen öffentlichen GitHub-SHAs. [Release 1.2.0](https://github.com/adriantagonist87/VoxDrop/releases/tag/v1.2.0)

### Git-Prüfung zu Beginn der Dokumentationsaufgabe

- Die ursprüngliche Arbeitskopie und der öffentliche GitHub-Checkout waren sauber. Es gab keine ungesicherten versionierten Änderungen.
- `origin/main` wurde von GitHub abgerufen und entsprach dem öffentlichen Release-Commit. Laufzeitdaten und Pakete unter `.runtime/` sind gemäß `.gitignore` lokale Artefakte.
- Der Übergabebranch enthält die Dokumentation und den Verweis aus der README. Der funktionale Code und die Release-Dateien haben den Stand von v1.2.0.

## Zuletzt geprüfter Code je Betriebssystem

| Umgebung | Letzter geprüfter öffentlicher Commit | Prüfung und Ergebnis |
| --- | --- | --- |
| macOS, Apple Silicon | `140eb934ae78ebcbc5b5c608ece7f0487ef81b38` | v1.2.0 Build 21 auf diesem Mac installiert. Vorherige Releaseprüfung mit echten Qwen-/Metal-Transkriptionen aus zwei abgelegten Testordnern erfolgreich. Die 51 vorhandenen automatisierten Tests wurden am 17.11.2026 erneut erfolgreich ausgeführt, unter macOS 27.2, arm64, Python 3.12.13. |
| Windows 11 mit NVIDIA | **UNGEPRÜFT unter Windows**, noch kein bestätigter Test-Commit | Der Nutzer meldete eine funktionsgestörte Windows-Ausgabe. Der v1.2.0-Launcher wurde auf dem Mac als PE32+ x86-64 gebaut. ZIP, Lockfile und gemeinsame Quellcodedateien wurden auf dem Mac geprüft. Ein nativer Windows-/CUDA-End-to-End-Test ist offen. |
| Linux | **UNGEPRÜFT**, Zielport offen | Gemeinsame Qt-Oberfläche vorhanden. Backends, Plattformadapter, Einrichtung und Pakete sind auf macOS/Windows ausgerichtet. |

Der macOS-Testbefehl war `MPLCONFIGDIR=<lokales Testverzeichnis> .runtime/aTrain/.venv/bin/python -m unittest discover -s tests`. Das Ergebnis war `Ran 51 tests … OK`. Dieser Testlauf prüft teilweise gemockte Abläufe. Die zusätzlichen GUI- und Modellprüfungen haben den jeweils unten angegebenen Umfang.

## Funktions- und Prüfmatrix

| Funktion | macOS | Windows |
| --- | --- | --- |
| Gemeinsames dunkles Qt-/QML-Fenster, verstellbare Spalten, lange Namen und Details | Cocoa-Tests bei mehreren Fenstergrößen und 125 % Skalierung durchgeführt | **UNGEPRÜFT unter Windows**, früherer Screenshot mit Darstellungsfehlern |
| Qwen3-ASR 1.7B mit Forced Aligner | Metal-End-to-End mit synthetischer Sprachaufnahme geprüft | **UNGEPRÜFT unter Windows**, PyTorch-/CUDA-Pfad implementiert |
| Whisper Large v3 Turbo | Metal-Einzellauf im App-Bundle geprüft | **UNGEPRÜFT unter Windows**, CTranslate2-/CUDA-Pfad implementiert |
| pyannote und DOVER-Lap | Kurze Paketläufe mit Sprecherzuordnung und drei DOVER-Lap-Durchgängen geprüft | **UNGEPRÜFT unter Windows** |
| Mehrere überwachte Ordner, Fehlerhinweis und Refresh | Dienst mit Ausfall eines Testordners und weiterlaufenden anderen Ordnern geprüft. Produktiver konfigurierter SMB-Ordner wurde als verfügbar gemeldet. | **UNGEPRÜFT unter Windows**, einschließlich UNC-/Netzlaufwerkpfaden |
| Rekursive Überwachung mit TXT neben Original | UI-Sperre und zwei verschachtelte Modell-Testläufe geprüft, Originale bytegleich und Hierarchie erhalten | **UNGEPRÜFT unter Windows** |
| Ordner-Drag-and-drop einschließlich Unterordnern | Qt-Cocoa-Drop-Ereignisse und zwei Qwen-Aufträge geprüft. Vorgeschlagene Move-Aktion wurde als Copy bestätigt. Überwachung blieb pausiert. | **UNGEPRÜFT unter Windows**, insbesondere Explorer-Drop und DPI |
| Verlauf, Duplikatschutz, Retry, Neutranskription und Veröffentlichung | Vorhandene automatisierte Tests auf macOS bestanden | **UNGEPRÜFT unter Windows** |
| Lange Stille überspringen und Zeitrückrechnung | Vorhandene automatisierte Tests auf macOS bestanden | **UNGEPRÜFT unter Windows** |
| Dock-Wiederöffnung und farbiges Menüleistensymbol | Cocoa-Probe für verstecktes/minimiertes Fenster und beide Statusfarben erfolgreich. Nutzer meldete anschließend funktionierende App. | Taskleisten-/Infobereichsverhalten **UNGEPRÜFT unter Windows** |
| Anmeldestart | Vorhandene Mac-Registrierung übernommen und als eingerichtet gemeldet. Neuer Login mit v1.2.0 noch offen. | **UNGEPRÜFT unter Windows**, HKCU-Run-Anbindung implementiert |
| Installationspaket | DMG-Prüfsumme, Signatur und Übereinstimmung zum installierten Build geprüft, ad hoc signiert | Auf dem Mac gebautes ZIP und öffentlicher Download geprüft, unsigniert. Installation **UNGEPRÜFT unter Windows**. |

## Offene Fehler und technische Lücken

| Kennung | Priorität und Befund | Nächste Prüfung |
| --- | --- | --- |
| WIN-01 | Hoch. Windows-Ausgabe laut Nutzer funktionsgestört. Ein früherer Screenshot zeigt beim Modell-Setup von `speaker-detection` einen `httpcore.ConnectError` mit `WinError 10013`. Die Ursache auf dem PC ist offen. | Version und Commit feststellen, tatsächlichen EXE-Start reproduzieren, Modell-Download und Netzwerkzugriff gezielt diagnostizieren. |
| WIN-02 | Hoch. GPU-Betrieb der Windows-Backends und Speicherbedarf auf RTX 5060 mit 8 GB sind **UNGEPRÜFT unter Windows**. | NVIDIA-/CUDA-Diagnose, beide ASR-Modelle, Forced Aligner, pyannote und DOVER-Lap einzeln ausführen. |
| WIN-03 | Mittel. Frühere Windows-Oberfläche war schlecht lesbar. Die harmonisierte QML-Ausgabe besitzt bisher Mac-Prüfungen. | Aktuelles ZIP bei mehreren DPI-Einstellungen, Fenstergrößen und Spaltenbreiten prüfen. |
| TEST-01 | Mittel. Die gesamte Testsuite hat Plattformannahmen. `test_app_upgrade.py` importiert das macOS-Modul mit `fcntl`. `test_local_job.py` erwartet explizit `metal`. Einige Tests erzeugen Symlinks. | Gemeinsame und OS-spezifische Prüfungen unter Windows ausführbar machen. Fehlende Symlink-Berechtigung als eigenen Testbefund festhalten. |
| BUILD-01 | Mittel. `scripts/build-windows.sh` ist ein macOS-Cross-Build mit `plutil`, `rsync`, `zip` und Zig. Ein nativer Windows-Paketbuild ist offen. | Erst vorhandenes Paket und Quellstart diagnostizieren. Bei Bedarf nativen Build als eigenen Arbeitsschritt umsetzen und dokumentieren. |
| MAC-01 | Mittel. `scripts/install-app.sh` ist eine historische Installations-/Migrationshilfe mit lokalem Modellbestand. Sie bildet die für v1.2.0 verwendete Aktualisierung mit Dienststopp und Rücksicherung nur teilweise ab. | Warmes Update gesondert prüfen und vereinheitlichen. Bis dahin laufende Aufträge vor dem beauftragten Austausch abschließen und Dienst/GUI geordnet neu starten. |

Der Fehlerbericht WIN-01 stammt aus einem früheren Testbuild. Die genaue Version des Screenshots ist offen. Für v1.2.0 bleibt die native Windows-Reproduktion ausstehend.

## Fortführung auf dem Windows-PC

Der konkrete Auftrag einschließlich Reproduktion, Diagnosebefehlen, Abnahmekriterien und Rückgabeformat steht in der Windows-Übergabe. Nach jedem tatsächlichen Plattformtest sind hier vollständiger Code-Commit, Windows-Version, GPU/Treiber, Testumfang und Ergebnis nachzutragen. [Windows-Übergabeauftrag](UEBERGABE_WINDOWS.md)
