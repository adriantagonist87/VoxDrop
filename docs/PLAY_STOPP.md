# Kompakte Play-/Stopp-Steuerung

Oben in der mittleren Spalte steht ein normaler quadratischer Knopf mit festen **44 × 44 logischen Pixeln**: grün mit Play-Dreieck oder rot mit Stopp-Quadrat, daneben eine normale Beschriftung. Er wächst im Vollbild nicht mit und bewegt sich beim Wechsel des aktuellen Auftrags nicht. Beim Anhalten erscheint „Wird gestoppt …“; erneuter Start ist erst nach dem tatsächlichen Ende möglich. Die zuerst gebaute breite Variante wurde auf Nutzerkorrektur durch diesen kompakten Knopf ersetzt.

**Starten** aktiviert die Verarbeitung der bestehenden Warteschlange, auch bei ausgeschalteter Ordnerüberwachung. Seit 23.11.2026 öffnet **Stopp** zuerst eine [Auswahl mit sofortigem Stopp, geregeltem Fertigstellen und Abbruch](UEBERWACHUNG_UND_STOPP.md). Erst „Transkription sofort stoppen?“ pausiert die weitere Verarbeitung und beendet eine gerade laufende Erkennung samt Modellprozessen. Der unterbrochene Auftrag kehrt an seinen bisherigen Platz zurück. Die wartenden Dateien bleiben erhalten. Beim erneuten Start beginnt eine unterbrochene Erkennung neu; es gibt keinen behaupteten Modell-Checkpoint mitten in einer Aufnahme.

Ist die Erkennung bereits fertig und ihr Ergebnis wird gespeichert oder aus einem vollständigen Cache exportiert, wird dieser sichere Abschluss noch beendet. Danach bleibt die Warteschlange gestoppt. Ein bereits ausdrücklich entfernter Auftrag wird durch Stopp nicht wiederhergestellt.

Die Ordnerüberwachung darf weiterhin neue Dateien einreihen; ihre Ein-/Ausschaltung ist jetzt auch direkt links neben der Statusanzeige erreichbar. Stopp hält die Verarbeitung an. Die getrennte Option „Nach diesem Auftrag pausieren“ und die geregelte Popupauswahl lassen den laufenden Auftrag fertigwerden. **„Warteschlange leeren …“** entfernt nach Bestätigung Aufträge und ist absichtlich von Stopp getrennt. Das vollständige Beenden der App bleibt die eigene Tray-Aktion.

## Technik und Prüfung

`stop-queue` setzt in einer SQLite-Transaktion die Queuepause, entfernt Sofort-Auswahlen und markiert die aktive unvollständige Erkennung für den vorhandenen Abbruch-/Wiederaufnahmepfad. Queuepositionen und gespeicherte Auftragsoptionen bleiben unverändert. Fertiger Export und vorhandener `text_hash` werden geschützt. `start-queue` weist einen noch laufenden Abbruch zurück, damit der ursprüngliche Auftrag vor einer Wiederaufnahme sicher in der Queue steht. Die GUI zeigt den tatsächlichen bzw. noch bestätigten Stoppstatus; Fehler lösen die lokale Wartesperre wieder.

## Finaler Prüfstand

Normaler quadratischer **44 × 44**-Knopf an fester Stelle oben in der Mitte: grünes Play zum Starten, rotes Stopp zum Anhalten. Er wächst im Vollbild nicht mit. Stopp beendet die aktuelle Erkennung, erhält die Queue samt Reihenfolge und wartet vor erneutem Start auf deren tatsächliches Ende. Fertiger Export wird noch abgeschlossen. „Warteschlange leeren …“ bleibt getrennt. Die zunächst breite Variante wurde auf Nutzerkorrektur ersetzt. [Bedienung und Grenzen](PLAY_STOPP.md).

Geprüfter Code `a7166f0039f9aafb1c710079f167c22b4512595f`, [Windows v1.3.5](https://github.com/adriantagonist87/VoxDrop/releases/tag/v1.3.5), ZIP-SHA-256 `adc19a6ad86e299099050e545357e9435caf22df6c9d57b29efbfa2c52e33ec4`, [93-Dateien-Manifest](../releases/v1.3.5/windows-release.json). 180 Tests in 51,249 s, 173 bestanden/sieben bekannte Plattformskips. Native finale Paketprüfung in 63.608 s: echte QML-Klicks Play → Stopp während CUDA-Qwen → Play, Modellprozesse nach 0.953 s beendet, Queue/Optionen/Originalhashes erhalten, gestoppter Zustand bleibt bestehen, erfolgreiche Wiederaufnahme vor folgendem Cache-Export bei ausgeschalteter Überwachung. SQLite/Fremdschlüssel ok. Größenregression normal/maximiert/Vollbild durchlaufen. Laufzeit, Modelle und GPU-Budget unverändert.



Für den Mac: `PlaybackButton.qml` im rekursiv kopierten Desktop-Bundle prüfen. Gemeinsame SQLite-/CLI-Semantik ist unverändert portierbar; echtes Modellprozess-Ende, Wiederstart, Abschluss eines laufenden Exports und feste Schaltflächenposition unter Cocoa müssen nativ geprüft werden. Keine neue Mac-DMG durch die Windows-Abnahme behaupten.
