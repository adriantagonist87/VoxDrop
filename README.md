<img src="macos/VoxDropLogo.png" alt="VoxDrop – Audio und Video zu Transkripten" width="144" height="144">

# VoxDrop

VoxDrop ist eine kostenlose App für macOS und Windows auf Basis von aTrain. Sie überwacht lokale Ordner und eingebundene SMB-Freigaben und transkribiert neue Audio- und Videodateien automatisch auf dem eigenen Rechner. Das Transkript wird als TXT neben der Aufnahme oder zusammen mit ihr in einem Unterordner gespeichert.

| System | Download | Stand |
| --- | --- | --- |
| **Windows 11 x64 / NVIDIA CUDA** | **[Windows-ZIP herunterladen](https://github.com/adriantagonist87/VoxDrop/releases/download/v1.4.0/VoxDrop-1.4.0-Windows-x64.zip)** · [Release und Prüfsumme](https://github.com/adriantagonist87/VoxDrop/releases/tag/v1.4.0) | Neue Arbeitsübersicht; Programmdateien und SHA-256 im [Release-Manifest](releases/v1.4.0/windows-release.json). |
| **macOS / Apple Silicon** | **[Mac-DMG herunterladen](https://github.com/adriantagonist87/VoxDrop/releases/download/v1.3.1/VoxDrop-1.3.1-macOS-arm64.dmg)** · [Mac-Release](https://github.com/adriantagonist87/VoxDrop/releases/tag/v1.3.1) | Bisherige native Mac-Ausgabe. Die unten beschriebenen neuen Windows-Funktionen werden auf dieser gemeinsamen Codebasis für Mac nachgezogen. |

## Windows einrichten

![VoxDrop-Arbeitsübersicht mit synthetischen Beispieldateien](docs/images/workspace-wide.png)

**Neu in 1.4:** Queue und kompakter Verlauf nebeneinander, bei kleinen Fenstern als Reiter. Aktueller Auftrag, quadratisches Play/Stopp, Ordnerstatus und GPU-Budget bleiben erreichbar. Die Einstellungen sind in **Transkription**, **Ordner & Überwachung** und **App & Daten** gegliedert, mit Speichern/Verwerfen. Große Verläufe erhalten Seitenwahl; aufgeklappte Queuezeilen und Scrollposition bleiben beim Abarbeiten erhalten. [Alle Funktionen, Screenshots und Prüfung](docs/WORKSPACE_LAYOUT.md).

Die ZIP vollständig in einen beschreibbaren lokalen Ordner entpacken und **VoxDrop.exe** starten. Beim ersten Start werden die passende Python-/CUDA-Laufzeit und anschließend die ausgewählten Modelle heruntergeladen. Danach erfolgen Transkription und Suche lokal. Überwachte Ordner und Einstellungen richtet jede Installation selbst ein. [Voraussetzungen und Einrichtung](windows/README.md)

Bei einem Update die Ordner **Laufzeit** und **Modelle** erhalten. Einstellungen und Auftragsdaten liegen unter **%LOCALAPPDATA%\VoxDrop**. Der Download enthält keine persönlichen Medien, Transkripte oder Einstellungen.

## Funktionen der aktuellen Windows-Ausgabe

- **GPU-Arbeitsbudget:** Regler von 10–100 % unter Windows-CUDA, während der Verarbeitung änderbar. Gezielte Rechenpausen entlasten den Desktop; kurze Spitzen und der Grafikspeicherbedarf bleiben bestehen. [Messungen und Grenzen](docs/GPU_ARBEITSBUDGET.md).
- **Play und Stopp:** Normaler quadratischer 44×44-Knopf an fester Stelle oben, auch im Vollbild. Starten setzt die Queue fort; Stopp beendet die aktuelle Erkennung und behält die Warteschlange. Fertige Ergebnisse werden noch sicher gespeichert. [Bedienung](docs/PLAY_STOPP.md).
- **Vollständige Warteschlange:** Alle wartenden Dateien mit Dateiname, Pfad, Position und Status im Arbeitsbereich. Kompakte Ansicht sowie ausklappbare Details für die ganze Liste oder einzelne Aufträge.
- **Ordner einzeln steuern:** Wartende automatische Aufträge eines pausierten oder entfernten Pfads verlassen die Queue. Unter **Warteschlange → Aktionen → Überwachte Ordner neu einlesen** lassen sich aktive Pfade sofort zum Scan vormerken. Jeder Pfad kann die globale Ausgabe übernehmen, TXT neben der Quelle speichern oder Aufnahme und TXT gemeinsam in den Zielunterordner verschieben.
- **Reihenfolge und Abbruch:** Dateien per Drag-and-drop oder Menü vorziehen/verschieben, einzelne Einträge entfernen, die aktuelle Transkription oder die ganze Warteschlange abbrechen und pausieren/fortsetzen. Die Reihenfolge bleibt beim Neustart erhalten; Umordnen funktioniert auch in Suchergebnissen.
- **Schnelle Suche:** Lupenbuttons öffnen die Suche nach Dateinamen und vollständigen Pfaden, einschließlich Wildcards. Im Verlauf durchsucht **Detailsuche starten** auf ausdrücklichen Wunsch auch Transkriptinhalte; die Suche kann wieder gestoppt werden. Der lokale Suchindex wird anschließend wiederverwendet.
- **Verarbeitungsverlauf und Bestand:** **Alle**, **Fehler**, **Fertig**, **Abgebrochen** und **Bestand** zeigen Anzahlen in Klammern. Fehler werden bei positiver Anzahl rot hervorgehoben. Nie gestartete, aus der Queue entfernte Dateien zählen nicht als bearbeitet; bereits vorhandene TXT werden separat als Bestand geführt.
- **Transkripte direkt öffnen:** In den Auftragsdetails das TXT mit der Standardanwendung des Betriebssystems öffnen oder seinen tatsächlichen Speicherort im Explorer anzeigen. Historische Fremdtranskripte erhalten keine erfundenen Modell- oder Laufzeitangaben.
- **Konflikte bei Datei-/Ordnerdrops:** Ein gemeinsamer Dialog erklärt bereits eingereihte und schon transkribierte Dateien. Je nach Konflikt lassen sich Dateien priorisieren, separat neu transkribieren, sofort bearbeiten oder ignorieren. Mehrfach abgelegte Dateien werden dedupliziert.
- **Dateischutz:** Vorhandene Ergebnisse werden geschützt. Ausdrückliche Neutranskriptionen erhalten separate Ergebnisdateien. Inhaltsgleiche umbenannte Aufnahmen können bekannte Ergebnisse wiederverwenden; noch geschriebene Aufnahmen, etwa von OBS, werden zurückgestellt.
- **Verlauf wirklich bereinigen:** Nach Bestätigung werden sämtliche gespeicherten Auftrags-, Queue-, Datei- und Suchdaten einschließlich des lokalen Arbeitscaches entfernt. Originalaufnahmen, TXT und Einstellungen bleiben bestehen. Bei aktiver Überwachung liest das nächste Intervall die Ordner neu ein: vorhandene TXT erscheinen wieder im Bestand, fehlende Ergebnisse werden neu eingereiht.
- **Tray und Taskleiste:** **X** blendet das Fenster in den Systemtray aus; Überwachung und Verarbeitung laufen weiter. **Minimieren** legt es in die Taskleiste. **VoxDrop beenden** im Tray stoppt die gesamte App samt Arbeitsprozessen und entlädt Modelle aus RAM/VRAM. Eine tatsächlich beendete App überwacht keine Ordner.
- **Mehrere Ordner und Netzlaufwerke:** Lokale Ordner und eingerichtete SMB-/UNC-Freigaben überwachen, optional rekursiv. Ordnerausfälle werden sichtbar; erreichbare andere Ordner können weiter bearbeitet werden. Einmalige Datei-/Ordnerdrops funktionieren auch bei ausgeschalteter regulärer Überwachung.
- **Lokale KI:** Qwen3-ASR 1.7B oder Whisper Large v3 Turbo, Zeitmarken, Deutsch/Englisch beziehungsweise automatische Spracherkennung, optional Stilleüberspringen und pyannote-Sprecherzuordnung mit DOVER-Lap. Sprach- und Sprechermodelle werden nacheinander geladen.
- **Mehr Platz und klare Bedienung:** Dunkle Oberfläche mit verstellbaren Spalten, neues transparentes App-Icon, kein platzverbrauchender Logo-Header im Fenster und konsolenlose Hintergrundprozesse.

Metadaten- und Inhaltssuche wurden mit 20.000 synthetischen Transkripten geprüft. Die Detailsuche indexiert Inhalte ausdrücklich im Hintergrund; beim Tippen in die normale Dateisuche wird kein vollständiger Inhaltslauf gestartet. [Prüfungen und Grenzen](docs/SUCHE_UND_DROP_KONFLIKTE.md)

## Mac einrichten

Voraussetzung für die Mac-Version ist ein Mac mit Apple Silicon und macOS 26.2 oder neuer.

Die DMG öffnen, den gesamten Ordner **VoxDrop** nach **Programme** ziehen und darin **VoxDrop.app** öffnen. Beim ersten Start kann macOS eine Bestätigung unter **Systemeinstellungen → Datenschutz & Sicherheit → Dennoch öffnen** verlangen. Der Download ist ad hoc signiert. [Apples Anleitung](https://support.apple.com/de-de/102445)

Über **Modelle herunterladen** werden die gewünschten Modelle und ihr Download-Cache im Programmordner unter **VoxDrop/Modelle** eingerichtet. Zum Entfernen der App samt Modellen den gesamten Ordner **VoxDrop** löschen. Bei Updates die neue **VoxDrop.app** in den vorhandenen VoxDrop-Ordner kopieren. Einstellungen und Verlauf liegen im Benutzerordner unter **Library/Application Support/VoxDrop**.

Für die Weiterentwicklung am Mac dient der gemeinsame Quellstand auf **main**. Die vorhandene Mac-DMG bleibt unverändert, bis die neuen gemeinsamen Funktionen nativ geprüft und neu paketiert wurden. Der Übergabeauftrag enthält Startbefehle, Funktionsmatrix, Builddateien, exakte Windows-Prüfstände und die Mac-Abnahme. **[Mac auf Windows-Funktionsstand bringen](docs/MAC_PORTIERUNG_WINDOWS_2026-11-18.md)**

[Arbeitsregeln](AGENTS.md) · [Projektstatus](docs/PROJEKTSTATUS.md) · [Entwicklung](docs/ENTWICKLUNG.md) · [Windows-Übergabe](docs/UEBERGABE_WINDOWS.md) · [Release-Identität und Branchschutz](docs/GITHUB_ABSCHLUSS_2026-11-18.md)

## Gemeinsame Grundlagen

- **Qwen3-ASR 1.7B** ist das Standardmodell. **Whisper Large v3 Turbo** ist als Alternative auswählbar.
- Transkripte mit Zeitstempeln und optionaler Sprecherzuordnung über pyannote. DOVER-Lap kann drei Durchgänge der Sprecherzuordnung zusammenführen.
- Lange Sprechpausen überspringen und Aufträge aus dem Verlauf mit anderen Einstellungen erneut transkribieren.
- Start bei der Anmeldung, Menüleistenstatus und Hinweise bei unerreichbaren oder schreibgeschützten Ordnern.
- Gemeinsame dunkelgraue Oberfläche. Der aktuelle Windows-Quellstand bietet eine verstellbare Queue-/Verlaufsansicht und getrennte Einstellungen; die veröffentlichte Mac-DMG behält bis zur nativen Portierung ihren bisherigen Aufbau.
- **Unterordner mit einbeziehen** erweitert die Überwachung auf verschachtelte Ordner. Die TXT-Dateien landen direkt neben den Aufnahmen.
- Ordner lassen sich für eine einmalige Transkription ins Fenster ziehen. VoxDrop reiht die Aufnahmen samt Unterordnern ein und legt die TXT-Dateien neben den Originalen ab.

## Benchmark auf einem Mac mini M5 Pro

Je ein Lauf pro Modell und Aufnahme auf der Apple-GPU eines Mac mini mit M5 Pro und 64 GB gemeinsamem Speicher. Die Gesamtzeit umfasst Dekodierung, Modellladen, Transkription, Zeitabgleich und die gemeinsame Sprecheranalyse mit pyannote. Der RAM-Wert ist die physische Spitzenbelegung des jeweiligen Spracherkennungsprozesses.

| Aufnahme | Audiodauer (Std:Min:Sek) | Qwen gesamt (Min:Sek) | Qwen RAM | Whisper gesamt (Min:Sek) | Whisper RAM |
| --- | ---: | ---: | ---: | ---: | ---: |
| Telefon | 0:48:19 | 3:48 | 5,28 GiB | 4:22 | 7,34 GiB |
| Raum | 1:58:02 | 9:35 | 5,09 GiB | 12:58 | 25,06 GiB |
| Video | 2:48:03 | 12:17 | 5,13 GiB | 17:26 | 30,10 GiB |

## Lizenzhinweise

VoxDrop steht unter der GNU Affero General Public License Version 3 (AGPL-3.0-only). [Lizenztext für VoxDrop](LICENSE)

Die eingebundene aTrain-Version steht unter AGPL-3.0-or-later. Bei der Weitergabe der DMG ist der zugehörige Quellcode gemäß § 6 der AGPL bereitzustellen. [aTrain-Quellstand](https://github.com/aTrainTranscription/aTrain/tree/ea8a7057857220b4299c0ba0b2aaf6def2f35b87) · [Lizenztext](https://spdx.org/licenses/AGPL-3.0-or-later.html)

Die Oberfläche verwendet Qt und Qt for Python. Der entsprechende Quellcode steht bei den Release-Downloads bereit. [Lizenzhinweise](desktop/Qt-Lizenzen.md)

Qwen3-ASR und der Forced Aligner stehen unter Apache-2.0, Whisper unter MIT und das Sprechermodell unter CC BY 4.0. [Qwen3-ASR](https://huggingface.co/Qwen/Qwen3-ASR-1.7B) · [Forced Aligner](https://huggingface.co/Qwen/Qwen3-ForcedAligner-0.6B) · [Whisper](https://huggingface.co/aTrain-core/faster-whisper-large-v3-turbo) · [Sprechermodell](https://huggingface.co/aTrain-core/speaker-detection)
