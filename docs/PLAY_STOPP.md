# Große Play-/Stopp-Steuerung

Oben in der mittleren Spalte steht ein normaler quadratischer Knopf mit festen **44 × 44 logischen Pixeln**: grün mit Play-Dreieck oder rot mit Stopp-Quadrat, daneben eine normale Beschriftung. Er wächst im Vollbild nicht mit und bewegt sich beim Wechsel des aktuellen Auftrags nicht. Beim Anhalten erscheint „Wird gestoppt …“; erneuter Start ist erst nach dem tatsächlichen Ende möglich. Die zuerst gebaute breite Variante wurde auf Nutzerkorrektur durch diesen kompakten Knopf ersetzt.

**Starten** aktiviert die Verarbeitung der bestehenden Warteschlange, auch bei ausgeschalteter Ordnerüberwachung. **Stopp** pausiert die weitere Verarbeitung und beendet eine gerade laufende Erkennung samt Modellprozessen. Der unterbrochene Auftrag kehrt an seinen bisherigen Platz zurück. Die wartenden Dateien bleiben erhalten. Beim erneuten Start beginnt eine unterbrochene Erkennung neu; es gibt keinen behaupteten Modell-Checkpoint mitten in einer Aufnahme.

Ist die Erkennung bereits fertig und ihr Ergebnis wird gespeichert oder aus einem vollständigen Cache exportiert, wird dieser sichere Abschluss noch beendet. Danach bleibt die Warteschlange gestoppt. Ein bereits ausdrücklich entfernter Auftrag wird durch Stopp nicht wiederhergestellt.

Die Ordnerüberwachung darf weiterhin neue Dateien einreihen; Stopp hält deren Verarbeitung an. Die getrennte Option „Nach diesem Auftrag pausieren“ lässt den laufenden Auftrag fertigwerden. **„Warteschlange leeren …“** entfernt nach Bestätigung Aufträge und ist absichtlich von Stopp getrennt. Das vollständige Beenden der App bleibt die eigene Tray-Aktion.

## Technik und Prüfung

`stop-queue` setzt in einer SQLite-Transaktion die Queuepause, entfernt Sofort-Auswahlen und markiert die aktive unvollständige Erkennung für den vorhandenen Abbruch-/Wiederaufnahmepfad. Queuepositionen und gespeicherte Auftragsoptionen bleiben unverändert. Fertiger Export und vorhandener `text_hash` werden geschützt. `start-queue` weist einen noch laufenden Abbruch zurück, damit der ursprüngliche Auftrag vor einer Wiederaufnahme sicher in der Queue steht. Die GUI zeigt den tatsächlichen bzw. noch bestätigten Stoppstatus; Fehler lösen die lokale Wartesperre wieder.

Erster vollständiger Windows-Lauf: 179 Fälle in 54,085 s, 172 bestanden und sieben bekannte Plattformskips. Neue Fälle: aktuelle Erkennung stoppen und geordnet fortsetzen, Wiederaufnahme nach Dienstneustart bei weiterhin gespeicherter Pause, Start ohne Überwachung, Exportabschluss, ausdrücklich entfernte Aufträge nicht wiederherstellen sowie reale QML-Mausklicks und Rot-/Grünwechsel. Native Paket-/CUDA-Gegenprüfung folgt vor Freigabe. Der erste neue QML-Prüfer verwendete nach dem Einklappen des aktuellen Auftrags noch dessen alte Klickposition; der Test wurde korrigiert und der Knopf zusätzlich an den festen oberen Ort gesetzt.

Für den Mac: `PlaybackButton.qml` im rekursiv kopierten Desktop-Bundle prüfen. Gemeinsame SQLite-/CLI-Semantik ist unverändert portierbar; echtes Modellprozess-Ende, Wiederstart, Abschluss eines laufenden Exports und feste Schaltflächenposition unter Cocoa müssen nativ geprüft werden. Keine neue Mac-DMG durch die Windows-Abnahme behaupten.
