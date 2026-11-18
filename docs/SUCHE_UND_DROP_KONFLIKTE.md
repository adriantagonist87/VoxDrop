# Suche, Drop-Konflikte und Explorer-Auswahl

Nutzeraufträge vom 18.11.2026: Suchfelder hinter Lupenbuttons in Warteschlange und Verlauf, schnelle Wildcardsuche, ausdrücklich gestartete/gestoppte Inhaltssuche auch bei 20.000 Transkripten, verständliche Konfliktentscheidungen bei gemischten Datei-/Ordnerdrops und Korrektur der Explorer-Auswahl.

## Aktuell ausgeliefert: Preview 9 und Queue-Menükorrektur

[Windows Preview 9](https://github.com/adriantagonist87/VoxDrop/releases/tag/v1.3.2-windows-preview.9), App-Code `c434d5c4921873d387cefc8cdc55f23f201e61de`, ZIP-SHA-256 `7dd6e52dadff40a73f8ce9b79c09609f2d2cd21ed3a6917d338af10937422da4`. ZIP `VoxDrop-1.3.1-Windows-x64-c434d5c49218.zip`, 45.729.489 Byte; 456 Byte mehr als Preview 8. Keine zusätzliche Abhängigkeit, Modell-/Lockfileänderung oder Datenbankmigration. Gemeinsamer Code bleibt bis Mac-Gegenprüfung im Draft-PR #1.

Nutzermeldung: Die ersten vier Queue-Menüeinträge ließen sich nicht anklicken. Reproduktion auf Preview 8: Bei aktiver Dateisuche waren alle Reihenfolgeaktionen und der Drag-Griff absichtlich über `pane.searching` deaktiviert; ihre bisherige Berechnung verwendete den gefilterten Zeilenindex. Die Standardfarben zeigten die Sperre zudem nicht deutlich.

Korrektur: `move_queue_relative` löst `first/up/down/last` innerhalb von `BEGIN IMMEDIATE` gegen alle aktuell wartenden Aufträge auf. Der Controller übergibt Auftrag und Richtung, keine gefilterte Zielposition. QML verwendet die ursprüngliche Gesamtposition und die gesamte Queueanzahl für tatsächlich unmögliche Grenzaktionen; deaktivierter Text ist ausdrücklich grau. „Als Nächstes“ ändert den nächsten wartenden Auftrag, ohne den aktiven Auftrag abzubrechen. Für Drag-and-drop transportiert `moveQueueDrop` den konkreten Zieleintrag und die Vor-/Nach-Seite; `move-queue --after` fügt direkt hinter diesem Anker ein. Damit wird etwa beim Drop von 1 hinter den sichtbaren Treffer 3 aus `[1,2,3,4,5]` korrekt `[2,3,1,4,5]`, auch wenn 2/4/5 ausgeblendet sind. Stale/aktive Aufträge werden abgewiesen, Erkennungszeiten und Dateiversionen bleiben unverändert.

135 Windows-Testfälle in 33,482 s: 128 bestanden, sieben bekannte Skips (fünf Mac-Migrationsfälle, zwei Windows-Symlinkrechte). Neue Backendfälle prüfen alle relativen Aktionen, aktive/stale Aufträge, unveränderte Zeitangaben, Vor-/Nach-Anker und Wiederöffnung der Datenbank. Zwei neue echte QML-Mausfälle prüfen aktivierte Menüeinträge bei nur einem sichtbaren Treffer sowie gefiltertes Drag-and-drop mit ausgeblendeten Nachbarn. Insgesamt 15 vollständige Qt-Fälle bestanden. Ein zunächst fehlerhafter Qt-Test erzeugte über `MenuItem.window()` einen zusätzlichen PySide-Fensterwrapper und beschädigte die Testbereinigung; der Test verwendet jetzt das bereits gehaltene Hauptfenster. Fehlgeschlagene Vorläufe gelten nicht als Abnahme.

Tatsächlich finales Paket mit isoliertem Profil über `VoxDrop.exe --background` gestartet; alle vier CLI-Aktionen, Vor-/Nach-Anker und echter gefilterter QML-Menüklick mit Änderung der tatsächlichen SQLite-Reihenfolge in 8,584 s bestanden. Synthetische Menüansicht visuell geprüft. Auftragsidentitäten, Pause, SQLite und Fremdschlüssel bestätigt. Die echte deutsche/englische CUDA-, Qwen-Unterbrechungs-/Wiederaufnahme- und Inhaltssuchabnahme bleibt exakt auf Preview-8-Code `d40b00526494155979d19d6b0b67fcf1853d618f`. Für Preview 9 wurden alle Engine-Dateien bis auf `queue_control.py`/`watch_service.py` bytegleich bestätigt; dort ist der AST außerhalb der Reihenfolgehelfer bzw. CLI/Queueimporte unverändert. Keine neue CUDA-Prüfung für die reine Reihenfolgekorrektur behaupten.

Direkter GitHub-Download/SHA bestätigt, konsistente SQLite-Sicherung über Backup-API, Konfiguration/Layout und vorherigen Code privat gesichert. Queuehelfer vor neuer CLI, Buildmetadaten zuletzt atomar ersetzt; alle 88 Paketdateien hashgleich. Sämtliche 9.385 unmittelbar vorher vorhandenen Auftragsidentitäten/Dateiversionen erhalten; Modelle, Laufzeit und aktuelle Nutzerkonfiguration unverändert. Supervisor-/Dienst-PIDs samt Erstellungszeit vor/nach Kopie identisch. Nur Oberfläche neu gestartet. Kontrollstand: 27 wartend, kein aktiver Auftrag, Pause weiterhin aktiv; Verlauf Alle 9.358, Fehler 1, Fertig 487. Bereits im Vorprofil abgebrochene Einträge bleiben im Verlauf. Eine erste Accessibility-Abfrage nach dem Fensterstart lieferte leere Statuswerte, während die reguläre Status-CLI korrekt antwortete. Nach erneutem Fensterstart mit privater Fehlerprotokollierung und Aktivierung sind Pause/Zähler korrekt bestätigt; kein zusätzlicher Quellcodefix und keine gesicherte Ursache dieses ersten Anzeigebefunds behauptet. Keine produktiven Umordnungs-/Abbruchaktionen als Test durchgeführt.

Mac-Gegenprüfung zusätzlich: gefiltertes Menü an erster/mittlerer/letzter Gesamtposition und Vor-/Nach-Drag mit ausgeblendeten Nachbarn. Frühere Neuinstallations-, CUDA- und 20.000-Dateien-Messungen behalten ihre jeweiligen SHAs und Grenzen.

## Vorangegangener ausgelieferter Prüfstand: Preview 8

[Windows Preview 8](https://github.com/adriantagonist87/VoxDrop/releases/tag/v1.3.2-windows-preview.8), App-Code `d40b00526494155979d19d6b0b67fcf1853d618f`, ZIP `VoxDrop-1.3.1-Windows-x64-d40b00526494.zip`, SHA-256 `80129d589819ab0ba4e3c7644aa5e31f63c1d565c403457df21d2b068d27c0f8`. Interne Version weiterhin 1.3.1, keine Lockfile-/Modelländerung. 45.729.033 Byte, nur 14.053 Byte größer als Preview 7. Stabile Assets nicht ersetzt; gemeinsamer App-Code bleibt im [Draft-PR #1](https://github.com/adriantagonist87/VoxDrop/pull/1), unter macOS ungeprüft.

131 Windows-Testfälle in 30,209 s: 124 bestanden, sieben bekannte Skips (fünf Mac-Migrationen, zwei Windows-Symlinkrechte). Die Suite enthält 13 vollständige Qt-Fälle sowie native Kindprozess-/Abbruchprüfungen. Tatsächliches Paket mit isoliertem Profil und echten deutschen/englischen CUDA-Läufen in 87,605 s bestanden: gemischte Drops vor Änderungen prüfen, idempotent anwenden, echten Qwen-Prozessbaum abbrechen, priorisierten Auftrag zuerst verarbeiten, bisherigen Auftrag automatisch neu beginnen, Bestands-TXT bei Neutranskription erhalten, Sofort-Auswahl bei pausierter Queue begrenzen und Paket-Pfad-/Inhaltssuche ausführen. Originalhashes, SQLite und Fremdschlüssel bestätigt.

Direkt von GitHub heruntergeladen, SHA und alle 88 installierten Dateien verglichen. Vorher im Leerlauf (null aktive Aufträge) komplettes Profil und Code privat kopiert und hashgeprüft. Aktuelle Konfiguration/Layout, Modelle/Laufzeit und Pause erhalten; nach regulärem App-/Dienststart alle 9.148 bisherigen Auftrags-IDs und Dateiversionen vorhanden, SQLite/Fremdschlüssel `ok`. Kontrolllauf: 8.870 wartend, kein aktiver Auftrag, Queue weiter pausiert; Verlauf 278/0/278 für Alle/Fehler/Fertig. Alle 97 ursprünglichen TXT vor dem Update gegen ihren aktuellen Inhalt geprüft und erhalten. Die frühere Ein-Ordner-Konfiguration wurde nicht über die vom Nutzer inzwischen geänderten Einstellungen geschrieben. Der Suchindex existierte nach dem Start noch nicht: keine automatische Inhaltsindexierung. Accessibility-Baum der installierten App bestätigt beide Lupenbuttons, Kompaktumschalter, Fortsetzen und die drei Zähler. Keine produktiven Konflikt-/Abbruchaktionen als Test ausgeführt.

## Schnelle Dateisuche

- `SearchToggle.qml` öffnet die jeweiligen Eingabefelder. Schließen setzt den Filter zurück. `*` ersetzt beliebig viele Zeichen, `?` ein Zeichen; eine Eingabe ohne Wildcard findet Teilzeichenfolgen. Groß-/Kleinschreibung und Pfadtrenner werden normalisiert. SQL-Metazeichen wie `%` und `_` bleiben wörtlich.
- Queue: Filter über bereits geladene Metadaten, keine Medien-/TXT-Lesezugriffe. Ursprüngliche Queuepositionen bleiben sichtbar. Seit Preview 9 bleiben Reihenfolgeaktionen und Drag-Griff auch bei aktivem Filter bedienbar und beziehen sich auf die gesamte Queue; der Hinweis erklärt dies. Entfernen und Auftragsdetails bleiben erreichbar.
- Verlauf: 180 ms Verzögerung fasst Tippeingaben zusammen; Worker-CLI filtert vor dem 250-Zeilen-Limit. Originalpfad, Ziel-/Transkriptname und bekannte Ergebnisdateien sind berücksichtigt. Zähler beziehen sich auf alle passenden terminalen Aufträge. Veraltete Antworten nach Filter-/Suchwechsel werden verworfen. „Verlauf leeren“ ist während einer Suche gesperrt, damit der globale Verlauf nicht für eine gefilterte Ansicht geleert wird.
- CLI: `status --search "Projekt*2026?" --filter all|errors|done --limit 250`. Werte werden als SQL-Parameter übergeben.

## Ausdrückliche Detailsuche

`desktop/transcript_search.py` wird beim Start lediglich importiert. Erst „Detailsuche starten“ erzeugt/aktualisiert `service/transcript-search.sqlite3` im lokalen Profil. Die Funktion verwendet das vorhandene SQLite FTS5, keine zusätzliche Bibliothek oder KI-Laufzeit. Neue/geänderte TXT werden einzeln gelesen, unveränderte Dateien anhand Größe/Änderungszeit wiederverwendet; mehrere Aufträge zur selben TXT teilen einen Indexeintrag. Entfernte, unlesbare oder während des Lesens geänderte Dateien liefern keine veralteten Inhaltstreffer.

Windows-Prüflauf mit SQLite 3.53.1: Contentless-Delete-FTS5 speichert den Suchindex ohne weitere vollständige Klartextkopie. Ältere SQLite-Builds können auf eine gewöhnliche FTS5-Tabelle zurückfallen; dies ist unter macOS separat zu prüfen. Grundlage: [SQLite FTS5](https://www.sqlite.org/fts5.html). Alle Wörter müssen vorkommen; `Wort*` sucht Wortanfänge. Rohes FTS-/SQL-Steuervokabular aus der Eingabe wird nicht als Abfragesyntax übernommen. Inhaltstreffer erweitern die Pfadtreffer derselben Suche.

Eigener Python-Suchprozess im bestehenden Prozessadapter/Windows Job Object; Fortschritt kommt als kleine JSON-Meldungen. Stoppen oder Ändern des Suchtexts beendet nur diesen Prozessbaum. Dadurch bleibt die GUI auch bei blockierendem Dateizugriff bedienbar. Ein abgebrochener Indexlauf lässt konsistente, bereits bestätigte Teilstände zurück; Ergebnisse werden erst nach erfolgreichem Abschluss atomar veröffentlicht. Ein Token bindet die Ergebnis-ID-Liste an die aktuelle Eingabe; eine temporäre SQLite-Tabelle beschränkt die Metadatenabfrage. Es werden keine Tausenden IDs als Kommandozeilenargument übergeben.

SQLite-Seitencache 8 MiB, jeweils nur eine Textdatei im Arbeitsspeicher, Leseabbruch zwischen 64-KiB-Blöcken. Dateien über 32 MiB werden gezählt und übersprungen. UTF-8/BOM, UTF-16-BOM und ältere CP1252-Texte werden unterstützt. Ein späterer Start prüft Änderungen erneut. Die Queue-/Verlaufsdatenbank wird nur gelesen; Index und Ergebnisdatei sind eigener lokaler Cache.

### Messung mit 20.000 TXT

Isolierter lokaler Testdatensatz mit insgesamt 60.580.500 Byte synthetischem Text, ohne persönliche Medien:

| Messung | Ergebnis |
| --- | --- |
| Queue-Pfadfilter, 100 Treffer | 47 ms |
| Verlaufspfadabfrage plus globale Zähler, installierter Preview-8-Code, Median aus fünf Läufen | 219 ms |
| Erster Inhaltssuchindex samt Suche | 8,782 s |
| Folgesuche inklusive Prüfung aller Dateiversionen | 1,125 s; keine Texte erneut eingelesen |
| Reine FTS-Abfrage im bestehenden Index | rund 0,9 ms |
| Lokale Indexdatei | 17.367.040 Byte |
| Eigener Suchprozess abbrechen, inklusive Start/Metadatensammlung | 0,640 s; keine Orphans |

SQLite-Integrität und Contentless-Speicherung bestätigt. Das sind Messwerte dieses lokalen Datensatzes, keine Zusage für beliebige Textgrößen oder Netzlaufwerke. Die im privaten Messbericht separat erfasste Speicherzahl betrifft den Benchmark-Elternprozess, nicht den gesamten Desktop samt Suchprozess; sie wird deshalb nicht als gesamter RAM-Verbrauch ausgewiesen. Tatsächlicher SMB-Serverausfall wurde nicht nachgestellt.

## Datei-/Ordnerdrops und Konflikte

`prepare-drop CONFIG` expandiert reguläre Dateien/Ordner, dedupliziert überlappende Eingaben und speichert einen versionierten Plan in `drop_batches`. Dateidrops sind nun ausdrücklich unterstützt; zuvor wurde der Dateipfad als Ordner geprüft, wodurch lediglich eine unverständliche Pfadmeldung erschien. Vor einer Entscheidung werden weder bestehende Aufträge verändert noch neue gestartet. Die GUI zeigt neue, wartende, aktive, fertige, TXT-Bestands- und Fehlerfälle sowie nicht lesbare Pfade in einer virtualisierten Liste. Zusätzliche Drops während einer Entscheidung werden gesammelt und danach gemeinsam geprüft.

`resolve-drop TOKEN ACTION` prüft Dateiversionen erneut, führt die Auswahl in einer kurzen SQLite-Schreibtransaktion aus und speichert das Resultat. Wiederholte Anwendung desselben Tokens erzeugt keine weiteren Aufträge. Inzwischen veränderte/verschwundene Dateien werden gemeldet; übrige gültige Dateien bleiben bearbeitbar. Windows-Pfadvergleich berücksichtigt ASCII-Groß-/Kleinschreibung; Punktsegmente werden normalisiert.

| Aktion | Verhalten |
| --- | --- |
| An 1. Stelle | Neue/wartende/wiederholbare Aufträge als Gruppe vorziehen; bereits fertige ignorieren |
| Neu transkribieren | Bestehende fertige Ergebnisse behalten, eigenen Neutranskriptionsauftrag/-namen erzeugen; bereits wartende nicht duplizieren |
| Sofort transkribieren | Auswahl vorziehen; eigenen aktuellen Inferenzbaum kontrolliert abbrechen und bisherigen Auftrag anschließend neu beginnen; Export fertigstellen |
| Bereits erfasste ignorieren | Nur unproblematische neue Aufnahmen einreihen |
| Gesamten Drop verwerfen | Plan schließen, keine Aufträge aus diesem Drop verändern |

`preemptions` bewahrt die Wiederaufnahmeabsicht und die reservierte Queueposition über einen Dienstabsturz. Abbruchbereinigung erfolgt vor dem Wiederbereitstellen. Expliziter Einzel-/Gesamtabbruch hebt diese Wiederaufnahme auf. Bei bereits pausierter Queue erlaubt `immediate_jobs` ausschließlich die ausdrücklich gewählte Gruppe und gegebenenfalls den bisherigen unterbrochenen Auftrag. Die übrige Queue bleibt pausiert. „Auswahl pausieren“ beendet diese Ausnahme für weitere Aufträge; normales Fortsetzen bleibt eine eigene Nutzeraktion. Die tatsächliche Auftragbeanspruchung prüft die Pause/Ausnahme erneut atomar.

TXT und Originale bleiben geschützt; für sämtliche Dropaufträge gelten rekursive Ablage neben der Aufnahme und keine Medienverschiebung. Bereits aktive ausgewählte Aufträge werden nicht unnötig erneut gestartet. Ein bereits begonnener Export wird auch bei „Sofort“ abgeschlossen.

## Explorer-Korrektur

Der bisherige Aufruf `Popen(["explorer.exe", "/select," + path])` quotiert bei Leerzeichen die gesamte Option. Der Explorer konnte dadurch im Standardordner landen. `desktop/file_actions.py` übergibt stattdessen den unveränderten Unicode-Dateipfad an `SHParseDisplayName` und ruft `SHOpenFolderAndSelectItems` mit der Dateikennung auf. Die Windows-Shell öffnet den Elternordner und markiert die Datei. COM-Initialisierung und Freigabe erfolgen im Worker, fehlende Dateien/HRESULT-Fehler werden sichtbar gemeldet. [Microsoft: SHParseDisplayName](https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/nf-shlobj_core-shparsedisplayname), [SHOpenFolderAndSelectItems](https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/nf-shlobj_core-shopenfolderandselectitems).

Regressionsfälle mit Leerzeichen, Unicode, Komma, Plus, fehlender Datei und Shell-Fehlern bestanden. Zusätzlicher realer Controller-/Shell-Aufruf mit synthetischer TXT wurde vom OS akzeptiert; Accessibility bestätigt Zielordner, genau eine enthaltene Datei und eine ausgewählte Datei. Die Aufnahme war vom darüberliegenden Fenster verdeckt; keine separat sichtbare Explorer-Bildabnahme behaupten. Finder-Verhalten blieb unverändert.

Ein Qt-Prüflauf zeigte nach dem neuen Dialog inkonsistente PySide-Wrapper beim eigenen QML-Typ `Action` und brach ab. Der eigene Typ heißt jetzt `AppActionButton`; dieselben GUI-Fälle einschließlich Dialog und späterer Verlaufsbedienung bestanden danach. Testfenster/Engines werden vollständig freigegeben. Vorläufige fehlgeschlagene Testläufe sind keine bestandene Abnahme.

## Übergabe an den Mac

Gemeinsamen Code zunächst im Draft lassen, bisherigen Mac-Prüfstand bewahren. Nativ auf Cocoa prüfen: alle neuen Module/QML-Dateien im Paket, SQLite-FTS5 einschließlich älterem Fallback, Standard-TXT-Pfade und Finder, Unicode/Wildcards, Suchprozessabbruch über Unix-Prozessgruppen, Indexwiederaufnahme, große Datenmengen, gemischte Drops und idempotente Aktionen. Insbesondere pausierte Sofort-Auswahl, explizite Pause/Abbruch sowie Wiederaufnahme nach Dienstunterbrechung gegenprüfen. Die vollständige Suite und gezielt `test_transcript_search.py`, `test_queue_controls.py`, `test_desktop_window.py` ausführen. Der Windows-Shell-Adapter hat explizite Windows-Tests.

Keine neue physische Explorer-Drop-, Taskleisten-/Tray-/DPI- oder tatsächliche SMB-Ausfallabnahme behaupten. Frühere Modell-/Neuinstallationsprüfungen behalten ihre in den vorherigen Berichten dokumentierten Code-SHAs. WIN-05 bleibt im vereinbarten jeweils einsprachigen Deutsch-/Englischumfang kein Abnahmekriterium.
