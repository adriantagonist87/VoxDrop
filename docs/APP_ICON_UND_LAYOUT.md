# Neues App-Icon und Fenster ohne Logo-Kopfzeile

Nutzerauftrag vom 18.11.2026: bereitgestellte grüne Audio-/Video-/CC-Vorlage für App-/Dock-/Taskleistensymbol und GitHub übernehmen; die gesamte Logo-/Namens-/Untertitelzeile im Fenster entfernen. Windows-Infobereich und Mac-Menüleistenstatus bleiben unverändert.

## Ausgeliefert und geprüft

[Windows Preview 10](https://github.com/adriantagonist87/VoxDrop/releases/tag/v1.3.2-windows-preview.10), App-Code `4e565d426167b55a900a2c35d449ae0f29a98493`, ZIP-SHA-256 `4bcdc831057c93227530f73a08b553c4a725a78962945097dc3dd91cb0bd6e0d`. ZIP `VoxDrop-1.3.1-Windows-x64-4e565d426167.zip`, 45.678.820 Byte. Interne Version weiterhin 1.3.1, Laufzeit und Modelle unverändert. Windows installiert; Mac-Quellstand vorbereitet, nativer Mac-Build und Dock-Prüfung ausstehend. Die bisherigen Modell-/Queue-/Suchprüfungen behalten ihre jeweiligen exakten Code-SHAs.

| Datei | Verwendung |
| --- | --- |
| `macos/VoxDropLogo.png` | Unveränderter 1254×1254-PNG-Master aus dem Nutzeranhang; SHA-256 `04fa9e563491c2a45667e4620eee4a9784b4083a1737e1961eafc82a1b570dc7` |
| `assets/VoxDrop.ico` | Windows-Icon mit 16, 24, 32, 48, 64, 128 und 256 Pixel; SHA-256 `418a997a1dad0905851361409c0401bc79f78ef53c3823587a79b513ff9ae72e` |
| `docs/images/voxdrop-icon.png` | 256-Pixel-Vorschaubild im GitHub-README |
| `macos/AppIcon.swift` | Bestehende 1×-/2×-Iconset-Erzeugung für `AppIcon.icns`; Vorlage füllt die Bildfläche ohne die frühere zusätzlich gezeichnete Kachel |
| `desktop/qml/Main.qml` | Gesamter 74-Pixel-Header entfernt; Inhalt beginnt oben, nativer Fenstertitel weiterhin VoxDrop |

Die PNG-Vorlage bleibt bytegleich, einschließlich ihrer gelieferten weißen Ränder und Farben. ICO und README-Bild sind Größen-/Formatableitungen, keine Neuzeichnung. `desktop/desktop.py` verwendet das neue PNG weiterhin als Qt-App-/Fenstersymbol; der Windows-Launcher enthält das neue ICO. Die bisherigen Statussymbole werden separat durch `controller.waveform` gezeichnet. Controller und Desktop-Einstieg sind zu Preview 9 bytegleich; Menüleisten-/Infobereichsstatus wurden nicht ersetzt.

## Korrigierter Buildpfad

Der native Windows-Builder übernahm bislang das alte ICO aus dem geprüften Referenz-ZIP. Er übernimmt jetzt `assets/VoxDrop.ico` aus dem aktuellen Checkout und bettet dessen Bilder in die EXE ein. Der Mac-basierte Windows-Builder kopiert dieselbe ICO-Datei und verwendet sie für die Ressourcen. Vendor-/aTrain-/uv-Referenzprüfungen bleiben erhalten. Der Mac-Build verwendet weiterhin `macos/AppIcon.swift` und `iconutil`; `CFBundleIconFile=AppIcon` bleibt bestehen. Alle Änderungen stehen im [Aufgabenbranch](https://github.com/adriantagonist87/VoxDrop/tree/fix/windows-native-validation).

## Nachweise unter Windows

- 15 bestehende vollständige Qt-Bedienfälle in 5,972 s bestanden: Queue, Drag-and-drop, gefiltertes Menü, Suchfelder, Detailsuche, Drop-Konfliktpopup, Verlaufszähler, TXT-Öffnung und Fensterverhalten. Kein neuer Test, der nur das entfernte Markup nachbildet.
- Such-/Konfliktansichten bei 1500×1000 und 1010×630 gerendert und visuell geprüft. Ganze Logo-Kopfzeile entfällt, 74 Pixel mehr Inhaltshöhe. Lange Namen/enge Spalten bleiben bedienbar.
- Fertiges Paket über `VoxDrop.exe --background` in isoliertem Profil gestartet. Echte Windows-Ressourcen-API bestätigt alle sieben eingebetteten Icon-Bilder und die Icon-Gruppe bytegenau gegen das neue ICO. Qt-App-Icon geladen; `header` leer und Content-Y=0 bestätigt.
- Alle vier relativen Queueaktionen, Vor-/Nach-Anker mit ausgeblendeten Nachbarn und tatsächlicher gefilterter QML-Mausklick mit Änderung der echten SQLite-Reihenfolge bestanden. Gesamter Paketprüflauf 8,712 s; Pause/Identitäten/SQLite/Fremdschlüssel erhalten.
- Alle 32 Engine-Dateien, Desktop-Controller und Desktop-Einstieg bytegleich zu Preview 9. Die vollständige 135-Fälle-Suite bleibt auf `c434d5c4921873d387cefc8cdc55f23f201e61de`, die echte DE-/EN-CUDA-/Unterbrechungs-/Inhaltssuchprüfung auf `d40b00526494155979d19d6b0b67fcf1853d618f` dokumentiert. Keine erneute CUDA-Abnahme für diese Icon-/Layoutänderung behaupten.
- Geändertes Windows-Cross-Buildskript mit `bash -n` geprüft. Mac-Swift-/ICNS-Erzeugung und sichtbares Dock-Verhalten sind damit nicht nativ geprüft.

## Installiertes Update und GitHub

Direkter GitHub-Download mit SHA-256; konsistente SQLite-/Einstellungssicherung und hashgeprüfte vorherige Codekopie. Alle 88 installierten Paketdateien identisch. Nur GUI neu gestartet; Supervisor-/Dienst-PIDs samt Erstellungszeit erhalten, Modelle/Laufzeit und aktuelle Nutzerordner unverändert. Windows gezielt über die geänderten VoxDrop-EXE-/ICO-Dateien benachrichtigt; kein globaler Iconcache gelöscht und Explorer nicht neu gestartet. Installierte GUI über Accessibility bestätigt: alter Kopfzeilenuntertitel fehlt, Such-/Queue-/Verlaufselemente vorhanden.

Zum Zeitpunkt unmittelbar vor diesem Update enthielt das aktuelle Profil bereits null Aufträge und eine nicht pausierte Queue; derselbe Zustand ist danach erhalten, SQLite/Fremdschlüssel `ok`. Frühere Abnahmesicherungen mit 9.385 Aufträgen sind historische Stände und werden nicht über den aktuellen Nutzerzustand zurückgespielt. Bestehender Suchcache bleibt erhalten. Das Update führt keine Verlaufslöschung oder neue Transkription aus.

GitHub-README-Vorschaubild und die drei Icon-Dateien auch auf `main` aktualisiert; README verlinkt die aktuelle Windows-Vorabversion ausdrücklich. Funktionale Änderungen einschließlich entferntem QML-Header und geändertem Mac-Icongenerator bleiben bis nativer Mac-Gegenprüfung im [Draft-PR #1](https://github.com/adriantagonist87/VoxDrop/pull/1). Bestehende stabile Releases und die installierte Mac-App wurden nicht überschrieben.

## Übergabe an Codex am Mac

`git fetch origin`, aktuellen PR-Branch prüfen; bisherigen nativen Mac-Prüfstand `df207f79aa812f70d090e4306443436d51d48952` bewahren. Mit `sh scripts/build-app.sh` Iconset/ICNS neu erzeugen, normales Bundle/Codesign und isolierten Cocoa-Start prüfen. Dock-/Finder-/App-Umschaltericon mit Vorlage vergleichen, Menüleisten-Statuswellen weiterhin grün/rot prüfen. Die Oberfläche muss ohne eigenen Logo-Header starten; Mindestgröße, lange Namen, neue Such-/Dropdialoge und alle vorherigen gemeinsamen Funktionen nativ gegenprüfen. Beim beauftragten Mac-Update vorhandene Modelle/Einstellungen bewahren und tatsächliche Dock-/LaunchServices-Aktualisierung bestätigen. Windows-Prüfung ersetzt diese Cocoa-Abnahme nicht.
