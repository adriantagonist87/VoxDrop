# Verbindliche Windows-Abnahme nach vollständiger Neuinstallation

Nutzerauftrag vom 18.11.2026: Nach Rückkehr des Nutzers die Windows-App vollständig deinstallieren und bereinigen, direkt von GitHub neu installieren und sämtliche Funktionen 1:1 im produktiven Arbeitsablauf prüfen. **GEPLANT, noch nicht durchgeführt.** Die bisherigen Paket-, Modell- und Ausfalltests bleiben Vorprüfungen; sie ersetzen diese Abnahme nicht.

Der Beginn erfolgt in der nächsten gemeinsamen Sitzung nach Rückmeldung des Nutzers. Der Auftrag zur Bereinigung und Neuinstallation ist bereits erteilt. Zuerst konkrete Bestände und Ziele zuordnen; Sicherheits-, Netzwerk- und Anmeldedialoge bedient der Nutzer selbst. Kein unbeaufsichtigter Rechnerneustart vor dieser Sitzung.

## 1. GitHub-Installationskandidat und Bestand eindeutig festhalten

- Vor dem Entfernen eine tatsächlich von GitHub erreichbare ZIP samt SHA-256 und vollständigem Code-Commit bestimmen. Der bisherige stabile Download v1.3.1 enthält die neuen PR-Korrekturen noch nicht. Der geprüfte Windows-Testbuild `bfd4e8ade80c2973cb77541571fa99a374977589` liegt bisher als lokales Artefakt vor; ein entsprechender gekennzeichneter GitHub-Test-/Vorabdownload muss für diese Abnahme verfügbar sein. Stabile Release-Dateien bleiben erhalten.
- Installationen und Testinstanzen, Modelle, verwaltete Laufzeiten, appbezogene Download-Caches, Profile, SQLite-Arbeitsstände, temporäre Audiodaten, eigene Autostarteinträge und Verknüpfungen inventarisieren. Aufgelöste absolute Pfade und Größen privat festhalten, keine pauschale Namenssuche zum Löschen verwenden.
- Aktive Aufträge geordnet abschließen oder ihren Zustand sichern. Konfiguration und Verlauf privat sichern; keine Modell-/Laufzeitduplikate als vermeintliche Bereinigung erzeugen. Bewusst behaltene Sicherungen mit Größe gesondert ausweisen.
- Produktive Originalmedien, vorhandene Transkripte, SMB-Inhalte, fremde Python-/uv-Installationen, gemeinsam genutzte Caches und Git-Anmeldedaten schützen. Entwicklungsquellen und Übergabeberichte getrennt von installierten App-Beständen behandeln. Persönliche Pfade und Inhalte bleiben außerhalb GitHub.

## 2. Vollständig deinstallieren und Speicherfreigabe nachweisen

- Alle eindeutig zu VoxDrop gehörenden GUI-, Supervisor-, Dienst- und Inferenzprozesse beenden; danach prüfen, dass keine dieser Prozesse mehr läuft.
- Die zuvor eindeutig zugeordneten App-/Testinstallationen einschließlich Modelle und Laufzeiten sowie zugehörige Profile, Arbeitskopien, appbezogene Caches/Temporärdateien, Autostarteinträge und Verknüpfungen entfernen. Alte externe Bestände ausdrücklich mit erfassen. Vor jedem rekursiven Entfernen den konkreten aufgelösten Zielpfad gegen die Bestandsliste prüfen.
- Keine Firewall-, Virenschutz-, Zugriffs- oder fremden Autostartregeln pauschal verändern. Nicht eindeutig zuordenbare gemeinsame Bestände zuerst getrennt klären.
- Vorher-/Nachher-Größen und freien Speicher vergleichen, Papierkorb/Dateisperren berücksichtigen. Verbliebene absichtlich geschützte Sicherungen getrennt ausweisen. Fehlende alte App-Prozesse, Modelle, Laufzeiten, Profile und Autostartziele belegen. **Erst danach** den bereinigten Ausgangszustand als bestanden markieren.

## 3. Frisch direkt von GitHub installieren

- Den festgelegten GitHub-Download tatsächlich erneut herunterladen und Prüfsumme gegen die veröffentlichte SHA-256 prüfen. Download-URL, Assetname und Code-Commit protokollieren.
- In den endgültigen beschreibbaren lokalen App-Ordner entpacken und ausschließlich über die unveränderte `VoxDrop.exe` starten. Keine lokalen Quellüberlagerungen, vorab eingerichtete Laufzeit, übernommenen Modellgewichte oder Entwickler-Startparameter verwenden.
- Python/CUDA sowie Qwen, Forced Aligner, Whisper und Sprechergewichte über den ausgelieferten normalen Einrichtungsweg neu beziehen. Fortschritt, Abbruch, tatsächliche Netzwerkfehler und anschließende Wiederholung prüfen; notwendige Freigaben erteilt der anwesende Nutzer.
- Neue Modelle/Hugging-Face-Cache unter `Modelle` und Python/CUDA/uv-Cache unter `Laufzeit` neben der EXE nachweisen. Zusätzliche große externe Downloads und zurückbleibende temporäre Audiodaten ausschließen. Frischen Erststart vor einer gezielten Wiederherstellung der gewünschten Produktiveinstellungen belegen.

## 4. Alle Funktionen im tatsächlichen Produktivablauf abnehmen

