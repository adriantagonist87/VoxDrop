# macOS auf dem gemeinsamen Stand 1.4

Ausgangsbasis: `2e493e973c9f24ed3b46e44c45f31f7801398217` aus `origin/main`, Windows-Paketcode `48ff35f43f07c07b4b7abd0b22561c9096fbe1cc`. Auftrag vom 21.11.2026: sämtliche aktuellen Windows-Funktionen und die neue Oberfläche auf dem Mac mini produktiv bereitstellen. Die vorhandene Mac-Installation war 1.3.1 / Build 23; Konfiguration, Verlauf, Modelle und Anmeldestart werden erhalten.

## Mac-Anpassungen

- Gemeinsame QML-Arbeitsübersicht, stabile Listen, Suche, Konfliktdialoge, globale Queue und Play/Stopp unverändert übernommen.
- Qwen-MLX lädt ASR und Forced Aligner nacheinander. Erst werden die Erkennungsergebnisse gesammelt, dann ASR-Referenzen und MLX-Cache freigegeben, anschließend wird ausgerichtet. Audioabschnitte und Zeitrechnung bleiben erhalten. Whisper wird bereits vor der Sprecherpipeline geschlossen.
- GPU-Budget auch auf Metal: temporäre Instanztypen an MLX-Audioencoder und Textdecoderblöcken evaluieren die Ergebnisse vor Synchronisation/Pause. CTranslate2-Metal delegiert seine synchronen nativen Aufrufe. Beide pyannote-Modelle erhalten MPS-Hooks. CPU bleibt ohne GPU-Pausen. Modellpräzision und Erkennungsparameter bleiben gleich; kein exaktes systemweites Last- oder RAM-Limit.
- `posix_guard.py` besitzt die jeweilige Unix-Prozessgruppe. Das Schließen der nur beim Eigentümer gehaltenen Pipe beendet die Gruppe auch nach hartem Eigentümerabsturz. Ausgabe/Exitcode bleiben erhalten. Der vorhandene Supervisor, begrenzte Logs und automatische Auftragswiederaufnahme gelten nun auch auf dem Mac. Temporäre Audiodaten liegen auf beiden Systemen im bereinigbaren Auftrag.
- Der Owner-Watchdog merkt PID und Erstellungszeit, damit eine später gesperrte SQLite-Datenbank die Eigentümerverlust-Erkennung nicht unterbindet. Profile werden weiterhin getrennt beendet.
- Cmd-Q läuft über einen Qt-Quit-Eventfilter in den vorhandenen vollständigen Abschluss. Rotes X bleibt Ausblenden in die Menüleiste; Minimieren bleibt Dock.
- Nativ reproduzierter Cocoa-Fehler: nach Maximieren → Vollbild → Minimieren wurden `Minimized → Windowed → Maximized → Minimized` gemeldet. Der gespeicherte Vollbildmodus wird während dieses Übergangs festgehalten und nach der nativen Wiederherstellung bestätigt. Bewusstes anschließendes Normalisieren bleibt wirksam.
- Lokale offene Schreibhandles werden mit dem vorhandenen macOS-`lsof` erkannt, auch ohne weiteres Größenwachstum. Ein auf einem anderen SMB-Client offener Schreiber ist damit nicht nachgewiesen; Dateiversions-/Kopier-/Veröffentlichungsschutz bleibt zusätzlich aktiv.
- Der Installer wartet auf einen tatsächlich laufenden aktiven Auftrag, beendet auch Supervisoren und startet anschließend den nativen App-Eigentümer. Ein verwaister DB-Zustand ohne laufenden Dienst blockiert das Update nicht.
- Optionaler Build aus einer vorhandenen signaturgeprüften Bundle-Laufzeit; kritische Python-/Torch-/Qt-/MLX-Pins werden erneut geprüft. Keine neuen Abhängigkeiten, Modelle oder Lockfileänderungen. `build-info.json` enthält Code-SHA, Entwicklungskennzeichnung und Hashes aller 43 eigenen Paketdateien. Die DMG enthält den genauen eigenen Quellstand und den aTrain-Pin.

## Bereits ausgeführte Prüfungen

macOS 27.2, Apple Silicon, Python 3.12.13, Qt 6.10.2, MLX 0.32.4 / MLX-Audio 0.6.5, Torch 2.9.1, CTranslate2-Metal 4.9.0. Nur isolierte Profile und synthetische Medien; vorhandene lokale Modelle weiterverwendet.

| Prüfung | Ergebnis |
| --- | --- |
| Gemeinsame Regressionen | 207 Fälle in 41,680 s, 199 bestanden, acht explizite Skips: sieben Windows-Adapter und eine nur nativ ausführbare Cocoa-Regression. |
| Native Fenster-/Modellregressionen | Zehn engere Fälle auf Cocoa bestanden. Erweiterte Maximieren-/Vollbild-/Minimierungsfolge zusätzlich im Paketprüfer. |
| Große native Oberfläche | 8.000 Queue- und 20.000 Verlaufseinträge bei 100/125/150 % Qt-Skalierung; Mindestfenster, alle Einstellungsgruppen, Details, Menüs und Dialoge; keine QML-Warnungen. |
| Inhaltsindex | 20.000 synthetische TXT, 206 erwartete Treffer, keine übersprungenen Dateien, Abbruch bestanden. Indexieren/Suchen 0,829 s; einschließlich Schreiben 1,888 s. Ein lokaler Einzellauf, keine SMB-Leistungszusage. |
| Modellmatrix | Zwölf echte Metal-Läufe: beide ASR-Modelle × getrennte deutsche/englische Aufnahmen × 100 %, 50 %, 50 % mit Stille und drei DOVER-Durchgängen. Textanker, ursprüngliche Zeitlinie nach zwölf Sekunden Pause und Originalhashes bestanden. Je Sprache/Modell waren die Transkripte bei 100/50 % ohne Stilleoption bytegleich. |
| Normale native App | Swift-Bundle-Einstieg mit isoliertem Profil geöffnet; Oberfläche und Einstellungen visuell geprüft, Metal-Budget per Tastatur gespeichert. Tatsächliches Cmd-Q leitete vollständigen Abschluss ein; GUI, Supervisor und Dienst danach beendet. |

Die 100-%-Sprachläufe dauerten auf den rund 25–28 Sekunden langen Testaufnahmen 2,5–3,9 Sekunden. Mit 50 % und Sprecher/DOVER lagen sie bei 13,5–22,5 Sekunden. Diese kurzen künstlichen Aufnahmen sind keine neue Langaufnahme-/RAM-Benchmarkserie. Die alten README-Benchmarks bleiben historische Messungen.

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

## Noch laufender Abschluss

Vollständiger nativer Paket-/Wiederaufnahmeprüfer, Eigentümerverlust während echter Erkennung, Mac-SMB-Testablage, finaler Commit/Windows-CI, DMG, gesichertes Produktivupdate und öffentlicher Downloadnachweis werden im anschließenden Statusupdate eingetragen. Keine neue Betriebssystem-Neustart-/Anmeldeabnahme und keine wochenlange Echtzeitprüfung behauptet. Der bestehende Anmeldestart bleibt erhalten; ein Rechnerneustart wird nicht ungefragt ausgelöst.
