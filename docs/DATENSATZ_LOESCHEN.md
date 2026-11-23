# Datensatz mit Originaldatei löschen

**Offener Stabilitätsvorfall:** Nach dem späteren Start einer produktiven CUDA-Transkription meldete der Nutzer einen vollständigen PC-Stillstand. Die Ursache ist nicht geklärt. Die folgenden Funktionstests der Löschung sind keine CUDA-Dauerfreigabe. App beendet, Queue pausiert, CPU-Schutz vorübergehend aktiv. [Gesicherte Befunde und weitere Diagnose](SYSTEMSTILLSTAND_2026-11-23.md).

## Bedienung und Nutzerentscheidung vom 23.11.2026

Jeder Verlaufseintrag einschließlich Fehlern und Bestand bietet in den Details den roten Button **Datensatz löschen**. Der Bestätigungsdialog zeigt den Dateinamen, alle betroffenen Dateipfade und die Warnung:

> Es werden alle Dateien (auch das Original) und Datenbankeinträge gelöscht, der Vorgang kann nicht rückgängig gemacht werden!

**Jetzt löschen** ist rot, **Abbrechen** grün und beim Öffnen fokussiert. Vorbereitung und Abbrechen verändern weder Original/TXT noch Auftragsdaten. Während der tatsächlichen Löschung sind erneute Bestätigung und Schließen gesperrt. Fehler bleiben im Dialog sichtbar. Der native Papierkorb behält die Dateien zur betriebssystemseitigen Wiederherstellung; die SQL-Einträge werden entfernt und lassen sich dadurch nicht zurückholen.

**Netzlaufwerke/SMB werden ausdrücklich abgelehnt.** Der Nutzer wählte „Löschen auf Netzlaufwerken mit einer Erklärung verweigern“. Der Dialog erklärt den fehlenden verlässlich nutzbaren Betriebssystem-Papierkorb und bietet keine aktive Löschbestätigung. Dateien und Datenbank bleiben erhalten. Es gibt keine lokale Ersatzkopie und keine permanente Löschung als Fallback.

Mehrere Neutranskriptionen derselben Originaldatei bilden einen gemeinsamen Datensatz. Dasselbe gilt für Vorgänge mit gemeinsamem Original-/Archivpfad oder gemeinsamem TXT, etwa gleichnamige FLV-/OPUS-Dateien. Der Dialog nennt die Anzahl der verknüpften Vorgänge und zeigt sämtliche betroffenen Dateien, bevor bestätigt werden kann. Ein bloß gleicher Medienhash an anderen Pfaden reicht nicht zum Gruppieren. Läuft ein verknüpfter Auftrag gerade, wird das Löschen verweigert.

## Geprüfter Code und Implementierung

