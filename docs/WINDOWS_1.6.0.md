# Windows Stable 1.6.0

Dieser Release bündelt unabhängige manuelle SMB-Drops, Modell-Download-Fortschritt mit Serverprüfung, den direkten Überwachungsschalter und Stoppdialog, den dunklen Popup-Player, die bestätigte Datensatzlöschung, die Modellverwaltung und die Erkennung aktueller Grafik-Watchdog-Berichte 193. Neue Windows-Profile starten mit CPU-Schutz. Der CUDA-Modus bleibt auswählbar und gespeicherte Einstellungen von bestehenden Profilen gelten weiter.

Windows-Code **`6fc12c5d54aa177c0f6ac43f5c431d0525936feb`**, ZIP-SHA-256 **`710cdf6c18a7df9bdeb090c7571d136901036472ae237adc06c2a5a4c6df46c8`**. Tag und ZIP verweisen auf denselben Windows-Code. Die Laufzeitpins und die Modellmanifeste sind erhalten. Das Windows-ZIP enthält keine Modelle oder vorbereitete Laufzeit. [Release und Prüfnachweis](https://github.com/adriantagonist87/VoxDrop/releases/tag/v1.6.0-windows) · [Dateimanifest](../releases/v1.6.0/windows-release.json) · [Windows-Codebranch](https://github.com/adriantagonist87/VoxDrop/tree/release/windows-1.6.0) · [PR #36](https://github.com/adriantagonist87/VoxDrop/pull/36)

## Prüfung

- Kombinierte lokale Windows-Suite mit 309 Fällen. 295 bestanden, 14 Plattform-/Symlink-Skips. Der exakte Commit bestand auch die Windows-CI einschließlich des Workspace-Tests mit 8.000 wartenden und 20.000 historischen Einträgen. [CI-Lauf](https://github.com/adriantagonist87/VoxDrop/actions/runs/45859261928)
- Normaler EXE-Erststart aus dem entpackten ZIP mit separatem Profil. Der Launcher hat aus einer lokalen Kopie des gepinnten Python-/Paket-Caches eine neue Laufzeit im App-Ordner aufgebaut. Der Erstbezug der Runtime über das Internet wurde in diesem Test durch den Cache ersetzt.
- Native Pakettests bei 125 Prozent Qt-Skalierung mit künstlichen Daten: originaler WAV-/FLV-/OPUS-Ton im Popup, Seek, Tempo, Lautstärke und Dateifreigabe. Reale Papierkorboperation, SQLite, Netzlaufwerk-Ablehnung, Modellverwaltung, direkter Überwachungsschalter, Stoppauswahl und Einmal-Import geprüft. Die künstlichen Papierkorbdateien wurden anschließend wiederhergestellt.
- Der separate Prüfnachweis des Releases enthält die CPU-Transkriptionen mit synthetischer Aufnahme. Auf dem betroffenen Rechner wurden für die Freigabe keine CUDA-Lasttests gestartet.

## Installation und Plattformgrenzen

ZIP vollständig in einen beschreibbaren lokalen Ordner entpacken und `VoxDrop.exe` starten. Bei einem Update `Laufzeit`, `Modelle` und das Benutzerprofil erhalten. Windows hält Einstellungen und Verlauf unter `%LOCALAPPDATA%\VoxDrop`.

Der gemeldete Systemstillstand nach dem Start einer CUDA-Transkription ist als offener Grafikvorfall dokumentiert. Der CPU-Schutz ist der geprüfte Betriebsweg für die betroffene Konfiguration. Die Erweiterung des Watchdogs beseitigt die unbekannte Ursache des Systemstillstands nicht. [Diagnose](SYSTEMSTILLSTAND_2026-11-23.md)

Die Hauptlinie erhält die Übergabe und Downloadlinks. Der gemeinsame Quellcode bleibt auf dem Windows-Branch und in den bestehenden Funktions-PRs, bis die neuen gemeinsamen Funktionen unter macOS nativ gegengeprüft wurden. Die Mac-Ausgabe bleibt 1.5.0 Build 27. Vor einer Übernahme insbesondere Popup-Dateifreigabe, Metering und Download-Abbruch, SMB-Ablehnung und Wiederherstellung beim Papierkorb, die Modellverwaltung mit HF-Symlinks, Überwachungsschalter und alle Stoppvarianten prüfen. [Mac- und Windows-Übergabe](UEBERGABE_WINDOWS.md)
