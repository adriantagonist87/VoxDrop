# Windows-Neuinstallation und Produktivabnahme am 18.11.2026

Status: **IN ARBEIT**, noch keine vollständige Abnahme. Dieser Bericht ergänzt die historischen Vorprüfungen und deren exakte Code-SHAs.

## Auftrag und Nutzungsumfang

Vollständige Bereinigung, neue Installation direkt von GitHub, Funktionsprüfungen im Arbeitsablauf und Veröffentlichung der Ergebnisse sind beauftragt. Meetings sind jeweils deutschsprachig oder englischsprachig. Beide Sprachen werden getrennt mit/ohne Stilleüberspringen geprüft. WIN-05 bleibt als synthetischer Mischsprachenbefund technisch offen, ist für diesen Nutzungsumfang aber kein Abnahmekriterium.

## Installationskandidat

- [GitHub-Prerelease v1.3.2-windows-preview.1](https://github.com/adriantagonist87/VoxDrop/releases/tag/v1.3.2-windows-preview.1).
- Asset `VoxDrop-1.3.1-Windows-Test-dbfcf833ef80.zip`: 45.704.396 Byte, plus `.sha256`.
- App-Code `dbfcf833ef80617929101e321decac3219e76291`.
- SHA-256 `be0bcba6711ba6c45b90f3b3f09b7920a8c62b01ef912cc23145adb3bf62555a`.
- Interne Version weiterhin 1.3.1; der Preview-Tag bezeichnet den neueren Windows-Fixstand. Keine stabilen Assets ersetzt, Preview nicht als neuestes stabiles Release markiert.
- ZIP-Integrität, `build-info.json` und alle 29 enthaltenen eigenen Desktop-/Engine-/Windows-Dateien gegen den Code-Commit geprüft. Keine Abweichung nach Zeilenendennormalisierung des Builders. Spätere Branch-Änderungen enthalten nur Dokumentation und einen Messprüfer.
- GitHub bestätigt Assetgröße und denselben Digest. Erneuter Download/frische Einrichtung folgen separat.

Ein erster privater Archivprüfer behandelte Verzeichniseinträge als Dateien. Erst der korrigierte Dateivergleich bestand; Prüftreiberfehler, kein Appfehler.

## Bestand und Schutz

Private Liste erfasst aufgelöste Installationspfade, Größen, Prozesse, Profile, Autostart und freien Speicher. Eindeutige VoxDrop-App-/Laufzeitbestände belegen vor Bereinigung rund 46 GiB. Ein separates älteres Skriptwerkzeug bleibt bis zur Nutzerentscheidung geschützt. Gemeinsame Caches, Git-Anmeldung, Entwicklungsquellen, Originalmedien und produktive Transkripte werden nicht pauschal gelöscht. Persönliche Pfade, Einstellungen, Datenbanken und Logs bleiben außerhalb GitHub.

## Abnahmefälle

| Fall | Status |
| --- | --- |
| Sicherung, Bereinigung und Speicherfreigabe | OFFEN |
| GitHub-Neudownload, Prüfsumme, normale EXE-Ersteinrichtung | OFFEN |
| Neue Modelle und Laufzeit vollständig im App-Ordner | OFFEN |
| Deutsch/Englisch getrennt, Qwen/Whisper, lange Pausen | OFFEN |
| Sprecher/DOVER, sequenzielle Modellbelegung und VRAM-Freigabe | OFFEN |
| Lokale/SMB-Überwachung, Pause, Rekursion und Ausfälle | OFFEN |
| Sichtbare Bedienung, Explorer-Drop, Fenster/Infobereich, Verlauf | OFFEN |
| Dateischutz, Kollisionen, Neutranskription und Wiederaufnahme | OFFEN |
| Tatsächlicher Windows-Neustart/Anmeldestart | OFFEN |
| Tatsächlicher Sleep/Resume | OFFEN |
| Produktive Ordner und Endeinstellungen | OFFEN |

Wochenlanger Betrieb braucht einen entsprechenden Beobachtungszeitraum. Gemeinsame Änderungen bleiben **UNGEPRÜFT unter macOS** und im Draft-PR #1. Mac-Prüfstand `df207f79aa812f70d090e4306443436d51d48952` bewahren.
