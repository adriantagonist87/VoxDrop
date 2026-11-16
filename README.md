# VoxDrop

Automatic Media Transcription

VoxDrop ist eine lokale macOS-App für Apple Silicon. Der Dienst überwacht eine Liste lokaler Ordner und eingehängter SMB-Pfade. Zu stabilen neuen Mediendateien erstellt er eine gleichnamige UTF-8-TXT. Die installierte App enthält die Laufzeit und speichert Einstellungen, Verlauf, Modellgewichte und Arbeitskopien in `~/Library/Application Support/SMB Transcriber`.

## Installation

VoxDrop 1.0.0 benötigt einen Mac mit Apple Silicon und macOS 26.2 oder neuer. Öffne die DMG und ziehe **VoxDrop** in den Programme-Ordner. Wähle in VoxDrop unter **Modell** Qwen oder Whisper und klicke auf **Modelle herunterladen**. Wenn die Sprechererkennung eingeschaltet ist, lädt VoxDrop auch das dafür benötigte Modell. Die Downloads laufen über Hugging Face. Anschließend verarbeitet VoxDrop Aufnahmen lokal.

Wähle unter **Überwachte Ordner** deinen Eingangsordner. Aktiviere **Ordnerüberwachung aktiv** und klicke auf **Dienst starten**. Für SMB-Ordner muss die Freigabe auf dem Mac eingehängt sein.

## Bedienung

Öffne **VoxDrop** über Spotlight oder im Programme-Ordner deines Benutzerkontos. Beim Öffnen erscheint das App-Symbol im Dock und eine Wellenform in der Menüleiste. Die Wellenform ist grün, wenn alle eingetragenen Ordner erreichbar und beschreibbar sind. Bei einer Störung wird sie rot. Das Menü zeigt auch den Dienststatus, öffnet das Hauptfenster und kann die Ordnerüberwachung pausieren oder fortsetzen.

Links stehen die Dienst- und Transkriptionseinstellungen, in der Mitte der aktive Auftrag und rechts die gespeicherte Historie. Unter **Modell** ist Qwen3-ASR 1.7B voreingestellt. Whisper Large v3 Turbo bleibt im selben Menü verfügbar. Mit **Speichern** gilt die Auswahl für neu erkannte Dateien. Bereits erfasste Aufträge behalten ihre Modelleinstellung. Unter **Rechengerät** ist Apple-GPU (Metal) voreingestellt. Die Ordnerüberwachung ist in der ausgelieferten Konfiguration aus. Unter **Überwachte Ordner** kannst du absolute Pfade und `smb://server/freigabe/ordner` eintragen. `smb://`-Pfade benötigen eine bereits eingehängte Freigabe. Die App prüft jeden Ordner unabhängig auf Lese- und Schreibzugriff. Das Refresh-Symbol stößt die Prüfung des jeweiligen Pfads an. Ein blinkendes Ausrufezeichen und die Warnung oben in der Mitte zeigen Störungen an. Die laufende Menüleisten-App sendet nach der macOS-Freigabe eine Mitteilung pro Störung. Für den Betrieb **Ordnerüberwachung aktiv** wählen und **Dienst starten** klicken. Änderungen an einem bereits laufenden Dienst werden nach **Speichern** übernommen. Das Fenster kann dabei geschlossen werden.

Im **Verlauf** lässt sich die chronologische Sortierung umkehren. Die Gesamtdauer der Audiodatei gibt die Länge der vollständigen Tonspur an. Die Transkriptionsdauer reicht vom Beginn der Verarbeitung bis zum erfolgreichen Export. Die Details neuer Aufträge zeigen die Dauer der Spracherkennung samt Modellladen und Wortzeitabgleich, die Dauer der Sprecherzuordnung und die höchste gemessene physische RAM-Belegung der Transkriptionsprozesse. Die RAM-Belegung wird alle 200 ms abgefragt. Frühere Aufträge zeigen die bereits protokollierten Zeiten und das Modell. Striche kennzeichnen fehlende Einzelmesswerte.

