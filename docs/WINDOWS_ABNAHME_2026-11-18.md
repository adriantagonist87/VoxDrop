# Windows-Neuinstallation und Produktivabnahme am 18.11.2026

Status: **IN ARBEIT**, noch keine vollständige Abnahme. Dieser Bericht ergänzt die historischen Vorprüfungen und deren exakte Code-SHAs.

## Auftrag und Nutzungsumfang

Vollständige Bereinigung, neue Installation direkt von GitHub, Funktionsprüfungen im Arbeitsablauf und Veröffentlichung der Ergebnisse sind beauftragt. Meetings sind jeweils deutschsprachig oder englischsprachig. Beide Sprachen werden getrennt mit/ohne Stilleüberspringen geprüft. WIN-05 bleibt als synthetischer Mischsprachenbefund technisch offen, ist für diesen Nutzungsumfang aber kein Abnahmekriterium.

## Installationskandidat

- Maßgeblich: [GitHub-Prerelease v1.3.2-windows-preview.2](https://github.com/adriantagonist87/VoxDrop/releases/tag/v1.3.2-windows-preview.2).
- Asset `VoxDrop-1.3.1-Windows-x64-c86746f8cc98.zip`: 45.704.551 Byte, plus `.sha256`.
- App-Code `c86746f8cc98c2dce75fb95bd489563591640f9a`.
- SHA-256 `3841a6ebcb882fb7e0642c1a390ea7475a98fe15e84e6b4ec67c068166ada426`.
- Interne Version weiterhin 1.3.1; der Preview-Tag bezeichnet den neueren Windows-Fixstand. Keine stabilen Assets ersetzt, Preview nicht als neuestes stabiles Release markiert.
- Preview 1: ZIP-Integrität, `build-info.json` und alle 29 enthaltenen eigenen Desktop-/Engine-/Windows-Dateien gegen den damaligen Code-Commit geprüft. Keine Abweichung nach Zeilenendennormalisierung des Builders. Preview 2 nativ aus sauberem committetem Checkout mit demselben verifizierten Vendorbestand gebaut; Korrektur WIN-08 enthalten.
- GitHub bestätigt Assetgröße und denselben Digest. Preview 2 erneut direkt heruntergeladen und mit öffentlicher Prüfsumme verglichen. Vollständige zweite Neueinrichtung ohne übernommene Modelle/Laufzeit durchgeführt.

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

### Zweite vollständige Einrichtung mit Preview 2

Vor dem zweiten Entfernen die frische Datenbank nativ geprüft: Integrität `ok`, null Aufträge, null aktive Aufträge. Alle Dateien des kleinen ersten Profils einschließlich SQLite vollständig privat kopiert und einzeln per SHA-256 verglichen. Ein zunächst geplanter Reset war von der automatischen Sicherheitsprüfung wegen unvollständiger Profilsicherung abgelehnt worden; erst nach dieser zusätzlichen Prüfung und vollständigen Sicherung ausgeführt. Kein Umgehen der Ablehnung. Preview 1, deren Laufzeit, Modelle und Profil anschließend vollständig entfernt; keine großen Downloads übernommen.

Preview 2 erneut direkt von GitHub heruntergeladen, SHA-256 und Code-Identität geprüft, unveränderte EXE aus leerem App-/Profilbestand gestartet. Neue Python-/CUDA-Laufzeit und anschließend Qwen, Aligner, Sprechergewichte sowie Whisper über die sichtbare Oberfläche bezogen. Beide Modellwahlen melden `Modelle installiert`, Modellspeicher neben der EXE. Frühere Nutzerfreigabe für denselben Python-Pfad blieb gültig. Keine lokale Quellüberlagerung. Native Sprach-/Datei-/Ressourcenprüfungen laufen auf diesem Paket.

| Fall | Status |
| --- | --- |
| Sicherung, Bereinigung und Speicherfreigabe | BESTANDEN, private Bestands-/Hash-/Volumenbelege |
| GitHub-Neudownload, Prüfsumme, normale EXE-Ersteinrichtung | BESTANDEN, Preview 2 mit Code und SHA oben |
| Neue Modelle und Laufzeit vollständig im App-Ordner | BESTANDEN, beide Modelle über sichtbare Oberfläche eingerichtet |
| Deutsch/Englisch getrennt, Qwen/Whisper, lange Pausen | BESTANDEN, acht echte CUDA-Fälle mit Textankern und Zeitmarken |
| Sprecher/DOVER, sequenzielle Modellbelegung und VRAM-Freigabe | OFFEN |
| Lokale/SMB-Überwachung, Pause, Rekursion und Ausfälle | OFFEN |
| Sichtbare Bedienung, Explorer-Drop, Fenster/Infobereich, Verlauf | OFFEN |
| Dateischutz, Kollisionen, Neutranskription und Wiederaufnahme | Datei-/Exportfälle BESTANDEN; Prozessabbruchprüfung läuft |
| Tatsächlicher Windows-Neustart/Anmeldestart | OFFEN |
| Tatsächlicher Sleep/Resume | OFFEN |
| Produktive Ordner und Endeinstellungen | OFFEN |

Wochenlanger Betrieb braucht einen entsprechenden Beobachtungszeitraum. Gemeinsame Änderungen bleiben **UNGEPRÜFT unter macOS** und im Draft-PR #1. Mac-Prüfstand `df207f79aa812f70d090e4306443436d51d48952` bewahren.

## Bestätigte Funktionsläufe auf Preview 2

### WIN-09: sichtbare Konsole beim Windows-Hintergrundstart

Der Nutzer meldete ein regelmäßig aufpoppendes leeres Terminal mit Pfad zur VoxDrop-Python-Laufzeit. Die Untätigkeit des eigentlichen Produktivprüflaufs wurde geprüft: zu diesem Zeitpunkt null eingereihte/aktive Aufträge. Eigene GUI-Statusaufrufe und anschließend der eigene untätige Supervisor/Dienst wurden zur Diagnose angehalten; keine Nutzeraufträge abgebrochen.

Konkreter nativer Vergleich aus einem GUI-Python-Elternprozess: normaler `CREATE_NO_WINDOW`-Start liefert `GetConsoleWindow() == 0`, erhält stdout/stderr. `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP` mit dem ausgelieferten `python.exe`-Venv-Redirector liefert dagegen ein echtes Konsolenhandle; dieselbe Variante mit `pythonw.exe` nicht. Die erste Hypothese eines allgemeinen Fehlers bei `CREATE_NO_WINDOW` war damit widerlegt. Der tatsächliche Auslöser ist die bisher verwendete Hintergrund-Startvariante des Supervisors.

Neue echte Regression in `test_process_lifecycle.py` scheitert am alten Code (`console != 0`). `process_options(background=True)` verwendet unter Windows jetzt `CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP` statt `DETACHED_PROCESS`. Ausgabeprotokolle, Prozessgruppe und Job-Object-Bereinigung bleiben geprüft. Vollständige Windows-Suite nach der Korrektur: 93 Fälle, 86 bestanden, sieben explizite Skips. Paketupdate und sichtbarer Dauerbetrieb werden separat nachgeprüft. Keine Änderung an Modellen, Lockfile oder ASR-/Sprecheralgorithmen; die Modell-/Sprachmessungen oben behalten ihren ursprünglichen SHA.

Alle folgenden Ergebnisse verwenden App-Code `c86746f8cc98c2dce75fb95bd489563591640f9a` aus dem erneuten GitHub-Download.

| Modell | Sprache | Stille überspringen / Sprecher / DOVER | Gesamtlauf |
| --- | --- | --- | --- |
| Qwen | Deutsch | aus / aus / aus | 31,344 s |
| Qwen | Deutsch | ein / ein / ein | 52,766 s |
| Qwen | Englisch | aus / aus / aus | 42,734 s |
| Qwen | Englisch | ein / ein / ein | 46,985 s |
| Whisper | Deutsch | aus / aus / aus | 8,937 s |
| Whisper | Deutsch | ein / ein / ein | 18,812 s |
| Whisper | Englisch | aus / aus / aus | 8,812 s |
| Whisper | Englisch | ein / ein / ein | 17,766 s |

Alle acht Prozesse erfolgreich, alle Originalhashes erhalten, definierte Textanker vor/nach der 20-s-Pause vorhanden. Zeitmarken für den Abschnitt nach der Pause blieben bei rund 27–30 s statt auf die kompaktierte Audiospur zurückzufallen. GPU-Nutzung nachgewiesen; nach Prozessende wieder auf jeweiligem Desktop-Niveau (wechselnde Baseline 1746–1832 MiB). Höchste GPU-Gesamtstichprobe Qwen 6306 MiB, Whisper 4186 MiB. Gesamtlauf enthält Prozessstart/Importe und Messabfragen; keine isolierte Modellgeschwindigkeit. Die DOVER-Fälle führten jeweils drei Durchgänge aus; Warnungen des Fusionspakets bei identischen Einsprecher-Ergebnissen stehen privat im Laufprotokoll. Diese künstlichen Einsprecherfälle belegen keine allgemeine Sprecherqualitätsgarantie.

Lokale echte GPU-Dateiabnahme mit fünf erfolgreichen Aufträgen: rekursive einmalige Ordnerablage, Duplikate und später ergänzte Datei, Originalhashes, separate Neutranskription bei erhaltenem alten TXT, gemeinsames Archivpaar ausschließlich bei aktivierter regulärer Archivoption, weiterlaufender erreichbarer Ordner, erneute Prüfung nach Rückkehr eines fehlenden Ordners, geschützte vorhandene TXT-Kollision und erfolgreicher Cache-Export-Retry. Vollständige private Zusammenfassung vorhanden.

Echter UNC-End-to-End-Lauf in ausdrücklich freigegebener isolierter Testablage: CUDA-Transkription, TXT neben Original trotz Archivoption im Drop-Pfad, Originalhash erhalten, konkreter Fehler bei fehlendem SMB-Unterordner und erfolgreiche Refresh-Prüfung nach dessen Anlage. Keine Unterbrechung des tatsächlichen SMB-Servers vorgenommen; dieser Fall bleibt getrennt ungeprüft.

Zwischenzeitlicher Windows-Neustart am 18.11.2026 vor Einrichtung des neuen Anmeldestarts beobachtet. Alle acht Sprachresultate waren davor gespeichert. Dieser Neustart gilt nicht als Anmeldestartabnahme, weil zu diesem Zeitpunkt noch kein neuer Run-Eintrag gesetzt war. Nach Wiederverbindung drei tatsächliche HTTPS-Prüfungen aus der installierten VoxDrop-Laufzeit (GitHub-API, GitHub-Rohquelle, Hugging Face) jeweils HTTP 200. GitHub-Connector lesend ebenfalls erreichbar. Die Connector-Schreiboperation auf main wurde zuvor mit 403 verweigert; der autorisierte reine Statuscommit wurde stattdessen regulär über die vorhandene Git-Anmeldung gepusht.

Sichtbare Bedienung bisher: Modellwechsel und beide Downloads, Pfad hinzufügen/eingeben, erreichbarer/beschreibbarer Prüfordner, rekursive Option mit gesperrter Archivoption, Stille und DOVER auswählen, Einstellungen speichern. Anmeldestart über die App aktiviert; exakter Run-Zielpfad nativ bestätigt, kein deaktivierter StartupApproved-Eintrag vorhanden. Ein erster Bedienversuch nach Wiederverbindung meldete fehlende Koordinatengeometrie; nach frischer Fensteraufnahme/Zuordnung funktionierte die koordinatengestützte Bedienung. Vollständige physische Explorer-/Taskleisten-/Infobereichsabnahme weiterhin offen.
