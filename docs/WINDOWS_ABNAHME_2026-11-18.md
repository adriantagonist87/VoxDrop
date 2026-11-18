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

### Bereinigung und erster Neuinstallationslauf

40 exakt zugeordnete App-/Testverzeichnisse entfernt; danach keine dieser Installationen, keine eigenen laufenden App-Prozesse und kein alter VoxDrop-Run-Eintrag vorhanden. Einstellungen/Verlauf und kleine Testzusammenfassungen sind privat mit Hashvergleich gesichert (154,161 MiB); keine Modell-/Laufzeitkopien gesichert. Zusätzlich hat der Nutzer das separate ältere Skriptwerkzeug zur vollständigen Entfernung freigegeben; dessen kleine Quellen bleiben privat gesichert (101.009 Byte). Freier Speicher vor neuer Einrichtung: C: +30,93 GiB; D: rund +8,27 GiB einschließlich des zusätzlichen Werkzeugs. Logische Dateigrößen und freigegebene Blöcke unterscheiden sich unter anderem durch Hardlinks und Dateisystembelegung.

Preview 1 erneut direkt von GitHub heruntergeladen und SHA-256 gegen heruntergeladene Prüfsummendatei sowie veröffentlichten Digest geprüft. Frisches Entpacken, fehlende Laufzeit/Modelle/Profil vor Start belegt. Unveränderte EXE richtete Python 3.12.13 und 128 gesperrte Abhängigkeiten neu ein. Python-Mirror-Fallback auf GitHub erfolgreich. Sichtbares QML-Fenster mit leerem Profil und richtigem Modellspeicher bestätigt. Beim Modelldownload echter 10013 und sichtbare Sicherheitsabfrage; Nutzer erteilte die Freigabe selbst. Tatsächlicher anschließender Download von Qwen, Aligner und Sprechergewichten abgeschlossen; Oberfläche meldet Modelle installiert. Keine Schutzregeln automatisiert geändert.

### WIN-08: veraltete Verweigerungsanzeige beim laufenden Retry

Während nach Nutzerfreigabe bereits große Modelldateien heruntergeladen wurden, blieb die Verweigerungsanzeige aktiv. `retry_network_permission` setzte den Wartezustand erst nach vollständiger Modelleinrichtung zurück. Jetzt wird er vor dem tatsächlichen Wiederholungsversuch gelöscht; erneute Verweigerung setzt ihn wieder. Die neue Regression schlägt am bisherigen Code fehl und besteht nach der Korrektur. Ein Sandbox-Test hatte zusätzlich einen separaten temporären Zugriffsfehler; nativer Wiederholungslauf bestätigte ausschließlich die erwartete fehlgeschlagene neue Regression. Danach fünf gezielte Tests bestanden. Vollständige native Windows-Suite: 92 Fälle, 85 bestanden, sieben explizite Skips, 15,160 s. Paketprüfung der Korrektur folgt. Gemeinsame Änderung **UNGEPRÜFT unter macOS**.

Künstliche getrennte Sprachfixtures: Deutsch 40,367 s, Englisch 37,026 s, je 20 s eingefügte Pause. Wiederholbare Erzeugung und Sprach-/Zeitmarkenprüfung liegen unter `scripts/`; sie verwenden installierte SAPI-Stimmen und veröffentlichen keine persönlichen Medien.

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
