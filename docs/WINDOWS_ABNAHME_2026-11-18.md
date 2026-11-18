# Windows-Neuinstallation und Produktivabnahme am 18.11.2026

Status: **Neuinstallation und Betrieb einschließlich echtem Neustart/Anmeldestart und S3-Standby geprüft; produktiv eingerichtet.** Die nachfolgend ausdrücklich ungeprüften physischen Bedien-, SMB-Serverausfall- und Langzeitfälle verhindern weiterhin eine pauschale vollständige Freigabe aller denkbaren Fälle. Dieser Bericht ergänzt die historischen Vorprüfungen und deren exakte Code-SHAs.

## Auftrag und Nutzungsumfang

Vollständige Bereinigung, neue Installation direkt von GitHub, Funktionsprüfungen im Arbeitsablauf und Veröffentlichung der Ergebnisse sind beauftragt. Meetings sind jeweils deutschsprachig oder englischsprachig. Beide Sprachen werden getrennt mit/ohne Stilleüberspringen geprüft. WIN-05 bleibt als synthetischer Mischsprachenbefund technisch offen, ist für diesen Nutzungsumfang aber kein Abnahmekriterium.

## Installationskandidat

- Maßgeblich: [GitHub-Prerelease v1.3.2-windows-preview.4](https://github.com/adriantagonist87/VoxDrop/releases/tag/v1.3.2-windows-preview.4).
- Asset `VoxDrop-1.3.1-Windows-x64-f35bff9f8f12.zip`: 45.704.618 Byte, plus `.sha256`.
- App-Code `f35bff9f8f1222d176b987382d3214dfbd9148c1`.
- SHA-256 `1be623b71f02177e46f402b43a53cf4232bc5e8bae513b7263c1c12553ba241a`.
- Interne Version weiterhin 1.3.1; der Preview-Tag bezeichnet den neueren Windows-Fixstand. Keine stabilen Assets ersetzt, Preview nicht als neuestes stabiles Release markiert.
- Preview 1: ZIP-Integrität, `build-info.json` und alle 29 enthaltenen eigenen Desktop-/Engine-/Windows-Dateien gegen den damaligen Code-Commit geprüft. Keine Abweichung nach Zeilenendennormalisierung des Builders. Preview 2 nativ aus sauberem committetem Checkout mit demselben verifizierten Vendorbestand gebaut; Korrektur WIN-08 enthalten.
- GitHub bestätigt Assetgröße und denselben Digest. Preview 2 erneut direkt heruntergeladen und mit öffentlicher Prüfsumme verglichen. Vollständige zweite Neueinrichtung ohne übernommene Modelle/Laufzeit durchgeführt.

Ein erster privater Archivprüfer behandelte Verzeichniseinträge als Dateien. Erst der korrigierte Dateivergleich bestand; Prüftreiberfehler, kein Appfehler.

## Bestand und Schutz

Private Liste erfasst aufgelöste Installationspfade, Größen, Prozesse, Profile, Autostart und freien Speicher. Eindeutige VoxDrop-App-/Laufzeitbestände belegten vor Bereinigung rund 46 GiB. Das separate ältere Skriptwerkzeug wurde nach ausdrücklicher Nutzerentscheidung ebenfalls entfernt; Einzelheiten und Sicherungsgrößen stehen unten. Gemeinsame Caches, Git-Anmeldung, Entwicklungsquellen, Originalmedien und produktive Transkripte wurden nicht pauschal gelöscht. Persönliche Pfade, Einstellungen, Datenbanken und Logs bleiben außerhalb GitHub.

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
| Sprecher/DOVER, sequenzielle Modellbelegung und VRAM-Freigabe | BESTANDEN auf Preview 2; Preview 4 zusätzlich langer Qwen-/DOVER-Lauf |
| Lokale/SMB-Überwachung, Pause, Rekursion und Ausfälle | Lokale/UNC-Dateipfade und funktionales Pause/Fortsetzen BESTANDEN; tatsächlicher SMB-Serverausfall ungeprüft |
| Sichtbare Bedienung, Explorer-Drop, Fenster/Infobereich, Verlauf | Modelle/Optionen/Speichern/Verlauf/Minimierung/Maximierung bedient; physischer Explorer-Drop und Taskleisten-/Infobereichsklicks ungeprüft |
| Dateischutz, Kollisionen, Neutranskription und Wiederaufnahme | BESTANDEN; Qwen-Prozessabbruch auch auf finalem Preview-4-Paket wiederholt |
| Tatsächlicher Windows-Neustart/Anmeldestart | BESTANDEN auf Preview 4; neuer nativer Bootzeitpunkt, automatischer GUI-/Supervisor-/Dienststart, neuer Auftrag/TXT/Hash |
| Tatsächlicher Sleep/Resume | BESTANDEN auf Preview 4; Windows-S3-Ereignisse, gleicher Prozessbaum und erfolgreicher neuer Folgeauftrag |
| Produktive Ordner und Endeinstellungen | BESTANDEN; freigegebener Ordner aktiv, gewünschte Optionen und Anmeldestart geprüft, eigene Prüfdaten/Helfer entfernt |

Wochenlanger Betrieb braucht einen entsprechenden Beobachtungszeitraum. Gemeinsame Änderungen bleiben **UNGEPRÜFT unter macOS** und im Draft-PR #1. Mac-Prüfstand `df207f79aa812f70d090e4306443436d51d48952` bewahren.

## Funktionsläufe mit jeweils angegebenem Paketstand

### Neustart und produktiver Abschluss am 18.11.2026

Aktuell installierter und geprüfter App-Code bleibt `f35bff9f8f1222d176b987382d3214dfbd9148c1` aus GitHub-Preview 4. Anschließende Commits ändern Dokumentation und den außerhalb des ausgelieferten Pakets liegenden Login-Prüfer; sie sind keine neue App-Paketversion.

Normaler Windows-Neustart ohne erzwungenes Schließen angefordert. Der Nutzer meldete sich selbst an. Nativer Windows-Bootzeitpunkt wechselte von 07:46:32,5 auf 10:00:33,5 Uhr MEZ; Kernel-General-Ereignis 12 bestätigt den neuen Boot. Der einmalige Beobachter sah vor seiner Testdatei exakt eine Hintergrund-GUI, einen Supervisor und einen Dienst (jeweils tatsächlicher Interpreter ohne Redirector-Doppelzählung). Er startete VoxDrop niemals selbst. Neuer synthetischer Auftrag automatisch `done`, Verarbeitung 83,155 s, TXT neben Aufnahme und Originalhash erhalten. Der Test war bereits abgeschlossen, bevor die App später regulär zur Sichtprüfung geöffnet wurde.

Vor Produktivaktivierung alle 335 vorhandenen Dateien im freigegebenen Ordner erneut gegen die privaten Ausgangshashes geprüft: unverändert. Konfiguration und konsistente SQLite-Datenbank gesichert. Zehn ausschließlich zu diesem Lauf gehörende Aufnahmen/TXT-Dateien privat kopiert, Hashes verglichen und aus dem Prüfordner entfernt. Der erste Abschlusshelfer stoppte anschließend beim Entfernen des leeren Ordners mit Windows-Sharing-Fehler 32; Ursache des offenen Handles nicht belegt, keine fremden Prozesse beendet. Der Fortsetzungsschritt prüfte Sicherung, Datenbankintegrität, Original-/TXT-Hashes und leeren Zielordner erneut. Danach leeren Prüfordner erfolgreich entfernt, Produktivkonfiguration validiert/atomar gespeichert und ausschließlich eigene temporäre Login-Helfer entfernt. Der Test-Run-Wert war bereits durch den Beobachter gelöscht; produktiver VoxDrop-Run-Wert bleibt erhalten.

Endzustand: genau der privat freigegebene produktive Ordner, rekursiv, TXT neben Original, keine Archivverschiebung; Qwen3-ASR 1.7B, automatische Sprache, CUDA, Stilleüberspringen, Sprechererkennung und drei DOVER-Durchgänge, 30-s-Intervall, Überwachung und Anmeldestart aktiv. Erster produktiver Scan erfasste 236 Medien, die normale Verarbeitung begann. Das ist keine behauptete Fertigstellung dieses Altbestands. Vorhandene Ergebnisse bleiben durch den geprüften Kollisionsschutz erhalten.

Erster echter produktiver Auftrag anschließend in 478,768 s erfolgreich abgeschlossen. Medienhash gegen die vor Aktivierung erstellte Bestandsliste und den gespeicherten Auftrags-Hash geprüft: Original unverändert. Neues TXT veröffentlicht und dessen Hash mit der Datenbank verglichen; alle 97 bereits zuvor vorhandenen TXT-Dateien weiterhin unverändert. Nächster produktiver Auftrag läuft. Abschließende native Prüfung bestätigt gespeicherte Produktivkonfiguration, Datenbankintegrität `ok`, jeweils einen GUI-/Supervisor-/Dienstbaum einschließlich Redirector-Paaren sowie entfernte eigene Prüfordner-/Autostarthilfen. Dienst und Supervisor behalten ihre PIDs vom tatsächlichen Anmeldestart.

Auch die zwei synthetischen Dateien der isolierten SMB-Prüfung gegen die dort gespeicherten Medien-/TXT-Hashes verifiziert, privat archiviert und anschließend samt exakt zugeordneten leeren Prüfunterordnern entfernt. Andere SMB-Dateien und Freigabeeinstellungen nicht verändert.

Bedienhilfe nach Neustart zunächst wieder mit vollständigen Bildern/Accessibility nutzbar. Normaler EXE-Aufruf zeigte dieselbe zuvor automatisch gestartete Instanz; Maximierung bedient, Status und Verlauf lesbar. Bei der anschließenden automatisierten Pfadzuweisung änderte `sky.set_value` den angezeigten Text, löste aber das in QML verwendete `textEdited`-Signal nicht aus. Der folgende Speichern-Klick meldete Erfolg, schrieb dabei jedoch den alten Controller-Entwurf mit entferntem Prüfordner. Die unabhängige Dateiprüfung erkannte diese Abweichung. Daher diese Interaktion ausdrücklich nicht als erfolgreiche Produktivpfad-Speicherung werten; Qt/UIA-Verhalten bei künftigen Accessibility-Prüfungen berücksichtigen.

Die validierte atomare Konfigurationsschnittstelle stellte den freigegebenen Produktivzustand wieder her. Anschließend ausschließlich den eigenen GUI-Prozess neu geladen, damit er die gespeicherten Einstellungen frisch übernimmt; Supervisor und Dienst blieben dabei mit identischen PIDs/Erstellzeiten erhalten. Konfiguration, Datenbankintegrität, aktive Überwachung und Entfernung der temporären Helfer danach erneut unabhängig geprüft. Die Bedienhilfe lieferte beim weiteren Tastaturversuch wieder schwarze Aufnahmen nach `failed to activate captured window`; zusätzliche Sichtbedienung beendet. Keine neue VoxDrop-Konsole im zuvor beobachteten Fensterbestand. Physischer Explorer-Drop und physische Taskleisten-/Infobereichsklicks bleiben ungeprüft; die bereits dokumentierte fensterübergreifende Drag-Grenze wurde nicht durch andere Eingabemethoden umgangen.

Verbleibende Grenzen: physischer Explorer-Drop, physische Taskleisten-/Infobereichsklicks, systemweiter DPI-Wechsel, tatsächlicher SMB-Serverausfall und mehrstündige/wochenlange Echtzeitserien. Gemeinsamer Code unter macOS ungeprüft, Draft-PR deshalb erhalten; stabile Release-Assets unverändert. WIN-05 technisch offen, für die vereinbarten getrennt deutsch-/englischsprachigen Meetings kein Abnahmekriterium.

### Aktueller Paketstand und Fortsetzung

Preview 4 nach erneutem Download unmittelbar aus dem GitHub-Asset installiert; SHA-256 gegen veröffentlichte Prüfsummendatei verglichen. Vor Update vollständige private Profil-/Codesicherung, Datenbankintegrität und null aktive Aufträge geprüft. Runtime-/Modellmanifeste bytegleich, sämtliche Modelldateigrößen und Änderungszeiten unverändert; alle aktualisierten App-Dateien bytegleich zum heruntergeladenen Paket. Dies ist ein geprüftes GitHub-Update nach der vollständigen leeren Preview-2-Installation, keine behauptete dritte/vierte Modelleinrichtung.

Die lange OPUS-Testkopie wurde durch die normale gespeicherte Überwachung vollständig verarbeitet: 2935,345 s Audio, insgesamt 490,062 s ab Beobachterstart einschließlich Scannervorlauf; laut gespeicherter Start-/Endzeit 456,038 s eigentliche Verarbeitung. ASR/Aligner 309,031 s, Sprecherphase 136,797 s. DOVER-Lap meldet drei erfolgreiche Durchgänge ohne Fallback. TXT neben Aufnahme; Originalaufnahme und Testkopie per SHA-256 unverändert. GPU bis 100 %, höchste Gesamtstichprobe 7465 MiB; gemeldete Worker-Spitzenbelegung 3.649.585.152 Byte. Keine CUDA-Speicherfehler. Fenster zeigt denselben erfolgreichen Auftrag mit Dauer/Status im Verlauf. Keine persönlichen Inhalte oder Dateinamen veröffentlicht.

Die Computerbedienung wurde zwischenzeitlich durch physisches Escape beendet; nach ausdrücklichem Nutzerauftrag wieder aufgenommen. Kein Test wurde allein aufgrund des gestarteten Prozesses als bestanden markiert. Der physische Explorer-Drop ist durch die verfügbare Bedien-API begrenzt: fensterübergreifender Drag wird vor Ausführung mit `point ... is outside window bounds` abgewiesen. Die interne einmalige rekursive Ordnerablage und deren Original-/Ergebnisschutz sind separat bestanden; ein physischer Explorer-Drop wird deshalb weiter nicht als bestanden ausgewiesen. Fenster-Minimierung und anschließende Wiederanzeige sowie native Maximierung über das Systemmenü wurden tatsächlich bedient; nach Maximierung vollständiges Layout und Verlauf lesbar.

Für die echte Neustartabnahme ist `scripts/check-windows-login.py` vorbereitet: privates Konfigurations-/Ergebnis-JSON, einmaliger eigener HKCU-Run-Beobachter. Er startet VoxDrop niemals selbst. Erst nach neuem Boot und beobachtetem automatischem Hintergrund-GUI-/Supervisor-/Dienststart legt er eine künstliche Aufnahme im Prüfordner ab; er prüft Fertigstellung/TXT/Originalhash und entfernt anschließend ausschließlich seinen eigenen Test-Run-Wert. Der produktive VoxDrop-Run-Wert bleibt erhalten. Tatsächlicher Neustartlauf weiterhin offen.

Vor dem echten Neustart die Testregistrierung auf einen kurzen lokalen Bootstrap umgestellt (151 statt 298 Zeichen; Windows-Run-Grenze 260). Nativer Test desselben Bootstrap im laufenden Boot bestätigt ausdrücklich `No new Windows boot`, kein Appstart, keine Produktivänderung und erhaltene Registrierung. Erst bei tatsächlich erfolgreichem neuen Anmeldelauf darf der private Abschlusshelfer den bereits festgelegten Produktivordner aktivieren. Er prüft zuvor sämtliche vorhandenen produktiven Dateien gegen die privaten Ausgangshashes, sichert Konfiguration und konsistente SQLite-Datenbank und archiviert ausschließlich die zehn exakt erwarteten Abnahme-Dateien mit Hashvergleich privat. Zusätzliche Dateien oder Abweichungen stoppen diesen Abschluss ohne pauschales Löschen. Noch kein produktiver Abschluss oder neuer Boot behauptet.

Der erste Sicherungsvorcheck verglich den berechneten `psutil.boot_time()`-Fließkommawert exakt und stoppte bei einer Abweichung unter einer Mikrosekunde. Windows-CIM und Kernel-General-12-Ereignis bestätigten denselben bisherigen Boot. Prüftreiber korrigiert: native `LastBootUpTime` als UTC-Zeitpunkt statt Fließkomma-Gleichheit für den Bootnachweis; erneuter tatsächlicher Bootstrap-Negativtest und Sicherungsvorcheck bestanden. Vier Aufträge abgeschlossen, null aktiv/ausstehend, SQLite `ok`, konsistente Datenbank-/Konfigurationssicherung vorhanden. Kein Appfehler und keine neue Bootabnahme daraus abgeleitet.

Finale Wiederholung des isolierten Qwen-Abbruchtests auf Preview 4 bestanden: normaler EXE-Hintergrundstart und automatischer Ersatz des beendeten Dienstes; Abbruch nach Anlage von 2.583.624 Byte dekodiertem Audio im Auftragsordner. Null verwaiste Inferenzprozesse, automatische Fertigstellung bis `done`, TXT veröffentlicht, Originalhash unverändert und unterbrochenes Audio entfernt. Produktives Profil nicht angehalten oder verändert.

Automatische englische Erkennung im normalen Überwachungsprofil auf Preview 4 bestanden: Qwen/CUDA, Sprache `auto`, Stilleüberspringen, Sprecher und DOVER aktiv; 37,026 s synthetisches Audio in 32,532 s. Alle Textanker vor/nach 20 s Pause vorhanden, Freitag-Zeitmarke bei 28 s, Originalhash unverändert. Separat gespeicherte Pause vor neuer deutscher Testdatei bestätigt: über vier Minuten keine Einreihung und kein TXT. Fortsetzen wird erst nach tatsächlicher Bedienung und erfolgreichem Folgeauftrag als bestanden markiert. Währenddessen verweigerte die Bedienhilfe den Cursorzugriff und lieferte schwarze Aufnahmen; Nutzer wurde gemäß Computer-Use-Regel zum Entsperren aufgefordert. Kein Appfehler daraus abgeleitet.

Fortsetzen anschließend über den ausgelieferten `controller.save_settings`-Pfad mit Validierung und atomarer Veröffentlichung durchgeführt, da die Bedienhilfe trotz bestätigter Entsperrung, frischer Fensterzuordnung und Kernel-Neuverbindung schwarze Aufnahmen lieferte. Kein zusätzlicher sichtbarer Speichern-Klick behauptet. Danach deutsche Testdatei automatisch `done`: 30,523 s, Sprache `auto`, Qwen/CUDA/Sprecher/DOVER/Stilleüberspringen, alle Textanker vorhanden, Zeitmarke nach Pause 29 s, Originalhash erhalten. Damit Pause/Fortsetzen funktional bestanden; zusätzliche sichtbare Bedienabnahme bleibt getrennt begrenzt.

### Tatsächlicher Standby und Wiederaufnahme auf Preview 4

Am 18.11.2026 um 09:47 Uhr echten S3-Standby über die native Windows-Power-API ausgelöst. Vorher null aktive/ausstehende Aufträge und ein GUI-/Supervisor-/Dienstbaum; einmaliger absoluter UTC-Aufweckzeitgeber mit `fResume=True` für 70 s gesetzt, keine dauerhafte Energie-/Sicherheitsoption verändert. API-Grundlage: [SetSuspendState](https://learn.microsoft.com/en-us/windows/win32/api/powrprof/nf-powrprof-setsuspendstate) und [SetWaitableTimer](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-setwaitabletimer).

Windows-Systemereignisse Kernel-Power 42/107 und Power-Troubleshooter 1 bestätigen S3 (`TargetState`/`EffectiveState` 4). Derselbe Boot und alle sechs App-Prozesse einschließlich Redirector-Paare mit identischen PIDs/Erstellzeiten blieben erhalten. Geschätzter Niedrigenergieanteil aus Uhr-/Unbiased-Interrupt-Time-Differenz 13,617 s; der Rechner wachte vor dem gesetzten Zeitgeber auf, dessen Auslösung wird daher nicht behauptet. Danach neue synthetische deutsche Aufnahme ohne App-Neustart automatisch erkannt und in 37,307 s fertiggestellt, TXT neben Original und SHA-256 erhalten. Eigener Zeitgeber anschließend entfernt; nur im Prüfprozess aktiviertes Shutdown-Privileg zurückgesetzt. Sleep/Resume mit Folgearbeit damit bestanden.

### Nachprüfung des Konsolenfixes in Preview 3

Fix-Code `f41506b13b391c92bdedf17e85c4b7bbc49f3001`, [Preview 3](https://github.com/adriantagonist87/VoxDrop/releases/tag/v1.3.2-windows-preview.3), ZIP-SHA-256 `06b1170625228516c83357b66e97d431399306e0e3fa08ee1c88f964c10999d4`. Nach vollständiger Neuinstallation von Preview 2 als reguläres GitHub-Update eingespielt, nicht als dritte leere Modelleinrichtung ausgegeben. Vollständige private Profil-/Codesicherung vor Update, identische Runtime-/Modellmanifeste, Modelldateien mit unveränderten Größen/Zeitstempeln. Alle installierten Paketdateien nach Kopie per SHA-256 gegen den erneut heruntergeladenen ZIP-Inhalt verglichen. Native Paketprüfung aus GUI-Elternprozess mit Console-Python-Kind: Hintergrundflags `134218240`, Prozesscode 0, `GetConsoleWindow() == 0`, stdout und stderr erhalten. App normal wieder gestartet; in der beobachteten Fensterliste keine VoxDrop-Konsole mehr.

### WIN-10: OPUS-Dateien werden nicht eingereiht

Die ausgewählte freigegebene lange Aufnahme liegt als `.opus` vor. Die gemeinsame `MEDIA_EXTENSIONS`-Liste enthielt `.ogg`, aber nicht `.opus`; der Scanner ignorierte die Testkopie deshalb trotz korrekt aktivierter Überwachung. Null eingereihte Aufträge wurden vor den Paketupdates geprüft. Die gemeinsame Liste wird um `.opus` ergänzt. Neue Regression prüft Erkennung auch mit Großschreibung `.OPUS`, tatsächlichen Warteschlangen-/Exportpfad mit Mock-Engine, TXT neben unverändertem Original und keine Archivverschiebung beim Ordner-Drop. Sie scheitert am alten Code mit null statt einem Auftrag. Echte Codec-Prüfung der privaten 48,9-minütigen OPUS-Kopie erfolgt zusätzlich; keine neue Codec-Abhängigkeit. Gemeinsame Formatänderung unter macOS noch ungeprüft.

Nach Korrektur gesamte Windows-Suite: 94 Fälle, 87 bestanden, sieben Skips, 17,080 s. Echte vollständige OPUS-Dekodierung mit vorhandenen Paketabhängigkeiten: 2935,3386875 s, 46.965.419 Samples, Kopie per SHA-256 unverändert. Die Erkennungsprüfung mit Mock-Engine und die tatsächliche Codec-Prüfung sind getrennte Nachweise; die vollständige Transkription über die laufende Überwachung folgt auf dem neuen GitHub-Paket.

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
