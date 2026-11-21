# macOS auf dem gemeinsamen Stand 1.4

Ausgangsbasis: `2e493e973c9f24ed3b46e44c45f31f7801398217` aus `origin/main`, Windows-Paketcode `48ff35f43f07c07b4b7abd0b22561c9096fbe1cc`. Auftrag vom 21.11.2026: sämtliche aktuellen Windows-Funktionen und die neue Oberfläche auf dem Mac mini produktiv bereitstellen. Die vorhandene Mac-Installation war 1.3.1 / Build 23; Konfiguration, Verlauf, Modelle und Anmeldestart werden erhalten.

## Mac-Anpassungen

- Gemeinsame QML-Arbeitsübersicht, stabile Listen, Suche, Konfliktdialoge, globale Queue und Play/Stopp unverändert übernommen.
- Qwen-MLX lädt ASR und Forced Aligner nacheinander. Erst werden die Erkennungsergebnisse gesammelt, dann ASR-Referenzen und MLX-Cache freigegeben, anschließend wird ausgerichtet. Audioabschnitte und Zeitrechnung bleiben erhalten. Whisper wird bereits vor der Sprecherpipeline geschlossen.
- GPU-Budget auch auf Metal: temporäre Instanztypen an MLX-Audioencoder und Textdecoderblöcken evaluieren die Ergebnisse vor Synchronisation/Pause. CTranslate2-Metal delegiert seine synchronen nativen Aufrufe. Beide pyannote-Modelle erhalten MPS-Hooks. CPU bleibt ohne GPU-Pausen. Modellpräzision und Erkennungsparameter bleiben gleich; kein exaktes systemweites Last- oder RAM-Limit.
- `posix_guard.py` besitzt die jeweilige Unix-Prozessgruppe. Das Schließen der nur beim Eigentümer gehaltenen Pipe beendet die Gruppe auch nach hartem Eigentümerabsturz. Ausgabe/Exitcode bleiben erhalten. Der vorhandene Supervisor, begrenzte Logs und automatische Auftragswiederaufnahme gelten nun auch auf dem Mac. Temporäre Audiodaten liegen auf beiden Systemen im bereinigbaren Auftrag.
- Der Owner-Watchdog merkt PID und Erstellungszeit, damit eine später gesperrte SQLite-Datenbank die Eigentümerverlust-Erkennung nicht unterbindet. Profile werden weiterhin getrennt beendet.
- Auch der kurze Unix-Startbefehl bleibt bis zur Dienstübergabe pipegebunden. Ein während SQLite blockierter Start darf seinen GUI-Eigentümer nicht überleben; der erfolgreich übergebene Supervisor legt ausdrücklich eine neue Sitzung an. Zwei echte Prozessregressionen prüfen beide Seiten dieser Übergabe. Der Windows-Startpfad bleibt erhalten.
- Cmd-Q läuft über einen Qt-Quit-Eventfilter in den vorhandenen vollständigen Abschluss. Rotes X bleibt Ausblenden in die Menüleiste; Minimieren bleibt Dock.
- Nativ reproduzierter Cocoa-Fehler: nach Maximieren → Vollbild → Minimieren wurden `Minimized → Windowed → Maximized → Minimized` gemeldet. Der gespeicherte Vollbildmodus wird während dieses Übergangs festgehalten und nach der nativen Wiederherstellung bestätigt. Bewusstes anschließendes Normalisieren bleibt wirksam.
- Lokale offene Schreibhandles werden mit dem vorhandenen macOS-`lsof` erkannt, auch ohne weiteres Größenwachstum. Ein auf einem anderen SMB-Client offener Schreiber ist damit nicht nachgewiesen; Dateiversions-/Kopier-/Veröffentlichungsschutz bleibt zusätzlich aktiv.
- Der Installer wartet auf einen tatsächlich laufenden aktiven Auftrag, beendet auch Supervisoren und startet anschließend den nativen App-Eigentümer. Ein verwaister DB-Zustand ohne laufenden Dienst blockiert das Update nicht.
- Optionaler Build aus einer vorhandenen signaturgeprüften Bundle-Laufzeit; kritische Python-/Torch-/Qt-/MLX-Pins werden erneut geprüft. Keine neuen Abhängigkeiten, Modelle oder Lockfileänderungen. `build-info.json` enthält Code-SHA, Entwicklungskennzeichnung und Hashes aller 43 eigenen Paketdateien. Die DMG enthält den genauen eigenen Quellstand und den aTrain-Pin.

