# Verarbeitungsverlauf, Bestand und vollständige Bereinigung

Nutzerentscheidung vom 18.11.2026: Ein nie gestarteter, entfernter Queueeintrag gehört nicht in den Verarbeitungsverlauf. Intern darf seine Unterdrückung erhalten bleiben. Die ausdrücklich gewählte Aktion „Verlauf leeren“ muss dagegen sämtliche Auftrags-/Dateiversions-/Suchdaten entfernen. Bei aktiver Überwachung soll der nächste reguläre Scan alles neu erfassen. Außerdem muss die neue Icon-Vorlage außen transparent sein.

## Aktueller Stand

[Windows Preview 11](https://github.com/adriantagonist87/VoxDrop/releases/tag/v1.3.2-windows-preview.11), App-Code `2a1ae7feb5c9c2125b20e630875bed13b316250e`, ZIP-SHA-256 `83822f1f5d39d48cf8328c67013699d6001cfdb675deeaa40cf6940ba91b3a86`. ZIP `VoxDrop-1.3.1-Windows-x64-2a1ae7feb5c9.zip`, 45.983.289 Byte. Interne Version 1.3.1, keine neuen Abhängigkeiten oder Modell-/Lockfileänderungen. Windows installiert, gemeinsam geänderter App-Code im Draft-PR bis nativer Mac-Gegenprüfung. Icon-Dateien und Übergabedokumentation auch auf main aktualisiert.

## Sichtbare Kategorien

| Ansicht | Inhalt |
| --- | --- |
| Alle | Erfolgreiche und fehlerhafte Verarbeitungen sowie nach Start abgebrochene Aufträge |
| Fertig | `done`, ausgenommen nur übernommene frühere Ergebnisse |
| Fehler | `failed` und `blocked`, einschließlich konkreter Fehler vor erfolgreichem Inferenzstart |
| Abgebrochen | `cancelled` mit früherem Verarbeitungsversuch oder gespeichertem Start; kein Fehler |
| Bestand | Vorhandene TXT, identische bekannte Aufnahmen und übernommene Ergebnisse; nicht als neue Erfolge zählen |

Nie gestartete Abbrüche (`attempt=0`, kein Start) und rein ersetzte Dateiversionen sind intern weiter gespeichert, aber im normalen Verlauf unsichtbar. So reiht die Überwachung entfernte Dateien nicht sofort wieder ein. „Alle“ enthält den Bestand ausdrücklich nicht. Zähler gelten vor dem 250-Zeilen-Limit und berücksichtigen die aktuelle Pfad-/Inhaltssuche. Bei „Bestand“ bleiben Standard-TXT-Öffnung, Ordneranzeige und geschützte Neutranskription erreichbar. Die Bestandszählung zählt gespeicherte Aufträge, nicht zwingend unterschiedliche TXT-Dateien.

Das neue leichte Engine-Modul `history_store.py` definiert Kategorien, Speicherrevision und Suchsperre. Alle Windows-/Mac-Builder nehmen es auf. Controller-Fallback und CLI verwenden dieselbe Kategorisierung; die Oberfläche bietet die beiden weiteren Filter in einer zweiten Zeile, auch bei Mindestbreite.

## Verhalten von „Verlauf leeren“

Die Aktion bleibt auch bei leerem sichtbarem Verlauf, aktivem Filter oder ausschließlich internen Abbrüchen/Suchcache erreichbar. Der Bestätigungsdialog beschreibt den globalen Umfang einschließlich Warteschlange. Eine laufende eigene Detailsuche wird zuerst beendet; während eines aktiven Kopier-/Transkriptions-/Exportauftrags ist die Aktion gesperrt. Der Nutzer kann diesen Auftrag zuvor über die vorhandene Abbruchfunktion beenden oder ihn fertiglaufen lassen.

Gelöscht werden alle Aufträge, Events, Mess-/Sprecherdaten, Ergebnis-/Hashbeziehungen, Queuepositionen, Abbruch-/Wiederaufnahme-/Sofort-Auswahlabsichten, Droppläne, Dateiversionen, Ordnerprüfstände und lokale Auftragsarbeitskopien. Lokaler FTS-Index einschließlich WAL/SHM, Ergebnis-JSON und abgebrochene Such-Temporärdateien werden entfernt. Einstellungen, Modell-/Laufzeitspeicher und die Medien/TXT auf den überwachten Laufwerken bleiben erhalten. Es gibt keine Transkript-/Medienlöschung. Schema und wenige Betriebskennungen bleiben bestehen; insbesondere werden monotone Auftrags-IDs nicht wiederverwendet und die Queuepause bleibt erhalten. Es bleiben keine fachlichen Auftrags-/Suchdatensätze als versteckter Verlauf zurück.

`BEGIN IMMEDIATE` und Aktivitätsprüfung sichern die SQL-Bereinigung. Cache-/Arbeitsdateien werden lokal vor Commit umbenannt und bei einem Fehler vor Commit zurückgestellt. `secure_delete`, `VACUUM` und WAL-Checkpoint entfernen gelöschte Dateninhalte und verkleinern die DB. Ein nach Commit blockierter temporärer Rest wird sichtbar gemeldet und kann über dieselbe Aktion erneut bereinigt werden; die Schaltfläche berücksichtigt solche Reste. Recursive Entfernung ist auf geprüfte eigene `.history-clear-*`-Pfade im lokalen Profil begrenzt; Verknüpfungen werden abgewiesen.

`storage_state.generation` wird erhöht. Vorher begonnene Scans dürfen ihre alten Dateilisten nicht zurückschreiben. Der Dienst verwirft seinen alten Zeitplan und liest bei aktiver Überwachung im nächsten konfigurierten Intervall neu ein. Vorhandene benachbarte TXT zu erfassten Medien werden wieder als Bestand übernommen; Medien ohne TXT werden neu eingereiht. Es gelten weiterhin die konfigurierten Ordner und Rekursionseinstellungen. Eine bewusst pausierte Queue bleibt pausiert, eine deaktivierte Überwachung wird nicht eingeschaltet. Die nächste ausdrücklich gestartete Detailsuche baut ihren Cache aus den neu erfassten Ergebnissen auf.

Suchprozess und Reset verwenden dieselbe OS-Dateisperre. Suchergebnisse enthalten zusätzlich die Speicherrevision; alte Tokens werden nach Reset abgewiesen. Die GUI wartet vor Bereinigung auf das Ende ihres eigenen Suchprozesses und verwirft ältere noch ausstehende Metadatenantworten. Produktive Bereinigung wurde nicht als Installationstest ausgeführt.

## Transparente Grafik

Die durch `imagegen` freigestellte Fassung ersetzt PNG-Master, ICO und GitHub-Vorschau. Weiße Zeichen im grünen Motiv bleiben erhalten. RGBA-PNG-Ecken und 256-Pixel-ICO-Ecken haben Alpha 0; Antialiasing bleibt erhalten. Native Windows-Ressourcen-API bestätigt alle sieben eingebetteten Iconbilder bytegenau. Gegen hellen/dunklen Hintergrund geprüft. [Prompt, Werkzeug und Dateien](ICON_FREISTELLUNG.md). Aktuelle Hashes: PNG `bafd2bd8e243adb0a4020efdf7f037125dda9c1b0bd6db437aca4e84a88135ec`, ICO `f74f4736730303b31bf295b2bf81f436c769b93bf5561e58cabf5af261df6816`, README-Vorschau `b60b410d99b94d8680fac70db73f86acc545a1f864f150f0d0f0752f7e6c4329`. Statuswellen unverändert, Logo-Header bleibt entfernt.

## Windows-Nachweise

144 Fälle in 54,338 s: 137 bestanden, sieben bekannte Skips (fünf Mac-Migrationen, zwei Windows-Symlinkrechte). Einschließlich 18 vollständiger Qt-Fälle und gezielter Prüfungen: 8.000 nie gestartete Abbrüche, alle Kategorien/Zähler, vollständige SQL-/Cache-/Dropbereinigung, Medien-/TXT-Erhalt, Wiederimport und erneute Inhaltssuche, alter Scan/Token nach Reset, aktive Suchsperre, sichtbar fehlgeschlagene/erneut mögliche Cachebereinigung, Bestätigung bei aktivem Filter und Verwerfen einer alten GUI-Statusantwort.

Finales unverändertes Paket über EXE in isoliertem Profil in 13,893 s bestanden. Nach Queueabbruch keine sichtbare Verarbeitung und keine automatische Doppeleinreihung; vorhandenes TXT separat suchbar. Echter CLI-Reset leert alle Fach-/Cachetabellen und Dateien. Dienst erfasst beim nächsten Zwei-Sekunden-Testintervall ohne manuellen Scan vorhandenes TXT und wartendes Medium neu. TXT anschließend wieder per Paket-Inhaltssuche auffindbar. Tatsächlicher QML-Bestätigungsdialog ruft reale CLI auf und leert echte DB/Index. Originalhashes, SQLite und Fremdschlüssel bestätigt. Bestand und Bereinigungsdialog bei 1500×1000 und 1010×630 visuell geprüft. Native Inferenz-/Jobbeanspruchungsfunktionen unverändert; frühere CUDA-Belege behalten ihre damaligen SHAs.

Mit installiertem Preview-11-Code erneut über 20.000 synthetische Datensätze gemessen: Pfadabfrage plus alle Kategorie-Zähler im Median rund 214 ms, reine bestehende FTS-Abfrage rund 0,9 ms. Frühere Erstindex-/Abbruchmessungen bleiben auf dem vorherigen dokumentierten Code; hier kein erneuter kompletter Inhaltsindex behauptet.

## Tatsächliches Update und Mac-Übergabe

Direkter GitHub-Download/SHA und alle 89 installierten Dateien bestätigt. Im vom Nutzer bereits pausierten Leerlauf (kein aktiver Auftrag) vollständiges Profil mit 41 Dateien und alten Code hashgesichert, danach Dienst/GUI regulär neu gestartet. Modelle/Laufzeit und aktuelle Nutzerkonfiguration erhalten. Alle 9.143 vorher vorhandenen Auftragsidentitäten/Dateiversionen vorhanden, SQLite/Fremdschlüssel `ok`. Kontrollstand: 8.869 wartend und weiterhin pausiert, kein aktiver Auftrag. Installierte Accessibility-Zähler: Alle 1, Fehler 0, Fertig 1, Abgebrochen 0, Bestand 273. Der neue Filter ändert keine produktiven Aufträge und löst keine produktive Bereinigung aus. Die früheren Einzelordner-/Leerprofilstände wurden nicht zurückgespielt.

Mac: aktuellen PR-Code prüfen, `history_store.py` im Bundle verifizieren, native Suite/Cocoa und alle fünf Ansichten ausführen. Reset einschließlich FTS-Dateisperre über `fcntl`, Unix-Suchprozessabbruch, SQLite-VACUUM/Fremdschlüssel und parallele Scanner prüfen. Nach Reset regulären nächsten Intervall, Bestand/Wildcards/Detailsuche und Pauseerhalt nachweisen. Transparentes ICNS/Dock/Finder neu bauen und alte Menüleisten-Statuswellen erhalten. Bisherigen Mac-Prüfstand `df207f79aa812f70d090e4306443436d51d48952` bewahren; gemeinsame Integration erst nach Gegenprüfung.
