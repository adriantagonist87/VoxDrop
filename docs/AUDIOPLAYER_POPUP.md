# Kompakter Player als eigenes Popup

## Bedienung seit 23.11.2026

Die Detailansicht zeigt keinen eingebetteten Player mehr. **Originaldatei abspielen** öffnet den Player als separates kompaktes Popup und startet die Tonspur. Die waagerechte Leiste übernimmt die Bedienanordnung der Vorlage im **dunklen App-Stil**: Play/Pause, dünne dezent grüne Regler mit schmalen Griffen, aktuelle Zeit/Gesamtdauer, Geschwindigkeit zwischen zwei Pfeilen und Lautstärke. Die sichtbaren Griffe sind schmal; unsichtbare Bedienflächen von 28 × 32 logischen Pixeln erleichtern das Ziehen. Der Lautsprecherknopf schaltet stumm; die Lautstärkeeinstellung bleibt erhalten. Aufnahmen mit Stundenlänge behalten die Stundenanzeige.

Beim Ziehen des Zeitbalkens zeigt die Leiste die gewählte Zielposition an. Laufende Fortschrittsmeldungen überschreiben diese Vorschau nicht. Erst beim Loslassen wird genau ein Seek ausgeführt; die Oberfläche schickt nicht für jede Mausbewegung eine neue Decoderanforderung. Klick auf die Strecke sowie Tastatur/Accessibility bleiben möglich. Pfeiltasten bewegen den Zeitregler in Sekundenschritten.

Ein **Klick außerhalb** oder **Escape** schließt nur den Player, beendet die Wiedergabe und gibt die Medienquelle frei. Die Details bleiben offen; derselbe Button öffnet den Player erneut. Details wechseln/schließen oder die App beenden schließt ihn ebenfalls. Während einer Dateiprüfung geschlossener Player darf später durch deren Antwort keine Wiedergabe mehr starten. Fehlende Dateien/Tonspuren bzw. Decoderfehler werden weiterhin behandelt; die sechs Dateiaktionen bleiben in den Details unabhängig vom Jobstatus erhalten.

