# Sicherung, Wiederherstellung und Gerätewechsel

Unter **Einstellungen → Import & Export** lassen sich die Bestandteile unabhängig per Checkbox auswählen:

- **Einstellungen und Fensterlayout**: gespeicherte Konfiguration mit sämtlichen Ordneroptionen, Modell-/Sprach-/Sprecher-/Budgeteinstellungen und `layout.ini`.
- **Datenbanken**: alle regulären lokalen SQLite-Datenbanken, einschließlich vollständigem Verlauf, Bestand, Dateiversionen, Ereignissen, Queue samt Reihenfolge, Messungen, Ergebnishashes und vorhandenem TXT-Suchindex. Keine Beschränkung auf die gerade sichtbare Verlaufsseite oder einen Filter.
- **Modelle**: Modellgewichte und Hugging-Face-Hub-Cache. Doppelte Dateiinhalte belegen im Archiv nur einmal Platz. Interne Modellverknüpfungen werden ohne benötigte Symlink-Rechte wiederhergestellt. Anmeldungstokens werden nicht exportiert; vorhandene Tokens des Zielgeräts bleiben erhalten.
- **Aufnahmen und TXT**: vorhandene Medien und TXT in den überwachten Ordnern einschließlich Unterordnern sowie noch vorhandene Quellen/Ergebnisse aus dem Verlauf. Vorhandene Originaldateien bleiben erhalten. Nicht erreichbare überwachte Ordner werden im Ergebnis und Manifest ausdrücklich gemeldet.

Standardmäßig sind Einstellungen und Datenbanken ausgewählt. Modelle und Medien können mehrere GB belegen. Ohne Medienauswahl enthält die Sicherung deren Datenbankverweise und den bereits vorhandenen Suchindex, jedoch keine Audio-/Video-/TXT-Originale. Nicht mehr vorhandene historische Originale können nicht aus dem Verlauf rekonstruiert werden. Temporäre Inferenzkopien, PID-/Sperrdateien und Diagnoseprotokolle sind keine Migrationsdaten. Programm und Python-/CUDA-/MLX-Laufzeit werden separat auf dem Zielgerät installiert; Netzwerkzugänge, eingehängte Freigaben und die gerätespezifische Anmelderegistrierung werden im Betriebssystem beziehungsweise unter „App & Daten“ eingerichtet.

## Export

1. Einstellungsentwürfe vorher speichern oder verwerfen.
2. Bestandteile auswählen und „Ausgewählte Daten exportieren …“ verwenden.
3. Die `.voxdrop.zip` auf das neue Gerät übertragen. Sie enthält persönliche Daten; es erfolgt kein Upload.

SQLite wird mit der Backup-API einschließlich bestätigter WAL-Änderungen gesichert. Der Export darf während einer Transkription laufen. Während der Sicherung veränderte oder lokal noch beschriebene Mediendateien führen zum Abbruch; eine zuvor vorhandene Sicherungsdatei bleibt bis zum vollständigen neuen Export erhalten. Große Dateien werden in begrenzten Blöcken verarbeitet. Abbrechen ist während Lesen/Prüfen möglich.

## Import

1. VoxDrop auf dem Zielgerät installieren und die Sicherung auswählen. Datum, Quellplattform, Auftrags-/Dateizahl und Größe werden angezeigt. Nur tatsächlich enthaltene Bestandteile sind auswählbar.
2. Ohne Medienimport die bisherigen Ordner bei Bedarf den lokalen Ordnern oder bereits eingebundenen Freigaben zuordnen. Windows-Laufwerks-/UNC-Pfade und Mac-Pfade werden über vollständige Pfadbestandteile, nicht über beliebige Textfragmente, zugeordnet. Beim Plattformwechsel Rechengerät automatisch anpassen; CPU bleibt CPU. Modelle sind plattformspezifisch und bei Windows↔Mac neu einzurichten.
3. Bei Medienimport einen Zielordner wählen. VoxDrop erstellt dort einen neuen `VoxDrop-Import-…`-Ordner mit getrennten, benannten Wurzelordnern. Einstellungen und ausgewählte Datenbanken werden automatisch auf diese Kopien umgestellt; die Verzeichnishierarchie bleibt erhalten. Wiederholte Importe erhalten jeweils einen eigenen Ordner. Bestehende Medien werden nicht überschrieben.
4. Aktiven Auftrag abschließen lassen oder kontrolliert stoppen. „Ausgewählte Daten importieren …“ zeigt die Ersetzungsbestätigung.
5. Nach erfolgreichem Import Ordner prüfen und Überwachung/Verarbeitung bewusst wieder starten. Beide bleiben zunächst angehalten. Ein neuer Anmeldestart wird nicht ungefragt eingerichtet.