## Bereits ausgeführte Prüfungen

macOS 27.2, Apple Silicon, Python 3.12.13, Qt 6.10.2, MLX 0.32.4 / MLX-Audio 0.6.5, Torch 2.9.1, CTranslate2-Metal 4.9.0. Nur isolierte Profile und synthetische Medien; vorhandene lokale Modelle weiterverwendet.

| Prüfung | Ergebnis |
| --- | --- |
| Gemeinsame Regressionen | Final nativ auf Cocoa: 209 Fälle in 52,975 s, 202 bestanden, sieben reine Windows-Skips. Die neue vollständige Cocoa-Regression läuft hier tatsächlich. Vorheriger Offscreen-Lauf: 207 Fälle in 41,680 s, acht Skips. |
| Native Fenster-/Modellregressionen | Zehn engere Fälle auf Cocoa bestanden. Erweiterte Maximieren-/Vollbild-/Minimierungsfolge zusätzlich im Paketprüfer. |
| Große native Oberfläche | 8.000 Queue- und 20.000 Verlaufseinträge bei 100/125/150 % Qt-Skalierung; Mindestfenster, alle Einstellungsgruppen, Details, Menüs und Dialoge; keine QML-Warnungen. |
| Inhaltsindex | 20.000 synthetische TXT, 206 erwartete Treffer, keine übersprungenen Dateien, Abbruch bestanden. Indexieren/Suchen 0,892 s; einschließlich Schreiben 1,888 s. Ein lokaler Einzellauf, keine SMB-Leistungszusage. |
| Modellmatrix | Zwölf echte Metal-Läufe: beide ASR-Modelle × getrennte deutsche/englische Aufnahmen × 100 %, 50 %, 50 % mit Stille und drei DOVER-Durchgängen. Textanker, ursprüngliche Zeitlinie nach zwölf Sekunden Pause und Originalhashes bestanden. Je Sprache/Modell waren die Transkripte bei 100/50 % ohne Stilleoption bytegleich. |
| Normale native App | Swift-Bundle-Einstieg mit isoliertem Profil geöffnet; Oberfläche und Einstellungen visuell geprüft, Metal-Budget per Tastatur gespeichert. Tatsächliches Cmd-Q leitete vollständigen Abschluss ein; GUI, Supervisor und Dienst danach beendet. |
| Finaler Paketprüfer | 1.4.0 Build 25, Programmcode `c6ef0b7433727eea357cf85798585ab326edb2f7`: echte QML-Klicks Stopp → Start während Metal-Qwen; Stopp in 0,892 s, Queue erhalten, erfolgreiche Verarbeitung und geschützte Inhaltswiederverwendung. Drei DOVER-Durchgänge mit tatsächlicher Fusion in SQLite bestätigt. Native Fensterzustände, X/Tray, echte TXT-Inhaltssuche, SQLite/Fremdschlüssel und vollständiges natives Quit bestanden. |
| Ausfall und Wiederanlauf | Derselbe Release-Build über seinen Swift-Launcher mit `--background`: Dienst-SIGKILL, keine verwaisten Inferenzprozesse, automatischer Dienst-/Auftragswiederanlauf, dekodiertes Audio im Auftragsordner und anschließend entfernt. GUI-SIGKILL bei gehaltener SQLite-Schreibtransaktion: gesamter eigener Prozessbaum nach 6,167 s beendet; keine neuen Scans ohne App; erneuter App-Start stellte den unterbrochenen Auftrag fertig. |
| Echte SMB-Ablage | Frischer eigener Testunterordner auf der bereits gemounteten Freigabe: rekursiver Drop mit Unicode/Leerzeichen/Komma/Plus, TXT neben unverändertem Original, keine Archivverschiebung, Neutranskription mit eigener TXT und geschütztem vorherigen Ergebnis, lokale SQLite konsistent. Eigene Testablage anschließend vollständig entfernt. Kein SMB-Serverausfall erzwungen. |
| CPU | Finaler Build 25: Qwen-CPU mit vollständiger deutscher künstlicher Aufnahme in 81,133 s; Whisper-CPU mit vollständiger englischer Aufnahme, Stille und dreifacher DOVER-Fusion in 26,952 s. Textanker und Originalhashes bestanden. Die vorhandenen quantisierten Ganzzahlgewichte bleiben erhalten; ausschließlich CPU-Gleitkommaparameter verwenden jetzt FP32. Ein nativer Stack bestätigte den extrem langsamen skalaren BF16-QuantizedMatmul-Kernel: vorher benötigte eine Drei-Sekunden-Probe 447 s, die isolierte FP32-Gegenprobe 14,576 s. Metal-Datentypen und Modell-Dateien bleiben unverändert. |