Geschwindigkeit: **0,5× bis 3×** über die Pfeile. Qt-Tonhöhenkorrektur ist ausdrücklich eingeschaltet; auf einem Backend ohne diese Funktion sind Geschwindigkeitsänderungen deaktiviert. Es wird kein beschleunigter Modus mit veränderter Stimme als Ersatz angeboten. Maßgebliche Bibliotheksfunktion: [Qt 6.10 QMediaPlayer.pitchCompensation](https://doc.qt.io/qt-6.10/qmediaplayer.html#pitchCompensation-prop).

## Implementierung und Git-Stand

Geprüfter Funktionscode **`6f0bb63d1afd843d5bacb9f1ef63026d23adca49`**, Branch [`feat/popup-audio-player`](https://github.com/adriantagonist87/VoxDrop/tree/feat/popup-audio-player), [PR #29](https://github.com/adriantagonist87/VoxDrop/pull/29). Ausgangspunkt `e74a65a04353d9ae876be9916c717cc6eaba35d9`. Der Branch enthält als Voraussetzung die vorhandene Playerimplementierung aus PR #20, ursprünglicher Code `6278335acb6589a97b4973c26cf0e931fb5ac369`, hier unverändert als `3f28818aef8d13c1b3be44d72a241c1c59028a90` übernommen. Anschließend wird deren Bedienung ersetzt. Beim Plattformabgleich diesen PR als Weiterentwicklung von #20 behandeln, statt dieselbe Playerbasis doppelt einzuspielen.

`Main.qml` enthält den separaten modalen `Popup` mit `CloseOnPressOutside | CloseOnEscape`. `AudioPreview.qml` rendert nur dessen kompakte Steuerelemente. Öffnen/Schließen läuft über eigene Controllersignale und `closeAudioPreview`; eine zusätzliche Anforderungsgeneration verwirft verspätete Play-Antworten. Die Detailgeneration und die anderen Dateiaktionen bleiben getrennt. `audio_preview.py` verwendet weiterhin lazy `QMediaPlayer`/`QAudioOutput`, ohne Video-/Hardwaredecoding oder Inferenz; neu sind `setPlaybackRate`, ausdrücklich aktivierte Tonhöhenkorrektur und Stummschaltung. Direkte Quellfreigabe statt des früher unter Windows blockierenden Qt-`stop()` bleibt erhalten.

Keine neue Abhängigkeit gegenüber dem bestehenden Player-Prüfstand, keine Modell-/Python-/Torch-/Qt-Pin- oder Datenbankschemaänderung. Ein frischer Checkout braucht weiterhin die bereits mit PR #20 eingeführten Qt-Addons 6.10.2. Keine neue Runtime und kein Modelldownload für das lokale Update. Die ursprünglichen Lizenzhinweise bleiben erhalten.

## Tatsächliche Windows-Prüfungen

Python 3.12.13, Qt/PySide 6.10.2 unter Windows 11. [Bereinigter Prüfnachweis](pruefungen/2026-11-23-windows-popup-player.json).

Der [Windows-Pflichtcheck des abschließenden funktionalen Commits](https://github.com/adriantagonist87/VoxDrop/actions/runs/45165205452) ist erfolgreich; er prüft auch das Popup im 8.000-/20.000-Aufträge-Workspace.

- **44 gezielte Audio-/Qt-Fälle in 16,743 s: 43 bestanden, ein Cocoa-Skip.** Neue Regressionen zu echter tonhöhenkorrigierter Rate, Grenzen/ungültigem Wert, Backend ohne Korrektur, Stummschaltung, Außenklick/Escape, verspäteter Dateiprüfung und stabiler Drag-Vorschau mit genau einem Seek beim Loslassen. Vorhandene Dateiverfügbarkeits-/Accessibility-/Start-/Stoppfälle erhalten.
- Finaler kombinierter Stand mit Player, SMB-Fix `f43e27fdf74dda4b1a492513cc548b9f7a4a54f1`, Download `79d42538022573fc32d6927115c99ebf3c4dc9c3` und Überwachungs-/Stoppsteuerung `5405d8e365171e6cecbc636c586fba866b0a7f87`: **286 Fälle in 167,670 s, 274 bestanden/zwölf bekannte Plattform-Skips**.
- Native Windows-QML bei **1010 × 630** und **100/125/150 % Qt-Skalierung**: Details anfangs ohne Player, echtes Öffnen über den Button, sämtliche Bedienelemente innerhalb des Fensters, dünne Regler, Maus-Seek, Geschwindigkeitsknöpfe, Lautstärke/Stumm, Außenklick/Escape mit weiterhin offenen Details, erneutes Öffnen, Detailwechsel und Dateifreigabe bestanden. Echte WAV-, FLV- und OPUS-Dateien; Video deaktiviert. Nach Schließen lässt sich die zuvor geöffnete Datei umbenennen.
- Bei 1× lief die Zeitposition im 900-ms-Test ungefähr **1,04×**, bei 2× ungefähr **1,98–2,07×** weiter. Qt meldete die Tonhöhenkorrektur als verfügbar und eingeschaltet. Die Tests liefen mit Lautstärke null; kein akustischer oder spektraler Endpunktvergleich und keine Aufzeichnung anderer Systemtöne behauptet. Keine Transkription gestartet, keine KI-Modelle geladen.

Die erste weiße/rote Variante übernahm die Vorlage auf Nutzerkorrektur zu wörtlich. Die endgültige Leiste verwendet die App-Farben, drei Pixel dünne Regler und schmale Griffe mit größeren Bedienflächen. Dabei wurde das fortlaufende Senden von Seek-Aufrufen beim Ziehen durch Vorschau und einen abschließenden Aufruf ersetzt. Eine anfängliche Patchoperation war vor jeder Dateimutation wegen einer doppelten Dateioperation abgewiesen und unmittelbar korrekt erneut ausgeführt worden. Keine produktiven Daten betroffen.

## Lokaler Entwicklungsstand

Das Update ist lokal installiert: insgesamt **vier Desktopdateien** (`audio_preview.py`, `controller.py`, `Main.qml`, `AudioPreview.qml`) ausgetauscht; die übrigen **97 vorherigen Programmdateien** erhalten. Die abschließende dunkle Gestaltung/Drag-Korrektur änderte davon nur die beiden QML-Dateien; in diesem Schritt blieben 99 vorhandene Programmdateien erhalten. Controller/Haupt-QML kombinieren die neue Bedienung ausdrücklich mit Downloadfortschritt und Überwachungs-/Stoppsteuerung. Profil und alter Code gesichert; Einstellungen, Jobs, Queuepositionen, bestehende Pause, Modelle und Runtime erhalten. Normale EXE neu gestartet und lebenden registrierten GUI-Eigentümer bestätigt. Anschließend die tatsächlich installierten Dateien mit demselben nativen WAV-/FLV-/OPUS-Klickablauf erneut erfolgreich geprüft; kein produktiver Auftrag als Test gestartet oder abgebrochen.

Basis bleibt Paket 1.5.1 mit Code `6278335acb6589a97b4973c26cf0e931fb5ac369`. `local-development.json` enthält sämtliche Overlay-Commits und die aktuellen Dateihashes, `build-info.json` weiterhin die Basis. **Kein Release und kein neues öffentliches Build.** Bestehende Downloads unverändert.

## Mac-Gegenprüfung

Neue Popup-/Geschwindigkeitsbedienung **UNGEPRÜFT unter macOS**. Mac 1.5.0 Build 27 bleibt bestätigt; gemeinsamer Funktionscode bis zur Gegenprüfung in PR #29. `main` erhält nur die beauftragte reine Dokumentationsübergabe.

1. Playerbasis samt Qt-Addons und diesen neuen Popupstand bewusst aus PR #29 übernehmen; die übrigen offenen SMB-/Download-/Überwachungs-PRs berücksichtigen.
2. Native Wiedergabe von WAV/OPUS/Videoaufnahmen prüfen. Qt-Backend muss Pitch-Korrektur unterstützen/aktivieren; 0,5–3×, Play/Pause, Seek, Lautstärke/Stumm, Stundenanzeige sowie Decoder-/Netzfehler testen. Bei fehlender Korrektur keine veränderte Tonhöhe zulassen.
3. Außenklick/Escape schließt ausschließlich den Player und gibt die Datei frei; Details bleiben offen. Erneutes Öffnen, langsame/verspätete SMB-Prüfung, Detailwechsel und Cmd-Q dürfen keine verspätete Wiedergabe hinterlassen. Mindestfenster/Retina, Tastatur und alle sechs Dateiaktionen erhalten.

Gezielt: `python -m unittest discover -s tests -p test_audio_preview.py` und `test_desktop_window.py`, vollständig über den bestehenden gepinnten Windows-CI-Weg. Der Workspace-Test rendert zusätzlich das neue Popup. Keine zusätzliche physische Windows-DPI-, ASR-/GPU-, Neustart-/Autostart-, Deinstallations- oder mehrwöchige Dauerabnahme in diesem Bedienungsschritt.