Vor Änderungen werden ZIP-Struktur, Format, sichere Zielpfade, Dateigrößen, SHA-256, SQLite-Integrität und Fremdschlüssel geprüft. Der Import stoppt eigene Dienste und Detailsuche, bereitet die Daten separat vor und sichert automatisch den bisherigen App-Stand als `VoxDrop-vor-Import-…/Vor-dem-Import.voxdrop.zip`. Dieser Pfad wird nachher angezeigt. Bei ausgewählten Modellen bleibt zusätzlich der bisherige Modellordner erhalten; auch sein Pfad wird angezeigt. Vorherige Medien werden nicht verschoben.

Ein Journal ermöglicht die Rücknahme bereits ersetzter Dateien bei einem Fehler oder nach einem abgebrochenen App-Prozess. Nach Neustart wird ein nicht abgeschlossener Import vor dem Dienststart zurückgenommen. Prozesskennungen und flüchtige Such-/Drop-/Sofortauswahlen werden nicht übernommen. Vorübergehend kopierte/transkribierte Aufträge werden wartend übernommen; bereits begonnene Veröffentlichungen werden zur Prüfung blockiert. Abgeschlossene Ergebnisse, explizite Abbrüche und Queue-Reihenfolge bleiben erhalten. Unveränderte Dateiversionen berücksichtigen bei mitkopierten Medien die Zeitauflösung des Ziellaufwerks.

## Ordneroptionen

Die beiden Checkboxen „Unterordner mit einbeziehen“ und „Unterordner für fertige Transkripte erstellen“ sind gleichartig bedienbar: Einschalten einer Option schaltet die andere aus; beide können ausgeschaltet werden. „Globale Vorgabe“ steht nicht mehr einseitig vor der zweiten Checkbox. Abweichende Ausgabeoptionen eines einzelnen überwachten Ordners bleiben als solche erhalten.

## Prüfstand

Die automatisierten Prüfungen verwenden ausschließlich isolierte Profile, synthetische Aufnahmen/TXT und kleine künstliche Modellgewichte. Sie prüfen unter anderem WAL-Sicherung, vollständigen Reimport, Queue/Pause, Dateiversionen, Unicode, Pfadzuordnung, wiederholten Medienimport, beschädigte Archive, Rollback und Wiederherstellung beim nächsten Start sowie die echte Qt-Oberfläche. Die native Zielplattformabnahme und der exakte getestete Code stehen im Projektstatus. Windows-Quellintegration wird bis zur tatsächlichen Windows-Paketabnahme nicht als native Veröffentlichung ausgegeben.


Abnahme am 21.11.2026: Mac 1.5.0 Build 27, Funktionscode `060ce5b7a1f597ec55d28255dcd07a296e6da73f`, 228 native Cocoa-Fälle in 62,180 s (221 bestanden/sieben Windows-Skips). Vollständiger Export/Vorschau/Reimport aller vier Bestandteile über den regulären Swift-Einstieg auf dem nativ geprüften Vorläufer `06244b77a57bb59a27816d049d8814ea28fb1d16`; Datenpipeline und QML anschließend unverändert, finale Dienststatus-Abfrage zusätzlich per GUI-Roundtrip geprüft. Finales Paketlayout bei 150 % ohne QML-Warnungen. Produktivinstallation und öffentlicher Download verifiziert; Modelle, Einstellungen, Verlauf, SMB und Anmeldestart erhalten. [Release-Verifikation](../releases/v1.5.0/macos-verification.json). Der Windows-CI-Reimport ist erfolgreich; eine native Windows-EXE-Veröffentlichung dieser neuen Funktion ist separat offen.