Die 100-%-Sprachläufe dauerten auf den rund 25–28 Sekunden langen Testaufnahmen 2,5–3,9 Sekunden. Mit 50 % und Sprecher/DOVER lagen sie bei 13,5–22,5 Sekunden. Diese kurzen künstlichen Aufnahmen sind keine neue Langaufnahme-/RAM-Benchmarkserie. Die alten README-Benchmarks bleiben historische Messungen.

### Direkter Qwen-Speichervergleich

Der unveränderte Mac-Backendcode aus `df207f79aa812f70d090e4306443436d51d48952` und der neue Backendcode wurden nacheinander mit denselben vorhandenen Modellen und derselben künstlichen deutschen Aufnahme ausgeführt. An den Ladegrenzen wurde nach `mx.synchronize()` der aktive MLX-Speicher erfasst; je Lauf wurde die MLX-Spitzenmessung zurückgesetzt. Die vollständigen ausgerichteten Ergebnis-JSONs waren bytegleich.

| MLX-Kennzahl | Früher | Sequenzielle Phasen |
| --- | ---: | ---: |
| Aktiv vor Laden des Aligners | 2.469.576.408 Byte | 203.388 Byte |
| Aktiv nach Laden des Aligners | 4.311.206.872 Byte | 1.841.833.852 Byte |
| Spitzenallokation im Lauf | 5.684.462.072 Byte (5,29 GiB) | 3.841.581.516 Byte (3,58 GiB) |

Die MLX-Spitze sank in diesem Einzellauf um 1,72 GiB beziehungsweise 32,4 %. Das ist keine Messung des gesamten Prozessbaums, der gesamten macOS-RAM-Anzeige oder eines mehrstündigen Meetings. Der Effekt entsteht durch das tatsächliche Freigeben des ASR-Modells vor dem Aligner, ohne Quantisierungs-/Modellwechsel.

## Reproduzieren

```sh
sh scripts/build-app.sh --runtime-from /pfad/zur/bisherigen/VoxDrop.app
res="$PWD/.runtime/package/VoxDrop.app/Contents/Resources"
"$res/Python/bin/python3.12" -BEs scripts/check-workspace-ui.py --native --output /privater/neuer/pruefordner --content
"$res/Python/bin/python3.12" -BEs scripts/check-macos-models.py --app .runtime/package/VoxDrop.app --models /pfad/zu/Modelle --fixtures /pfad/zu/kuenstlichen/wavs --output /privater/neuer/modellpruefordner
"$res/Python/bin/python3.12" -BEs scripts/check-macos-app.py --app .runtime/package/VoxDrop.app --models /pfad/zu/Modelle --fixture /pfad/zu/kuenstlicher/de.wav --output /privater/neuer/apppruefordner
"$res/Python/bin/python3.12" -BEs scripts/verify-macos-bundle.py .runtime/package/VoxDrop.app
```