**Mehrere Prüfdurchgänge (DOVER-Lap)** ist unter **Sprechererkennung** verfügbar und zunächst ausgeschaltet. Aktiviert kombiniert VoxDrop drei lokale pyannote-Durchgänge auf der Zeitachse der Originalaufnahme. **Sprecherzahl** gilt in jedem Durchgang. Bei einer abweichenden festen Sprecherzahl oder einer fehlgeschlagenen Fusion zeigen die Auftragsdetails an, dass ein Einzellauf verwendet wurde und warum. Die CLI bietet die Option `--dover-lap`.

In den Auftragsdetails startet **Neu transkribieren** einen eigenen Auftrag mit den aktuell im Fenster gewählten Transkriptionseinstellungen. Die zusätzliche TXT erhält den Zusatz `(Neu …)` und wird im bisherigen Zielordner abgelegt. Ist der Zielordner nicht mehr vorhanden, liegt sie neben der Aufnahme. **Verlauf leeren …** setzt Aufträge und bekannte Dateiversionen nach Bestätigung zurück. Dateien in überwachten Ordnern können anschließend erneut erkannt werden.

**Unterordner für fertige Transkripte erstellen?** legt die TXT im Unterordner des jeweiligen Quellordners ab. Der vorgeschlagene Name lautet `_FERTIGGESTELLT`. Sobald die TXT geprüft ist, verschiebt VoxDrop die Originalaufnahme dorthin. Bei ausgeschalteter Option liegt die TXT bei der Originalaufnahme im Quellordner. Bereits verarbeitete Dateiversionen bleiben im Verlauf erfasst.

Der Schalter **Automatisch bei Anmeldung starten** verwaltet die LaunchAgent-Datei für die nächste Anmeldung. SMBMounter oder macOS bindet die Freigabe ein. Beim Start prüft VoxDrop jeden Ordner sofort und bei fehlendem Zugriff nach weiteren 10, 30 und 60 Sekunden. Ein blockierter Zugriff hat ein Zeitlimit. Andere Ordner werden unabhängig geprüft. Sobald die Verbindung verfügbar ist oder die Startversuche ausgeschöpft sind, gilt das eingestellte Scanintervall.

Wenn macOS nach dem Zugriff auf Netzwerkvolumes fragt, erteile die Freigabe im macOS-Dialog. Danach erkennt der laufende Dienst die Freigabe bei seiner nächsten Prüfung.

## Entwicklungsumgebung

Auf dem Zielgerät geprüft: Mac mini mit M5 Pro und 64 GB RAM, macOS 27.2 (26B123), rund 3,3 TiB frei. `bootstrap.sh` richtet uv 0.13.7, CPython 3.12.13, den aTrain-Commit und dessen unverändertes `uv.lock` unter `.runtime` ein. Das separate `metal/uv.lock` ergänzt CTranslate2 4.9.0 für die Apple-GPU. Das separate `qwen/uv.lock` bindet MLX Audio 0.6.5 für Qwen ein. Die Umgebungen liegen lokal im Projekt.

```sh
sh scripts/bootstrap.sh
PY=.runtime/aTrain/.venv/bin/python
"$PY" smb_transcriber.py --help
"$PY" smb_transcriber.py setup-models
sh scripts/build-app.sh
```

`build-app.sh` baut und signiert das App-Bundle in `.runtime/package`. Nach der Modellbereitstellung installiert `sh scripts/install-app.sh` die App in `/Applications`, sofern der Ordner schreibbar ist, oder in `~/Applications`. Bei der ersten Installation übernimmt das Skript die Modelle, den Verlauf und vorhandene Einstellungen aus dem Projekt. Bei einem Upgrade ergänzt es die Qwen-Gewichte im vorhandenen App-Support-Ordner.

`sh scripts/build-dmg.sh` packt das signierte App-Bundle mit Installationshinweisen und dem gepinnten aTrain-Quellcode in eine DMG. Die Quellrevision steht in `scripts/bootstrap.sh`. Die mitgelieferten Abhängigkeiten behalten ihre jeweiligen Lizenzhinweise.

## Lokaler Test

```sh
PY=.runtime/aTrain/.venv/bin/python
mkdir -p .runtime/testmedia
say -v Anna -o .runtime/testmedia/Pruefaufnahme.aiff \
  'Dies ist eine synthetische Prüfaufnahme. Die Transkription läuft lokal.'
"$PY" smb_transcriber.py probe .runtime/testmedia/Pruefaufnahme.aiff
"$PY" -m unittest discover -s tests -v
```