Funktionscode **`6b4722c394ca42844754e54b66283e3f6812e992`**, Branch [`feat/trash-history-record`](https://github.com/adriantagonist87/VoxDrop/tree/feat/trash-history-record), [PR #31](https://github.com/adriantagonist87/VoxDrop/pull/31). Ausgangspunkt `e6243f9cfcdb112a9e6069181e353de4c5701557`. Der Branch enthält die Player-Voraussetzungen aus #20/#29 bewusst als `ab59da8d28bd9409e473b6e86ede63ee3f48f4c6`, `af94b86cae8635a104920dd0d760c2968678f1f1` und `f253816f12df34cc9536a4d08ee0af715a2119c2`. Beim Mac-Abgleich diese Voraussetzungen nicht doppelt integrieren. Auf `main` zunächst ausschließlich diese Dokumentationsübergabe; Funktionscode bleibt bis nativer Mac-Gegenprüfung im PR. Kein Release und kein öffentliches Paket.

`record_delete.py` stellt drei CLI-Aktionen bereit: `prepare-delete-record`, `delete-record`, `discard-delete-record`. Vorbereitung erzeugt eine exakte Bestätigung mit Token und Datei-/SQL-Snapshot. Das Journal liegt im lokalen Serviceprofil unter `record-delete`. Die asynchrone Controller-Anbindung hält die Oberfläche während Hashprüfung und Papierkorboperation bedienbar. Verspätete Antworten auf eine abgebrochene Vorbereitung werden verworfen.

Die Engine prüft die gespeicherte Medienversion, reguläre Dateien, Reparse-/Symlinkziele, kanonische Pfade, lokale Laufwerke und unmittelbar vor dem ersten Verschieben alle Dateiidentitäten. Windows prüft zusätzlich Delete-Sharing und Berechtigungen vorab. Eine inzwischen ersetzte Originaldatei wird geschützt; liegt noch eine passende Archivdatei vor, wird die geschützte andere Datei ausdrücklich als erhalten angezeigt. Ohne passende vorhandene Originalversion wird die Aktion verweigert. Bereits fehlende Dateien können zusammen mit ihrem verwaisten Verlaufseintrag bereinigt werden.

Das tatsächliche Verschieben verwendet [QFile.moveToTrash](https://doc.qt.io/qt-6.10/qfile.html#moveToTrash). Die gepinnte [Qt-6.10.2-Windows-Implementierung](https://github.com/qt/qtbase/blob/v6.10.2/src/corelib/io/qfilesystemengine_win.cpp) verwendet `IFileOperation` mit `FOF_ALLOWUNDO` und `FOFX_RECYCLEONDELETE`, prüft das individuelle Ergebnis und liefert den Papierkorbpfad. Es existiert kein `unlink`-/`remove`-Fallback für Originale und Transkripte. Genau zugeordnete lokale Arbeitskopien unter `jobs/<id>` gehen ebenfalls in den Papierkorb.

Das Journal wird nach jeder bestätigten Verschiebung atomar geschrieben und enthält deren Papierkorb-Beleg. Erst nach allen Verschiebungen entfernt eine SQLite-Transaktion die ausgewählten Jobs, abhängigen Mess-/Export-/Queue-/Ereignis-/Ergebnisdaten und ihre Suchindexzuordnung. Fremde Jobs bleiben erhalten; deren Verweis auf ein früheres Ergebnis wird gegebenenfalls gelöst. Eine Speichergeneration verwirft alte Scanner-/Suchantworten. Der bestehende Queue-Pausenzustand wird nicht verändert.

Dateisystem und SQLite können keine gemeinsame Transaktion bilden. Bei einem Teilfehler bleiben die SQL-Einträge und das Journal erhalten; bereits verschobene Dateien liegen im Papierkorb. Ein erneutes ausdrückliches „Datensatz löschen“ zeigt diesen Zustand und setzt nach Bestätigung fort, ohne bereits verschobene Dateien doppelt anzufassen. Ein veränderter SQL-/Dateisnapshot verhindert das Fortsetzen. Es gibt keine selbsttätige Hintergrundlöschung und keine automatische Wiederherstellung aus dem Papierkorb. Die allgemeine vollständige Verlaufsbereinigung räumt auch diese lokalen Journale auf.

Alle drei Builder übernehmen das neue Engine-Modul. Keine neue Abhängigkeit gegenüber dem Playerstand, kein Modell-/Laufzeitpinwechsel und keine Datenbankschemamigration.

## Tatsächliche Windows-Prüfungen

Windows 11, Python 3.12.13 und Qt/PySide 6.10.2. Ausschließlich isolierte Profile und künstliche Medien. [Bereinigter Nachweis](pruefungen/2026-11-23-windows-record-delete.json).

- Gezielte Suite: **52 Fälle in 19,545 s, 50 bestanden/zwei Skips** (Cocoa und nicht verfügbare Windows-Symlinkerstellung). Zwölf neue Enginefälle und drei neue QML-/Controllerfälle prüfen Abbrechen, Token-/SQL-/Dateiversionen, native Papierkorbfehler ohne Fallback, Teilfehler/erneute Bestätigung, fehlende Dateien, Archivschutz, aktive Verknüpfungen, mehrere Originale/Neutranskripte, SQL-Fremdschlüssel und selektive Suchbereinigung.
- Vollständiger lokaler Kombinationslauf umfasst die bisherigen Player-, SMB-, Download- und Überwachungs-/Stoppänderungen. **301 Fälle in 174,965 s, 288 bestanden/13 Skips**. Der [Windows-Pflichtcheck des funktionalen Commits](https://github.com/adriantagonist87/VoxDrop/actions/runs/45170306204) ist erfolgreich.
- Native Windows-QML bei **1010 × 630 logischen Pixeln**, **100/125/150 % Qt-Skalierung**, langem Unicode-Dateinamen: roter Detail-/Bestätigungsknopf, grünes Abbrechen, Pfadumbrüche, unveränderte Dateien bei Abbrechen und tatsächlicher Weg **QML → Controller → CLI → Betriebssystem-Papierkorb → SQLite** bestanden.
- Echte Papierkorbpfade samt Inhaltshashes bestätigt. Ein real mit Windows-Dateihandle gesperrtes TXT verhindert die gesamte Aktion vor dem ersten Verschieben. Unbeteiligte Dateien, SQL-Einträge und Queuepause bleiben erhalten. Reales gemapptes Netzlaufwerk und UNC-Klassifikation verweigern die Löschung ohne Zugriff auf private Medien.
- Installierte Dateien nochmals mit eigenem Testprofil geprüft, einschließlich nativer Arbeitskopien im Papierkorb und tatsächlichem Netzwerkfehlerdialog mit deaktiviertem „Jetzt löschen“. Normale EXE erneut gestartet und lebender GUI-Owner mit exakter Prozessidentität geprüft. Alle **17** durch die Tests verschobenen künstlichen Dateien/Ordner anschließend gezielt über die Windows-Shell wiederhergestellt; fremde Papierkorbeinträge unangetastet.

Reproduktion der modellfreien Regressionen mit eingerichteter Entwicklungsumgebung: `python -m unittest discover -s tests -p test_record_delete.py` und `python -m unittest discover -s tests -p test_desktop_window.py` (Qt für Headless-Prüfung mit `QT_QPA_PLATFORM=offscreen`). Die nativen Papierkorb-/Sperr-/Skalierungsprüfungen müssen mit eigener künstlicher Aufnahme und isoliertem Profil auf dem Zielbetriebssystem erfolgen. Keine produktiven Originale als Testfälle löschen.

## Lokale Installation und Plattformgrenzen

Lokal vier Programmdateien ergänzt/aktualisiert: `Engine/record_delete.py`, `Engine/watch_service.py`, `Desktop/controller.py`, `Desktop/qml/Main.qml`. Die übrigen **98 vorherigen Programmdateien** wurden gegen ihre bestehenden Paket-/Overlayhashes unverändert geprüft. Vorherige SMB-, Download-, Überwachungs-/Stopp- und dunkle Popup-Player-Fixes bleiben erhalten. Paketbasis `6278335acb6589a97b4973c26cf0e931fb5ac369`; alle sechs Entwicklungslagen mit Dateihashes stehen in `local-development.json`.

Aktuelles Profil und betroffene Altdateien privat gesichert. Aufträge/Reihenfolge, Konfiguration, Layout, Modelle und Runtime erhalten. Nach normalem EXE-Neustart keine produktive Verarbeitung gestartet und bestehende Queuepause erhalten. Das ist ein lokaler Entwicklungsstand, keine Release- oder vollständige Neuinstallationsabnahme.

**macOS: UNGEPRÜFT.** Bestätigter Mac-Stand bleibt 1.5.0 Build 27. Vor gemeinsamer Integration nativ prüfen: Qt-Papierkorb und Dateienwiederherstellung, Schreib-/Löschrechte und fehlender Papierkorb ohne permanenten Fallback, SMB-Mount-Ablehnung, Dateiversions-/Symlink-/Archivschutz, Mehrfach-/Neutranskriptgruppe, Teilfehler und App-Ende zwischen Verschiebungen, Suchindex/Fremdschlüssel, alle Dialogaktionen bei Mindestgröße/Retina, Fokus/Escape sowie Cmd-Q. Keine Mac-Freigabe aus dem Windows-Ergebnis ableiten.
