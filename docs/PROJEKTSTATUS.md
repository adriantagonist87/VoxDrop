# Projektstatus VoxDrop

Stand vom 17. November 2026. Für jede Weiterentwicklung sind zusätzlich die Arbeitsregeln und die Entwicklungsanleitung zu lesen. [Arbeitsregeln](../AGENTS.md) · [Entwicklung](ENTWICKLUNG.md) · [Windows-Übergabeauftrag](UEBERGABE_WINDOWS.md)

## Gemeinsamer Stand

| Gegenstand | Stand |
| --- | --- |
| Öffentliches Repository | `adriantagonist87/VoxDrop`, Hauptbranch `main` |
| Freigegebener Stand | `v1.3.0`, macOS-Build 22, Windows-x64-ZIP |
| Getesteter Implementierungscommit | `2936f8992a977d6db11dd3d442ebf4d447a748d7` |
| Gemeinsame Entwicklungsbasis | `main` mit App-Code, Arbeitsregeln und gemeinsamer Dokumentation |
| Betriebsmodell | Eigenständige lokale macOS- und Windows-Apps, auch in verschiedenen Netzwerken |
| Referenzbibliothek | aTrain `ea8a7057857220b4299c0ba0b2aaf6def2f35b87` |

Die ursprüngliche Mac-Historie von v1.2.0 mit Code-Commit `19c8084193ec96717d878e6912334b3c28759c93` ist lokal unter `archive/macos-local-before-shared-github` erhalten. Die aktive Mac-Arbeitskopie verwendet `origin` zum gemeinsamen GitHub-Repository. Ihr `main` verfolgt `origin/main`. Neue Mac- und Windows-Arbeiten beginnen auf dieser gemeinsamen öffentlichen Historie. Plattformübergreifende Übergaben verwenden die vollständigen öffentlichen GitHub-SHAs. [Release 1.3.0](https://github.com/adriantagonist87/VoxDrop/releases/tag/v1.3.0)

### Git-Prüfung zu Beginn der Dokumentationsaufgabe

- Die ursprüngliche Arbeitskopie und der öffentliche GitHub-Checkout waren sauber. Es gab keine ungesicherten versionierten Änderungen.
- `origin/main` wurde von GitHub abgerufen und entsprach dem öffentlichen Release-Commit. Laufzeitdaten und Pakete unter `.runtime/` sind gemäß `.gitignore` lokale Artefakte.
- Die Dokumentation wurde zunächst im Übergabebranch erstellt und anschließend zusammen mit der Mac-Finalisierung auf `main` übernommen.

## Zuletzt geprüfter Code je Betriebssystem

| Umgebung | Letzter geprüfter öffentlicher Commit | Prüfung und Ergebnis |
| --- | --- | --- |
| macOS, Apple Silicon | `2936f8992a977d6db11dd3d442ebf4d447a748d7` | v1.3.0 Build 22 auf diesem Mac installiert. Frischer Quell-Checkout, vollständig neuer Bootstrap, leeres Testprofil, echte Downloads von Qwen/Aligner/pyannote und Whisper erfolgreich. Beide ASR-Modelle auf Metal mit Sprecherzuordnung geprüft, Qwen zusätzlich mit drei DOVER-Lap-Durchgängen. Alle 58 automatisierten Tests unter macOS 27.2, arm64, Python 3.12.13 bestanden. |
| Windows 11 mit NVIDIA | **UNGEPRÜFT unter Windows**, noch kein bestätigter Test-Commit | Der Nutzer meldete eine funktionsgestörte Windows-Ausgabe. Der v1.3.0-Launcher wurde auf dem Mac als PE32+ x86-64 gebaut. ZIP und Lockfile wurden auf dem Mac geprüft. Ein nativer Windows-/CUDA-End-to-End-Test ist offen. |
| Linux | **UNGEPRÜFT**, Zielport offen | Gemeinsame Qt-Oberfläche vorhanden. Backends, Plattformadapter, Einrichtung und Pakete sind auf macOS/Windows ausgerichtet. |

Der macOS-Testbefehl war `MPLCONFIGDIR=<lokales Testverzeichnis> .runtime/aTrain/.venv/bin/python -m unittest discover -s tests`. Das Ergebnis war `Ran 58 tests … OK`. Dieser Testlauf prüft teilweise gemockte Abläufe. Die zusätzlichen GUI- und Modellprüfungen haben den jeweils unten angegebenen Umfang. Die Ersteinrichtung wurde in einem leeren Profil auf dem vorhandenen Mac geprüft. Die Prüfung auf einem physisch zweiten Mac ist offen.

### Mac-Ersteinrichtung und Modellablage

- Die Distribution installiert einen gemeinsamen Ordner `VoxDrop` mit `VoxDrop.app` und dem später angelegten Ordner `Modelle`. Heruntergeladene Gewichte und Cache lagen im Test vollständig unter `Modelle`, zusammen rund 9,6 GiB für den geprüften Modellbestand.
- Die signierte App blieb nach beiden Downloads und Transkriptionen verifizierbar. Python, Qt, aTrain, CTranslate2/Metal und MLX ließen sich bei ausgeblendetem Build-Verzeichnis aus dem installierten Bundle laden.
- Ein Update innerhalb des bestehenden Ordners erhielt die frisch geladenen Modellgewichte mit bestätigten Prüfsummen. Die produktive Installation übernahm ihre bisherigen Modelle aus dem Benutzerprofil und aktualisierte den Anmeldestart auf den App-Launcher. Konfiguration und Verlauf wurden erhalten.
- MAC-01 wurde durch den neuen Installer `macos/install.py` und die vereinfachte Installationshilfe behoben. Ein Regressionstest prüft die Wiederherstellung von App und Modellen bei fehlgeschlagenem Austausch.
- Die App bleibt ad hoc signiert. Der Nutzer hat ein kostenpflichtiges Apple-Developer-Konto ausdrücklich abgelehnt. Die einmalige Freigabe unter „Datenschutz & Sicherheit → Dennoch öffnen“ ist für neue Macs dokumentiert. Die Standard-Gatekeeper-Prüfung weist diesen Build wegen der fehlenden Developer-ID-/Notarisierungsfreigabe zurück.

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
| Anmeldestart | Registrierung auf App-Launcher mit `--background` umgestellt und übernommen. Neuer tatsächlicher Login mit v1.3.0 noch offen. | **UNGEPRÜFT unter Windows**, HKCU-Run-Anbindung implementiert |
| Installationspaket | DMG-Prüfsumme, Signatur und Übereinstimmung zum installierten Build geprüft, ad hoc signiert | Auf dem Mac gebautes ZIP und öffentlicher Download geprüft, unsigniert. Installation **UNGEPRÜFT unter Windows**. |

## Offene Fehler und technische Lücken

| Kennung | Priorität und Befund | Nächste Prüfung |
| --- | --- | --- |
| WIN-01 | Hoch. Windows-Ausgabe laut Nutzer funktionsgestört. Ein früherer Screenshot zeigt beim Modell-Setup von `speaker-detection` einen `httpcore.ConnectError` mit `WinError 10013`. Die Ursache auf dem PC ist offen. | Version und Commit feststellen, tatsächlichen EXE-Start reproduzieren, Modell-Download und Netzwerkzugriff gezielt diagnostizieren. |
| WIN-02 | Hoch. GPU-Betrieb der Windows-Backends und Speicherbedarf auf RTX 5060 mit 8 GB sind **UNGEPRÜFT unter Windows**. | NVIDIA-/CUDA-Diagnose, beide ASR-Modelle, Forced Aligner, pyannote und DOVER-Lap einzeln ausführen. |
| WIN-03 | Mittel. Frühere Windows-Oberfläche war schlecht lesbar. Die harmonisierte QML-Ausgabe besitzt bisher Mac-Prüfungen. | Aktuelles ZIP bei mehreren DPI-Einstellungen, Fenstergrößen und Spaltenbreiten prüfen. |
| TEST-01 | Mittel. Die gesamte Testsuite hat Plattformannahmen. `test_app_upgrade.py` importiert das macOS-Modul mit `fcntl`. `test_local_job.py` erwartet explizit `metal`. Einige Tests erzeugen Symlinks. | Gemeinsame und OS-spezifische Prüfungen unter Windows ausführbar machen. Fehlende Symlink-Berechtigung als eigenen Testbefund festhalten. |
| BUILD-01 | Mittel. `scripts/build-windows.sh` ist ein macOS-Cross-Build mit `plutil`, `rsync`, `zip` und Zig. Ein nativer Windows-Paketbuild ist offen. | Erst vorhandenes Paket und Quellstart diagnostizieren. Bei Bedarf nativen Build als eigenen Arbeitsschritt umsetzen und dokumentieren. |

Der Fehlerbericht WIN-01 stammt aus einem früheren Testbuild. Die genaue Version des Screenshots ist offen. Für v1.3.0 bleibt die native Windows-Reproduktion ausstehend.

## Fortführung auf dem Windows-PC

Der konkrete Auftrag einschließlich Reproduktion, Diagnosebefehlen, Abnahmekriterien und Rückgabeformat steht in der Windows-Übergabe. Nach jedem tatsächlichen Plattformtest sind hier vollständiger Code-Commit, Windows-Version, GPU/Treiber, Testumfang und Ergebnis nachzutragen. [Windows-Übergabeauftrag](UEBERGABE_WINDOWS.md)