Das Modellprüfskript verlangt `de.wav`, `en.wav` und `references.json` mit `language`, `required` und `second_start_seconds`. Die Aufnahmen enthalten ausschließlich künstliche Sprache. Private Pfade, Datenbanken, Rohlogs und Medien bleiben unter `.runtime/` und außerhalb von GitHub.

## Produktivupdate und Release

Die signierte App 1.4.0 Build 25 ist am bisherigen Mac-Installationsort produktiv installiert und sichtbar geöffnet. Vorher wurden App, konsistenter SQLite-Verlauf, Einstellungen und Anmelderegistrierung außerhalb des Repositorys gesichert. Nachher: Konfiguration bytegleich; alle vier vorherigen Aufträge in ID, Quelle, Dateiversion und Zustand erhalten; sämtliche 106 Modell-/Cachedateien in Hash, Inode, Größe und Änderungszeit unverändert; SQLite/Fremdschlüssel ok; Bundle-Signatur und alle 43 Manifestdateien gültig. Die bestehende Anmelderegistrierung startet weiterhin den nativen App-Launcher mit `--background`, RunAtLoad und ohne KeepAlive.

Die tatsächliche installierte Oberfläche meldete Überwachung an, den bestehenden SMB-Ordner 1/1 verfügbar, keine Fehler und keinen aktiven Auftrag. Der laufende Dienst gehört jetzt zur neuen GUI. Paketcode: `c6ef0b7433727eea357cf85798585ab326edb2f7`; vollständiger nativer 209er-Teststand mit finaler Cocoa-Regressionsfolge: `c6ef0b7433727eea357cf85798585ab326edb2f7`. [Windows-CI auf diesem Stand erfolgreich](https://github.com/adriantagonist87/VoxDrop/actions/runs/44927646527).

Die separate Mac-Veröffentlichung verwendet `v1.4.0-macos` und ersetzt keine vorhandene Windows-ZIP. Die DMG ist unter [v1.4.0-macos](https://github.com/adriantagonist87/VoxDrop/releases/tag/v1.4.0-macos) separat veröffentlicht. SHA-256: `78a957a4f735a530a2fbf3062fd10959319dea32c2de7fedd5b787e73c2d0fba`. Die schreibgeschützt eingehängte DMG enthält die gültige Signatur, alle 43 bytegleichen Programmdateien und beide Quellarchive; Info.plist, Launcher und Signaturkatalog stimmen mit der produktiven Installation überein. Der erneute öffentliche Downloadnachweis steht in `releases/v1.4.0/macos-verification.json`. Keine neue Betriebssystem-Neustart-/Anmeldeabnahme und keine wochenlange Echtzeitprüfung behauptet. Der bestehende Anmeldestart bleibt erhalten; ein Rechnerneustart wird nicht ungefragt ausgelöst.

Beim ersten Windows-CI-Lauf hielt der neue Mac-Test seine Numpy-Memorymap in den Mock-Argumenten fest; `reset_mock()` gibt sie nun vor Windows-Tempbereinigung frei. Beim Paketprüfer wurde die getrennte Darstellung von aktuellem Auftrag und Queue sowie die beabsichtigte Inhaltswiederverwendung korrekt berücksichtigt. Auf SMB entfernt macOS AppleDouble-Begleitdateien teils zusammen mit der Hauptdatei; die Bereinigung des ausschließlich eigenen Testordners toleriert bereits entfernte Begleitdateien. Diese Testtreiberbefunde ändern keine persönlichen Dateien oder die produktive Windows-Ausgabe.

Die abschließenden Paket-/Ausfallprüfer warten zusätzlich ausdrücklich auf die Phase „Transkribieren (Qwen)“ nach dem Modellladen. Auch dieser gezielte Lauf bestand: echtes QML-Stopp in 0,892 s, keine verwaisten Prozesse nach Dienst-SIGKILL, vollständiges Ende nach GUI-Verlust trotz SQLite-Schreibsperre in 6,167 s und erfolgreiche anschließende Wiederaufnahme.
