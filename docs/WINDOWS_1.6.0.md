# Windows Stable 1.6.0

Dieser Release bündelt unabhängige manuelle SMB-Drops, Modell-Download-Fortschritt mit Serverprüfung, den direkten Überwachungsschalter und Stoppdialog, den dunklen Popup-Player, die bestätigte Datensatzlöschung, die Modellverwaltung und die Erkennung aktueller Grafik-Watchdog-Berichte 193. Neue Windows-Profile starten mit CPU-Schutz. Der CUDA-Modus bleibt auswählbar und gespeicherte Einstellungen von bestehenden Profilen gelten weiter.

Am 26.11.2026 wurden die Download-Dateien im bestehenden Release auf Revision 2 aktualisiert. Die Revision behebt die Sperre im Modell-Tab bei Leerlauf und ergänzt das gemeinsame Löschen mehrerer Verlaufseinträge mit vorausgewähltem Erhalt der Originale.

Das aktuelle ZIP enthält Windows-Code **`5aed5c184cefeb27b0cde2f375c65a39623be99a`** und hat SHA-256 **`ebbb983d2db41d0d82213d3ef87b67dc4d40ef6ba7ba8f1907b2b4a583d79f59`**. Der unveränderte Tag `v1.6.0-windows` dokumentiert zusammen mit den automatisch generierten Quellarchiven den ursprünglichen Commit `6fc12c5d54aa177c0f6ac43f5c431d0525936feb`. Das ursprüngliche ZIP hatte SHA-256 `710cdf6c18a7df9bdeb090c7571d136901036472ae237adc06c2a5a4c6df46c8`. Laufzeitpins und Modellmanifeste sind erhalten. Laufzeit und Modelle werden nach dem Entpacken eingerichtet. [Release und Prüfnachweis](https://github.com/adriantagonist87/VoxDrop/releases/tag/v1.6.0-windows) · [Aktuelles Dateimanifest](../releases/v1.6.0/windows-release.json) · [PR #38](https://github.com/adriantagonist87/VoxDrop/pull/38)

## Prüfung der aktualisierten Download-Dateien

- Windows-Suite mit 317 Fällen, davon 303 bestanden und 14 übersprungen. Der exakte Build-Commit bestand den Windows-Pflichtcheck. [CI-Lauf](https://github.com/adriantagonist87/VoxDrop/actions/runs/45871968314)
- Normaler EXE-Start aus dem frisch gebauten ZIP mit separatem Profil und neuer Laufzeit aus dem gepinnten Offline-Cache. Alle 103 Programmdateien und die Prüfsumme des öffentlich heruntergeladenen ZIP stimmten mit dem Manifest überein.
- Bei 125 Prozent Skalierung 20 Originale behalten und 20 TXT in den Papierkorb verschoben. Zusätzlich drei Datensätze samt Originalen, Abbrechen und Modelllöschung im Leerlauf mit künstlichen Daten geprüft. Alle 26 verschobenen Testdateien wiederhergestellt. [Datensatzlöschung](DATENSATZ_LOESCHEN.md) · [Modellverwaltung](MODELLVERWALTUNG.md)

## Prüfung des ursprünglichen Pakets

- Kombinierte lokale Windows-Suite mit 309 Fällen. 295 bestanden, 14 Plattform-/Symlink-Skips. Der exakte Commit bestand auch die Windows-CI einschließlich des Workspace-Tests mit 8.000 wartenden und 20.000 historischen Einträgen. [CI-Lauf](https://github.com/adriantagonist87/VoxDrop/actions/runs/45859261928)
- Normaler EXE-Erststart aus dem entpackten ZIP mit separatem Profil. Der Launcher hat aus einer lokalen Kopie des gepinnten Python-/Paket-Caches eine neue Laufzeit im App-Ordner aufgebaut. Der Erstbezug der Runtime über das Internet wurde in diesem Test durch den Cache ersetzt.
- Native Pakettests bei 125 Prozent Qt-Skalierung mit künstlichen Daten: originaler WAV-/FLV-/OPUS-Ton im Popup, Seek, Tempo, Lautstärke und Dateifreigabe. Reale Papierkorboperation, SQLite, Netzlaufwerk-Ablehnung, Modellverwaltung, direkter Überwachungsschalter, Stoppauswahl und Einmal-Import geprüft. Die künstlichen Papierkorbdateien wurden anschließend wiederhergestellt.
- Der separate Prüfnachweis des Releases enthält die CPU-Transkriptionen mit synthetischer Aufnahme. Auf dem betroffenen Rechner wurden für die Freigabe keine CUDA-Lasttests gestartet.

## Installation und Plattformgrenzen

ZIP vollständig in einen beschreibbaren lokalen Ordner entpacken und `VoxDrop.exe` starten. Bei einem Update `Laufzeit`, `Modelle` und das Benutzerprofil erhalten. Windows hält Einstellungen und Verlauf unter `%LOCALAPPDATA%\VoxDrop`.

Der gemeldete Systemstillstand nach dem Start einer CUDA-Transkription ist als offener Grafikvorfall dokumentiert. Der CPU-Schutz ist der geprüfte Betriebsweg für die betroffene Konfiguration. Die Erweiterung des Watchdogs beseitigt die unbekannte Ursache des Systemstillstands nicht. [Diagnose](SYSTEMSTILLSTAND_2026-11-23.md)

Die Hauptlinie erhält die Übergabe und Downloadlinks. Der gemeinsame Quellcode bleibt auf dem Windows-Branch und in den bestehenden Funktions-PRs, bis die neuen gemeinsamen Funktionen unter macOS nativ gegengeprüft wurden. Die Mac-Ausgabe bleibt 1.5.0 Build 27. Vor einer Übernahme insbesondere Popup-Dateifreigabe, Metering und Download-Abbruch, SMB-Ablehnung und Wiederherstellung beim Papierkorb, die Modellverwaltung mit HF-Symlinks, Überwachungsschalter und alle Stoppvarianten prüfen. [Mac- und Windows-Übergabe](UEBERGABE_WINDOWS.md)
