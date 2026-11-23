# Originalaufnahmen direkt im Verlauf anhören

Der Windows-Prüfstand 1.5.1 ergänzt den lokalen Audioplayer. Implementierung: [Branch `feat/history-media-player`](https://github.com/adriantagonist87/VoxDrop/tree/feat/history-media-player), [PR #20](https://github.com/adriantagonist87/VoxDrop/pull/20). Der gemeinsame Code bleibt gemäß dem plattformübergreifenden Übergabeauftrag bis zur Mac-Gegenprüfung im Pull Request. Mac 1.5.0 Build 27 bleibt der letzte nativ bestätigte Mac-Stand.

## Bedienung

Im Verlauf einen Vorgang öffnen und **Originaldatei abspielen** wählen. Seit dem [neuen Popupstand vom 23.11.2026](AUDIOPLAYER_POPUP.md) bleibt der Player zunächst verborgen und öffnet sich erst über diesen Button als kompakte waagerechte Leiste. Er bietet **Play/Pause**, einen verschiebbaren **Zeitbalken**, aktuelle Position/Gesamtdauer, **Geschwindigkeit mit Tonhöhenkorrektur** und **Lautstärke/Stumm**. Außenklick oder Escape schließt nur den Player und gibt die Quelle frei; die Details bleiben offen. Lange Aufnahmen zeigen auch Stunden. Die Lautstärke wird als App-Einstellung gespeichert. Details öffnen startet keine Wiedergabe; Schließen oder Wechseln der Details sowie App-Beenden gibt die Medienquelle frei. Die folgenden 1.5.1-Prüfungen beschreiben die ursprüngliche Playerbasis; der neue Popup-Prüfstand steht separat im verlinkten Dokument.

Für jeden Verlaufseintrag bleiben sechs Aktionen sichtbar:

1. **Originaldatei im Explorer anzeigen** (Mac: Finder)
2. **Originaldatei abspielen**
3. **Transkript im Explorer anzeigen** (Mac: Finder)
4. **Transkript öffnen** mit der Standardanwendung des Betriebssystems
5. **Neu transkribieren**
6. **Schließen**

Die vorhandene Aktion **Erneut versuchen** bleibt zusätzlich bei passenden Fehlerzuständen erhalten. Dateiverfügbarkeit wird unabhängig vom Verarbeitungsstatus geprüft. Damit sind Originalaufnahmen auch nach abgebrochener Verarbeitung oder „Stille-Erkennung hat keine Sprache gefunden“ erreichbar. Fehlende Dateien deaktivieren ihre Aktionen mit Erklärung; ohne TXT wird kein Transkript vorgetäuscht. Eine vorhandene TXT ist auch bei einem Fehlerstatus zugänglich. Neutranskription folgt weiterhin den vorhandenen Zustands- und Dateischutzregeln.

## Umsetzung und Grenzen

`AudioPreview.qml` bindet `audio_preview.py` an. `QMediaPlayer`/`QAudioOutput` werden erst bei Wiedergabe erzeugt. Es werden keine Sprach-/Sprechermodelle und keine Inferenzprozesse gestartet. Videospuren und Hardwaredecoding sind für diese Vorschau deaktiviert. Die lokale Originalaufnahme wird weder konvertiert noch als zusätzliche Audiodatei im Profil gespeichert. Qt puffert nur während der Wiedergabe.

`detail_files.py` berücksichtigt Originalort, vorhandenen Archivort, bekannte TXT-Pfade und die eigenen Ausgabedateien einer Neutranskription. Die Prüfung läuft in einem appgebundenen CLI-Prozess mit acht Sekunden Kommunikationszeitlimit. Ein nicht erreichbarer Netzordner darf die GUI nicht durch eine synchrone Dateiprüfung blockieren. Vor einer Dateiaktion wird erneut geprüft; verspätete Antworten nach Schließen/Wechseln dürfen keine Wiedergabe starten. Die eigentliche Medienwiedergabe verwendet den lokalen Qt-FFmpeg-Decoder. Nicht unterstützte/beschädigte Medien und fehlende Tonspuren werden im Player gemeldet. Ein später während der Wiedergabe ausfallendes Netzlaufwerk hängt auch vom Qt-Decoder und vom Betriebssystem ab und ist durch den lokalen Codec-Test nicht als SMB-Dauerbetrieb abgenommen.

Zusätzliche Abhängigkeit: **PySide6-Addons 6.10.2**, passend zu unverändertem Essentials/Shiboken. Windows-Lockfile und Mac-Anforderung mit Wheel-Hash sind aktualisiert; Modellpins und Datenbankschema bleiben erhalten. Unter Windows entsteht `Laufzeit/runtime-2ce5d3d2adcc` im App-Ordner; wiederverwendbare Pakete kommen aus dem bestehenden uv-Cache. Keine Modelle werden dafür erneut geladen. [Qt-/FFmpeg-Lizenzen und Quellcode](../desktop/Qt-Lizenzen.md).

## Windows-Prüfung vom 23.11.2026

Geprüfter funktionaler Code: **`6278335acb6589a97b4973c26cf0e931fb5ac369`**, Python 3.12.13, Qt/PySide 6.10.2, Windows 11 x64. [Dateimanifest](../releases/v1.5.1/windows-release.json) und [bereinigter Prüfnachweis](../releases/v1.5.1/windows-verification.json). ZIP-SHA-256: `6dfd45c54df6134fb5b37e2f281368b1ba7b388b740f8d2c9d0219426dca4a63`; 98 Programmdateien. Das eingefrorene Paket ist eine Windows-Vorschau, kein neuer Mac-Release.

- Vollständige Regression: **251 Fälle in 140,551 s; 239 bestanden, zwölf bekannte Plattform-Skips**. Wiedergabe verwendet einen realen Windows-Audioendpunkt, mit Lautstärke null im automatisierten Test.
- Reale synthetische WAV-, FLV- (mit Video und MP3-Tonspur) und OPUS-Dateien: Wiedergabe, Seek, abgeschaltete Videospur und Freigabe beim Schließen bestanden. Beschädigte Datei und lange Zeitanzeige separat geprüft.
- Aus dem gebauten Paket: natives Windows-Qt-Fenster bei 1010 × 630 mit langem Unicode-Dateinamen, sechs sichtbaren Aktionen, Play/Pause, Seek, Lautstärke, erneutem Öffnen, fehlender TXT und FLV/OPUS aus Fehlerzuständen bestanden. Die Datei lässt sich nach Schließen umbenennen; keine Transkription gestartet.
- Quellfenster tatsächlich bedient: Playerregler, Explorer-Auswahl der fehlgeschlagenen Originalaufnahme, TXT im Explorer und Öffnen mit der Standardanwendung. Normaler EXE-Start mit isoliertem Profil, drei künstlichen Verlaufseinträgen und appgebundenem Dienst bestätigt. Ein weiterer physischer Klickdurchlauf des EXE-Fensters war wegen Windows-Zugriffsverweigerung auf den Cursor nicht möglich; die Paketprüfung erfolgte mit dem nativen Qt-Testlauf. Diese Grenze wird nicht als erfolgreiche physische Bedienungsabnahme ausgegeben.
- Paketlayout: 8.000 Queue-/20.000 Verlaufseinträge, Mindest-/breites Fenster und Dialoge bei 100/125/150 % Qt-Skalierung erfolgreich. Dies bescheinigt keine zusätzliche physische Windows-DPI-Messung.

Reproduzierbare Tests mit der gepinnten Windows-Laufzeit: `python -BEs -Xutf8 scripts/ci-tests.py run` nach dem bestehenden CI-Prepare/Install; gezielt `python -m unittest discover -s tests -p test_audio_preview.py`, entsprechend `test_detail_files.py`/`test_desktop_window.py`/`test_process_lifecycle.py`. Für Layout: `python scripts/check-workspace-ui.py --app <entpacktes-Paket> --native --scale 1.5 --output <privater-Testordner>`. Ausschließlich isolierte Profile und künstliche Medien verwenden.

Das eingefrorene Paket wurde am selben Windows-PC bei leerem aktivem Slot installiert und alle 98 Programmdateien wurden gegen das Manifest geprüft. Der vorher aktive Auftrag wurde ohne Wiederanlauf regulär fertig. Profil und alter Programmstand wurden gesichert; Jobdaten, Queue-Reihenfolge, Konfiguration, Layout und Modellmetadaten blieben beim Kopieren gleich. Die neue Runtime verwendete den vorhandenen App-Cache und lud nur Addons zusätzlich; die alte Runtime bleibt für Rückkehr erhalten. Neustart über die normale EXE und lebender App-Owner bestätigt; die ausschließlich für das Update gesetzte Pause wurde aufgehoben. Das ist eine native Windows-Vorschau des Feature-PR, keine Mac-Freigabe und keine erneute mehrwöchige Dauerabnahme.

Nach Veröffentlichung wurde das ZIP nochmals von der öffentlichen GitHub-Downloadadresse geladen. SHA-256, alle 98 ZIP-Einträge und alle installierten Programmdateien stimmen mit dem Manifest überein. [Öffentlicher Downloadnachweis](../releases/v1.5.1/windows-public-verification.json). Feature- und Dokumentations-PR bestanden ihren jeweils aktuellen verpflichtenden Windows-Check; der reine Übergabestatus wurde über [PR #21](https://github.com/adriantagonist87/VoxDrop/pull/21) auf `main` integriert.

Gefundene Fehler während der Umsetzung: Qt 6.10.2 blockierte im nativen `stop()` nach Pause/Seek; direktes Leeren der Quelle beendet die Wiedergabe ohne diesen Aufruf. Die Regression prüft Stopzustand und freigegebenen Dateihandle. Die anfänglichen QML-Regler nutzten nur `onMoved` und übernahmen Accessibility-Wertänderungen nicht; nun reagieren sie idempotent auf Wertänderungen. Ein Testlauf hatte zusätzlich einen falsch platzierten Testabschnitt und eine durch kalte Prozesseenumeration abgelaufene 60-Sekunden-Prozessfixture; diese Testfehler wurden korrigiert, anschließend lief die vollständige Suite erfolgreich. Private Qt-Pakettests benötigen eine echte Ereignisschleife für die asynchronen Python-Worker; reine wiederholte `QTest.qWait`-Aufrufe waren dafür kein verlässlicher Testtreiber.

## Nächste Mac-Prüfung

1. PR #20 bewusst übernehmen und die Runtime mit dem aktualisierten `desktop/requirements-macos.txt` neu aufbauen. `--runtime-from` einer alten 1.5.0-App enthält Addons nicht; der Builder prüft den Pin und lehnt eine unvollständige Laufzeit ab.
2. Native Arm64-Wiedergabe von WAV/OPUS und typischen Videoaufnahmen prüfen: Play/Pause, Maus-/Tastatur-Seek, Lautstärke, Ende/Neustart, beschädigte/fehlende Medien, lange Aufnahme und Dateiname, Schließen/Wechseln/Cmd-Q.
3. Alle sechs Aktionen bei Erfolg, Fehler, Abbruch und Bestand sowie fehlender TXT prüfen; Finder markiert Original und Transkript, Standardanwendung öffnet TXT, geschützte Neutranskription bleibt korrekt.
4. Neue Bundle-Abhängigkeit, dynamische Bibliotheken/Lizenzen, Signatur, Mindestfenster/Retina und Offline-SMB prüfen. Erst nach dieser nativen Gegenprüfung den gemeinsamen Feature-PR integrieren und eine neue Mac-Freigabe dokumentieren. Die vorhandene 1.5.0-Abnahme bleibt unverändert.