Der ausdrückliche Modell-Setup lädt und prüft die gepinnten Modellrevisionen für Qwen, die Wortzeit-Ausrichtung, Whisper und Pyannote. Die Qwen-Revisionen und SHA-256-Werte stehen in `qwen-models.json`. Anschließende Jobs laufen mit Hugging Face im Offline-Modus und deaktivierter pyannote-Telemetrie.

```sh
"$PY" smb_transcriber.py setup-models
"$PY" smb_transcriber.py transcribe .runtime/testmedia/Pruefaufnahme.aiff \
  --output-dir .runtime/testmedia --language de --speaker-count 1
```

Sprache und Sprecherzahl bleiben automatisch, wenn die Optionen fehlen. Die CLI verwendet Qwen als Standard. `--model large-v3-turbo` wählt Whisper. Der TXT-Export verwendet UTF-8 und ordnet Sprecherlabels nach ihrem ersten Auftreten. Bei einer Namenskollision bleiben vorhandene Zieldateien geschützt.

## Architektur und Prüfstand

- Qwen verwendet Qwen3-ASR 1.7B in der 8-Bit-MLX-Fassung und den Qwen3-ForcedAligner 0.6B in BF16. Ein separater lokaler Prozess verarbeitet die gemeinsam dekodierte Audiospur in etwa 80 Sekunden langen Abschnitten. Die Zeitstempel werden auf die Originalaufnahme zurückgerechnet. Kann der Aligner keine Wortzeiten zuordnen, bleiben Text und Abschnittszeit erhalten. Der aTrain-Core erhält für beide Modelle die vollständige Tonspur zur Sprecherzuordnung. [Qwen3-ASR](https://github.com/QwenLM/Qwen3-ASR)
- Die App nutzt den gepinnten aTrain-Core für PyAV-Dekodierung, Whisper-Wortzeiten, pyannote-Sprecherzuordnung, Glättung und Gruppierung. Für Apple-GPU nutzt Whisper CTranslate2 4.9 mit FP16. Pyannote führt Segmentierung und Embeddings auf PyTorch MPS aus. Die CPU-Option verwendet INT8 für Whisper. Die Whisper-Pfade verarbeiten die vollständige Datei ohne zusätzliche Aufteilung durch die App. [CTranslate2 4.9](https://github.com/OpenNMT/CTranslate2/releases/tag/v4.9.0)
- Die native SwiftUI-App startet den separaten Python-Dienst und liest die lokale SQLite-Historie über dessen CLI. Dadurch braucht die Oberfläche keinen HTTP-Server. Im Fenstertest lief ein synthetischer Job nach Beenden der App zu Ende. Nach erneutem Öffnen zeigte der Verlauf seinen Erfolg.
- Der Dienst nimmt eine Datei erst nach einem vollständigen stabilen Scanintervall an und prüft die vollständige SSD-Kopie vor der Inferenz. Er ordnet Dateiversionen und unterbrochene Exportversuche persistent zu. Fehler erfordern eine manuelle Wiederholung. Liegt das Transkript bereits lokal vor, wird nur der Export wiederholt.
- `airdrop` unterstützt das exklusive Anlegen von Dateien. Beide Zieldateien können während des Kopierens bereits sichtbar sein. Der Dienst prüft ihre SHA-256-Werte vor dem Abschluss und entfernt den Eingang erst danach. Ein nachweislich eigener, unveränderter Teiltransfer kann beim manuellen Retry fortgesetzt werden. Vorhandene fremde Dateien bleiben erhalten.
- Der Referenzcheckout ist `ea8a7057857220b4299c0ba0b2aaf6def2f35b87`. Bei aTrain bestanden 134 Unit-Tests. Ruff meldete keine Verstöße, und die Formatprüfung für App und Core bestand. Getestete Versionen: faster-whisper 1.2.1, PyAV 18.1.0, Torch 2.9.1, pyannote.audio 4.0.7.
- Die 9,8 Sekunden lange synthetische Aufnahme lief vollständig durch Whisper und pyannote. Ein Dauerdienst-Test mit 30 s Scanintervall und ein separater SMB-Durchlauf unter `_TRANSKRIPTIONEN` waren erfolgreich. Auf der Freigabe wurden TXT, unveränderter Medien-Hash und ein einziger Auftrag nach Neustart bestätigt. Der SMB-Testunterordner wurde anschließend entfernt.
- Die 22 Projekttests sind bestanden. In einem isolierten SMB-Test wechselte der Dienst nach etwa 10 Sekunden von nicht erreichbar zu erreichbar und exportierte danach genau einen synthetischen Metal-Auftrag. Der Login-Dienst ist über `AssociatedBundleIdentifiers` seiner App zugeordnet und wurde nach dem App-Update mit erreichbarer Freigabe gestartet.
- Beim dreiminütigen Ausschnitt derselben Telefonaufnahme brauchte Whisper auf der CPU 36,93 s und mit Metal 9,96 s. Die Sprecherzuordnung dauerte 98,56 s beziehungsweise 8,47 s. Beide Pfade erkannten zwei Sprecher. Die Zeiten erfassen die Phasen ohne Modellladen.
- Der Vergleich mit einem manuellen Sprecher-Referenztranskript steht als Abnahmetest aus.

## Frühere Whisper-Referenzmessung

Jede Datei lief vollständig in einem eigenen Messprozess, ohne zusätzliche Aufteilung. Der Laufzeitwert umfasst die lokale Kopie, Inferenz, Publikation und Rückprüfung. Die TXT-Dateien wurden als UTF-8 gelesen und an Anfang, Mitte und Ende auf aufsteigende Zeitstempel geprüft. Die SHA-256-Werte der archivierten Medien entsprechen den Eingabemedien. Jeder Auftrag steht genau einmal erfolgreich in SQLite.

| Format | Audiodauer | Rechengerät | Laufzeit | Spitzen-RSS |
| --- | --- | --- | --- | --- |
| MP3 | 1:58:02 | CPU-Referenz, Whisper INT8 | 1:25:36 | 18,07 GiB |
| MP4 | 2:48:03 | Apple-GPU, Whisper FP16 | 17:39 | 15,73 GiB |
| M4A | 48:19 | Apple-GPU, Whisper FP16 | 4:17 | 5,44 GiB |

Der systemweit belegte Swap lag bei Beginn des langen MP4-Laufs bei etwa 212 MiB und erreichte 486 MiB. Die vollständige Messreihe steht lokal im Verzeichnis `.runtime/recordings-check.BOHiS5`.

## Lange Stille überspringen

Die standardmäßig ausgeschaltete Checkbox **Lange Stille überspringen** gilt nach **Speichern** für neu erkannte Dateien. Silero VAD sucht lokal nach Abschnitten ohne erkannte Sprache. Die Spracherkennung überspringt Pausen ab etwa drei Sekunden, auch am Anfang und Ende. Kurze Pausen und ein Puffer um Sprachabschnitte bleiben in der Analyse. Die ursprüngliche Tonspur bleibt die Grundlage für Pyannote und für alle Zeitstempel. Die Ausgabedatei enthält weiterhin die vollständige Originalaufnahme. Die CLI bietet die Option `--skip-silence`.

## Lizenzinventur

- Qwen3-ASR und der Qwen3-ForcedAligner stehen laut Modellkarten unter Apache-2.0. [Qwen3-ASR-Lizenz](https://huggingface.co/Qwen/Qwen3-ASR-1.7B) · [Forced-Aligner-Lizenz](https://huggingface.co/Qwen/Qwen3-ForcedAligner-0.6B)

- Der eingebundene aTrain-Quellstand steht unter AGPL-3.0-or-later. [aTrain-Quellstand und Lizenz](https://github.com/aTrainTranscription/aTrain/tree/ea8a7057857220b4299c0ba0b2aaf6def2f35b87)
- Das Whisper-Modell steht laut aTrain-Modellregister unter MIT. [Whisper-Modellrevision](https://huggingface.co/aTrain-core/faster-whisper-large-v3-turbo/tree/df99141c9f5db0615d025664cff8949373a69593)
- Das Sprechermodell steht laut aTrain-Modellregister unter CC-BY-4.0. [Sprechermodellrevision](https://huggingface.co/aTrain-core/speaker-detection/tree/027e7a80b40a5e3e69cb83ccf901725b59a4063d)
- Die transitiven Abhängigkeiten sind im Upstream-Lockfile erfasst. Vor Distribution sind deren Lizenzhinweise und die Modellattributionen für ein konkretes Paket zu vervollständigen.