Die tatsächlich verwendeten Eingangs-/Ausgabeordner und Einstellungen gemeinsam festlegen und die folgenden Fälle über die normale sichtbare App prüfen. Die bekannten Freigaben für Besprechungs-Testkopien und isolierte SMB-Testdaten bleiben erhalten; die konkrete Produktivkonfiguration wird in dieser Sitzung festgelegt. Für Verschiebe-, Kollisions- und Ausfallprüfungen gekennzeichnete Prüfdaten innerhalb der betreffenden Speicherumgebung verwenden. Bestehende produktive Ergebnisse schützen. Automatisierte interne Prüfungen ergänzen die Bedienprüfung.

| Funktion | Nachweis in der frisch installierten App | Status |
| --- | --- | --- |
| Ersteinrichtung und Netzwerk-Warten | Vollständiger Download, verständlicher Fehler, Abbruch/Wiederholung nach tatsächlicher Nutzerentscheidung | OFFEN |
| Qwen und Forced Aligner | Echte produktive Aufnahme auf CUDA, Text und Zeitmarken inhaltlich prüfen | OFFEN |
| Whisper | Dieselbe relevante Aufnahme als Vergleich, CUDA-Nutzung und Ergebnis prüfen | OFFEN |
| Sprecherzuordnung und DOVER-Lap | Aus/ein, Sprecherzahl und drei Fusionsdurchgänge mit den verfügbaren Einstellungen prüfen | OFFEN |
| Sequenzielle Modellbelegung | Qwen-ASR vor Aligner entladen, Qwen-Prozess vor Sprecherpipeline beendet; Whisper vor Sprecherpipeline entladen. DOVER-Durchgänge seriell mit einer Pipeline. VRAM an Übergängen und nach Abschluss/Abbruch messen; kein fortschreitender Restverbrauch über mehrere Aufträge | OFFEN |
| Lange Stille | Mit/ohne Überspringen vergleichen; Textvollständigkeit und ursprüngliche Zeitmarken prüfen, WIN-05 gezielt nachstellen | OFFEN |
| Regelmäßige Überwachung | Neu eintreffende Dateien über mehrere Intervalle und mehrere lokale/SMB-Ordner verarbeiten | OFFEN |
| Noch laufende Kopie und Dateisperre | Keine vorzeitige Ausgabe; Verarbeitung bzw. Wiederholung nach Freigabe | OFFEN |
| Pause/Fortsetzen | Neue Datei bleibt während Pause liegen und wird nach Fortsetzen verarbeitet | OFFEN |
| Rekursion | TXT neben jeder Originalaufnahme; Hierarchie erhalten; Zielunterordneroption gesperrt | OFFEN |
| Explorer-Ordner-Drop | Physisch ablegen, Unterordner einmalig einreihen, keine Verschiebung; später hinzugefügte Datei nicht erneut durch Drop einreihen | OFFEN |
| Reguläre Archivoption | Aufnahme und TXT nur bei bewusst aktivierter passender Option gemeinsam verschieben | OFFEN |
| Originale und bestehende Ergebnisse | Vorher-/Nachher-Hashes, Duplikatschutz und geschützte TXT-Kollisionen | OFFEN |
| Verlauf | Details, Sortierung, Neutranskription mit eigener Ausgabe und kontrollierte Wiederholung prüfen | OFFEN |
| Ordner-/SMB-Ausfall | Konkreter Fehler, weiterlaufender anderer Ordner, Refresh und automatische Erholung nach Rückkehr | OFFEN |
| Abbruch und Wiederanlauf | Eigenen Dienst während Prüfauftrag unterbrechen; keine verwaisten Inferenzprozesse, sichere automatische Fertigstellung | OFFEN |
| Tatsächlicher Windows-Neustart | Anmeldestart aktivieren, Windows neu starten, normal anmelden; ohne manuellen App-Start neue Aufnahme automatisch verarbeiten | OFFEN |
| Sleep/Resume | Überwachung und wartende Aufträge nach echtem Energiesparzustand wieder aufnehmen | OFFEN |
| Taskleiste und Infobereich | Tatsächliche Klicks, Status/Fehleranzeige und Wiederöffnung mit erhaltenem Normal-/Maximiert-/Vollbildzustand | OFFEN |
| Layout und Einstellungen | Reale Skalierung, Mindestgröße, lange Namen, Spalten und Details; Werte nach App-/Windows-Neustart erhalten | OFFEN |
| Ressourcen und längere Serie | Mehrere echte Aufnahmen, RAM/VRAM-Freigabe, begrenzte Logs, freie Platte und bereinigte Arbeitsdateien beobachten | OFFEN |

Pro Fall Version, Einstellungen, anonymisierte Testbeschreibung, erwartetes und beobachtetes Ergebnis sowie relevante Ressourcenwerte festhalten. Prozessabschluss allein genügt nicht für die inhaltliche Abnahme. Nicht durchführbare Fälle bleiben ausdrücklich offen; für wochenlangen Betrieb ist ein entsprechend langer Beobachtungszeitraum erforderlich.

## 5. Abnahme und gewünschter Endzustand

Ergebnisse in Projektstatus, Entwicklung und Windows-Übergabe mit tatsächlichem GitHub-Asset und vollständigem geprüftem SHA aktualisieren. Bei Fehlern den konkreten Fall beheben und auf einem neu gebauten, von GitHub bezogenen Paket wiederholen; keine unprotokollierten lokalen Patches als Neuinstallation ausgeben.

Zum Schluss bleibt die frisch von GitHub installierte App mit den vereinbarten produktiven Ordnern, Einstellungen, Modellen und Anmeldestart eingerichtet. Testregistrierungen und eigene Prüfdaten werden gezielt entfernt, Nutzeraufnahmen und produktive Transkripte bleiben erhalten. Bis zur abgeschlossenen Neuinstallations-/Produktivabnahme und zur separaten Mac-Gegenprüfung bleibt der gemeinsame Code im Draft-PR.
