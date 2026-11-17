# Projektstatus VoxDrop

Stand vom 17. November 2026. Für jede Weiterentwicklung sind zusätzlich die Arbeitsregeln und die Entwicklungsanleitung zu lesen. [Arbeitsregeln](../AGENTS.md) · [Entwicklung](ENTWICKLUNG.md) · [Windows-Übergabeauftrag](UEBERGABE_WINDOWS.md)

## Gemeinsamer Stand

| Gegenstand | Stand |
| --- | --- |
| Öffentliches Repository | `adriantagonist87/VoxDrop`, Hauptbranch `main` |
| Freigegebener Stand | `v1.3.1`, macOS-Build 23, Windows-x64-ZIP |
| Getesteter Implementierungscommit | `df207f79aa812f70d090e4306443436d51d48952` |
| Gemeinsame Entwicklungsbasis | `main` mit App-Code, Arbeitsregeln und gemeinsamer Dokumentation |
| Betriebsmodell | Eigenständige lokale macOS- und Windows-Apps, auch in verschiedenen Netzwerken |
| Referenzbibliothek | aTrain `ea8a7057857220b4299c0ba0b2aaf6def2f35b87` |

Die ursprüngliche Mac-Historie von v1.2.0 mit Code-Commit `19c8084193ec96717d878e6912334b3c28759c93` war zunächst lokal unter `archive/macos-local-before-shared-github` gesichert. Beim ausdrücklich beauftragten vollständigen Entfernen aller alten VoxDrop-Arbeitskopien am 17.11.2026 wurde auch dieser lokale Sicherungsbranch entfernt. Die aktive Mac-Arbeitskopie wurde anschließend frisch von GitHub geklont. Ihr `main` verfolgt `origin/main`. Neue Mac- und Windows-Arbeiten beginnen auf dieser gemeinsamen öffentlichen Historie. Plattformübergreifende Übergaben verwenden die vollständigen öffentlichen GitHub-SHAs. [Release 1.3.0](https://github.com/adriantagonist87/VoxDrop/releases/tag/v1.3.0)

### Git-Prüfung zu Beginn der Dokumentationsaufgabe

- Die ursprüngliche Arbeitskopie und der öffentliche GitHub-Checkout waren sauber. Es gab keine ungesicherten versionierten Änderungen.
- `origin/main` wurde von GitHub abgerufen und entsprach dem öffentlichen Release-Commit. Laufzeitdaten und Pakete unter `.runtime/` sind gemäß `.gitignore` lokale Artefakte.
- Die Dokumentation wurde zunächst im Übergabebranch erstellt und anschließend zusammen mit der Mac-Finalisierung auf `main` übernommen.

## Zuletzt geprüfter Code je Betriebssystem

| Umgebung | Letzter geprüfter öffentlicher Commit | Prüfung und Ergebnis |
| --- | --- | --- |
| macOS, Apple Silicon | `df207f79aa812f70d090e4306443436d51d48952` | v1.3.1 Build 23: alle 64 Tests einschließlich sechs neuer Fensterregressionen unter macOS 27.2, arm64, Python 3.12.13 bestanden. Zusätzlich vollständiges QML-Fenster auf Cocoa mit Öffnungssignalen, Einzelinstanz-Socket, Maximierung, Vollbild, Minimierung und Schließen geprüft. Auf diesem Mac installiert; Desktop-Dateien bytegleich zum Prüfstand, Einstellungen und Modellbestand erhalten. Die vollständige Modell-/Neustartabnahme erfolgte zuvor mit v1.3.0 bei `270e3af7ce96bfce8c5daf49236da2fa4d1d05be`; deren KI-Backend ist unverändert. |
| Windows 11 mit NVIDIA | **UNGEPRÜFT unter Windows**, noch kein bestätigter Test-Commit | Der Nutzer meldete eine funktionsgestörte Windows-Ausgabe. Der v1.3.1-Launcher wurde auf dem Mac als PE32+ x86-64 gebaut. ZIP und Lockfile wurden auf dem Mac geprüft. Ein nativer Windows-/CUDA-End-to-End-Test ist offen. |
| Linux | **UNGEPRÜFT**, Zielport offen | Gemeinsame Qt-Oberfläche vorhanden. Backends, Plattformadapter, Einrichtung und Pakete sind auf macOS/Windows ausgerichtet. |

Der macOS-Testbefehl war `MPLCONFIGDIR=<lokales Testverzeichnis> .runtime/aTrain/.venv/bin/python -m unittest discover -s tests`. Das Ergebnis war `Ran 58 tests … OK`. Dieser Testlauf prüft teilweise gemockte Abläufe. Die zusätzlichen GUI- und Modellprüfungen haben den jeweils unten angegebenen Umfang. Die Ersteinrichtung wurde in einem leeren Profil auf dem vorhandenen Mac geprüft. Die Prüfung auf einem physisch zweiten Mac ist offen.

### Fensterkorrektur in v1.3.1

Der Nutzer meldete am 17.11.2026, dass ein maximiertes Fenster beim Öffnen über Dock oder Menüleistensymbol wieder klein wurde. Der Fehler wurde unter Cocoa reproduziert: Der bisherige Wiederöffnungsaufruf `QWindow.show()` änderte das maximierte Fenster von 1920 × 1051 auf 1280 × 820 Pixel und setzte den Fenstermodus auf normal zurück.

`desktop/window_state.py` bündelt jetzt die Fensteraktivierung für Menüleistensymbol, Dock-Wiederöffnung und Einzelinstanz-Nachricht. `setVisible(True)` erhält den bestehenden Modus. Beim Zurückholen aus der Minimierung wird der letzte normale, maximierte oder Vollbildmodus wiederhergestellt. Bewusstes Verkleinern durch den Nutzer wird weiterhin berücksichtigt.

- Sechs Regressionstests und die gesamte Suite mit insgesamt 64 Tests bestanden. Die neuen Tests wurden sowohl mit dem Offscreen-Plugin als auch im Cocoa-Gesamtlauf geprüft.
- Die Anbindung im vollständigen QML-Fenster wurde zusätzlich über `windowRequested`, den echten `QLocalSocket`-Öffnungsweg und das macOS-Aktivierungssignal geprüft. Vier erneute Öffnungen im maximierten Zustand, Wiederöffnung nach Schließen und Minimieren, drei Vollbildaktivierungen sowie eine normale Benutzergröße von 1170 × 740 Pixeln blieben stabil. Dies war eine native Qt-Softwareprüfung der Öffnungssignale, kein automatisierter physischer Dock-Klick.
- Die Mac-App wurde sicher aktualisiert und wieder geöffnet. Alle Modell-Dateien behielten Inode, Größe und Änderungszeit; die Verarbeitungseinstellungen blieben bytegleich. Die Signatur und die Übereinstimmung der installierten Desktop-Dateien zum Prüfstand wurden bestätigt.
- Die gemeinsame Korrektur ist auch im neu gebauten Windows-ZIP enthalten. Dessen Desktop-Dateien, Lockfile und Launcher-Laufzeithash wurden auf dem Mac geprüft. Das Fensterverhalten bleibt **UNGEPRÜFT unter Windows**.

Für diesen Oberflächenfix wurde die geprüfte gebündelte Laufzeit aus v1.3.0 wiederverwendet; Desktop-Quellen, Versionsmetadaten und nativer Mac-Launcher wurden neu paketiert. Die Windows-Ausgabe wurde mit dem bestehenden Buildscript und Zig 0.15.2 neu gebaut. Die Qt-Quellen entsprechen unverändert Version 6.10.2. [Release 1.3.1](https://github.com/adriantagonist87/VoxDrop/releases/tag/v1.3.1)

### Vollständige Neuinstallation aus dem GitHub-Download

Am 17.11.2026 wurden auf Nutzerauftrag sämtliche zuvor erfassten VoxDrop-Installationen, Dienste, Profile, Modelle sowie Build- und Testarbeitskopien entfernt. Originalmedien und Transkripte auf SMB blieben erhalten. Erst danach wurden `main` bei `270e3af7ce96bfce8c5daf49236da2fa4d1d05be` und die öffentliche DMG v1.3.0 neu heruntergeladen.

- Die DMG-Prüfsumme stimmte mit der veröffentlichten Prüfsummendatei und dem GitHub-Asset-Digest überein. Der gesamte Programmordner wurde über den Finder installiert; Fensterstart und Modellspeicher `VoxDrop/Modelle` wurden in der Oberfläche bestätigt.
- Qwen3-ASR, Forced Aligner, pyannote und Whisper wurden über die unveränderte Modelleinrichtung der installierten App vollständig neu geladen. Modelle samt Cache belegten laut `du` rund 9,6 GiB im Programmordner.
- Eine neue synthetische Sprachaufnahme von rund 41 Sekunden wurde mit Qwen auf Metal einschließlich drei DOVER-Lap-Durchgängen und mit Whisper auf Metal einschließlich einfacher Sprecherzuordnung verarbeitet. Beide Aufträge endeten erfolgreich. TXT-Dateien lagen neben den Aufnahmen; SHA-256-Vergleiche bestätigten unveränderte Originale.
- 21 gebündelte Implementierungsdateien waren bytegleich mit dem frischen GitHub-Checkout. Die App-Signatur war nach Downloads und Transkriptionen weiterhin gültig. Alle 58 automatisierten Tests bestanden mit dem installierten Interpreter und dessen separatem DOVER-Paketpfad.
- Ein tatsächlicher Mac-Neustart am 17.11.2026 um 19:12 Uhr und die anschließende Nutzeranmeldung wurden durchgeführt. `launchd` startete den nativen App-Launcher und den lokalen Verarbeitungsdienst automatisch. Ein vorübergehender Beobachter bestätigte beide laufenden Prozesse, ohne sie selbst zu starten, und legte erst danach eine neue Aufnahme im überwachten Ordner ab. Dieser Auftrag wurde automatisch mit Qwen auf Metal und drei DOVER-Lap-Durchgängen erfolgreich abgeschlossen. TXT neben Original und unveränderter Originalhash wurden erneut bestätigt. Die vorübergehenden Testregistrierungen wurden anschließend entfernt; der produktive Anmeldestart blieb aktiv.
- Die einmalige Gatekeeper-Freigabe erfolgte durch den Nutzer. Nach dem Neustart war zusätzlich eine macOS-Freigabe für den Testordner unter „Dokumente“ erforderlich. Diese Systemfreigaben wurden nicht umgangen.

Die Modell- und Neustartprüfungen verwendeten ausschließlich einen lokalen Ordner mit künstlichen Testaufnahmen. Zum Abschluss meldete der Dienst für den inzwischen konfigurierten SMB-Eingang einen verfügbaren Ordner ohne Fehler; Überwachung und Anmeldestart waren aktiv. Diese Ordnerkonfiguration wurde beim Abschluss erhalten. Dieser Test belegt eine neue Installation auf dem vorhandenen Mac; ein physisch zweiter Mac und Windows bleiben ungeprüft.

### Mac-Ersteinrichtung und Modellablage

- Die Distribution installiert einen gemeinsamen Ordner `VoxDrop` mit `VoxDrop.app` und dem später angelegten Ordner `Modelle`. Heruntergeladene Gewichte und Cache lagen im Test vollständig unter `Modelle`, zusammen rund 9,6 GiB für den geprüften Modellbestand.
- Die signierte App blieb nach beiden Downloads und Transkriptionen verifizierbar. Python, Qt, aTrain, CTranslate2/Metal und MLX ließen sich bei ausgeblendetem Build-Verzeichnis aus dem installierten Bundle laden.
- Ein Update innerhalb des bestehenden Ordners erhielt die frisch geladenen Modellgewichte mit bestätigten Prüfsummen. Die produktive Installation übernahm ihre bisherigen Modelle aus dem Benutzerprofil und aktualisierte den Anmeldestart auf den App-Launcher. Konfiguration und Verlauf wurden erhalten.
- Die alte angeheftete Dock-Verknüpfung wurde auf den neuen App-Pfad aktualisiert und ihr Ziel geprüft. `macos/UpdateDock.swift` übernimmt diesen Schritt bei der beauftragten Aktualisierung aus der Entwicklungsumgebung.
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
| Dock-Wiederöffnung und farbiges Menüleistensymbol | Statusfarben zuvor geprüft. v1.3.1 erhält zusätzlich Maximierung und Vollbild bei erneuten Öffnungssignalen, beim Zurückholen und über den Einzelinstanz-Socket; unter Cocoa geprüft. | Taskleisten-/Infobereichsverhalten einschließlich Fensterkorrektur **UNGEPRÜFT unter Windows** |
| Anmeldestart | Nativer App-Launcher mit `--background`: echter Neustart und Anmeldung nach vollständiger GitHub-Neuinstallation geprüft. App und Dienst starteten automatisch; neue Aufnahme wurde nach der einmaligen Ordnerfreigabe automatisch verarbeitet. | **UNGEPRÜFT unter Windows**, HKCU-Run-Anbindung implementiert |
| Installationspaket | DMG-Prüfsumme, Signatur und Übereinstimmung zum installierten Build geprüft, ad hoc signiert | Auf dem Mac gebautes ZIP und öffentlicher Download geprüft, unsigniert. Installation **UNGEPRÜFT unter Windows**. |

## Offene Fehler und technische Lücken

| Kennung | Priorität und Befund | Nächste Prüfung |
| --- | --- | --- |
| WIN-01 | Hoch. Windows-Ausgabe laut Nutzer funktionsgestört. Ein früherer Screenshot zeigt beim Modell-Setup von `speaker-detection` einen `httpcore.ConnectError` mit `WinError 10013`. Die Ursache auf dem PC ist offen. | Version und Commit feststellen, tatsächlichen EXE-Start reproduzieren, Modell-Download und Netzwerkzugriff gezielt diagnostizieren. |
| WIN-02 | Hoch. GPU-Betrieb der Windows-Backends und Speicherbedarf auf RTX 5060 mit 8 GB sind **UNGEPRÜFT unter Windows**. | NVIDIA-/CUDA-Diagnose, beide ASR-Modelle, Forced Aligner, pyannote und DOVER-Lap einzeln ausführen. |
| WIN-03 | Mittel. Frühere Windows-Oberfläche war schlecht lesbar. Die harmonisierte QML-Ausgabe besitzt bisher Mac-Prüfungen. | Aktuelles ZIP bei mehreren DPI-Einstellungen, Fenstergrößen und Spaltenbreiten prüfen. |
| TEST-01 | Mittel. Die gesamte Testsuite hat Plattformannahmen. `test_app_upgrade.py` importiert das macOS-Modul mit `fcntl`. `test_local_job.py` erwartet explizit `metal`. Einige Tests erzeugen Symlinks. | Gemeinsame und OS-spezifische Prüfungen unter Windows ausführbar machen. Fehlende Symlink-Berechtigung als eigenen Testbefund festhalten. |
| BUILD-01 | Mittel. `scripts/build-windows.sh` ist ein macOS-Cross-Build mit `plutil`, `rsync`, `zip` und Zig. Ein nativer Windows-Paketbuild ist offen. | Erst vorhandenes Paket und Quellstart diagnostizieren. Bei Bedarf nativen Build als eigenen Arbeitsschritt umsetzen und dokumentieren. |

Der Fehlerbericht WIN-01 stammt aus einem früheren Testbuild. Die genaue Version des Screenshots ist offen. Auch für v1.3.1 bleibt die native Windows-Reproduktion ausstehend.

## Fortführung auf dem Windows-PC

Der konkrete Auftrag einschließlich Reproduktion, Diagnosebefehlen, Abnahmekriterien und Rückgabeformat steht in der Windows-Übergabe. Nach jedem tatsächlichen Plattformtest sind hier vollständiger Code-Commit, Windows-Version, GPU/Treiber, Testumfang und Ergebnis nachzutragen. [Windows-Übergabeauftrag](UEBERGABE_WINDOWS.md)
