# Warteschlange, Transkriptöffnung und Dateierkennung

Nutzerauftrag vom 18.11.2026: Die mittlere Spalte muss sämtliche wartenden Aufträge sichtbar und bedienbar machen. Zusätzlich TXT direkt mit der OS-Standardanwendung öffnen, frühere Ergebnisse erkennen und laufende Aufnahmen vor verfrühter Verarbeitung schützen.

## Umsetzung

- Mittlere Spalte: laufender Auftrag mit gezieltem Abbruch, darunter virtualisierte vollständige Warteschlange. Dateiname/Pfad, Position, Status, Größe, bekannte Audiodauer, Einreihzeit, Modell/Sprache/Gerät und Optionen; unbekannte Dauern werden nicht geschätzt. Details für jeden Eintrag, auch außerhalb der 250 Verlaufseinträge.
- Reihenfolge per internem Drag-and-drop oder Menü ändern: als Nächstes, einen Platz vor/zurück, ans Ende. SQLite speichert die Reihenfolge unabhängig vom ursprünglichen Erkennungsdatum. Neu erkannte Dateien kommen ans Ende. Der Dienst prüft die Reihenfolge beim tatsächlichen Beanspruchen erneut.
- Einzelne Einträge entfernen: terminaler Zustand `cancelled`, Original und vorhandene TXT bleiben erhalten; dieselbe Dateiversion wird beim nächsten Scan nicht erneut eingereiht. Wiederholung ist über den Verlauf ausdrücklich möglich.
- Aktuellen Auftrag abbrechen: persistente Abbruchanforderung, lokale Kopie überprüft sie zwischen Blöcken, Inferenzmonitor beendet den zugehörigen Prozessbaum. Windows verwendet das bestehende Job Object, Unix eine eigene Prozessgruppe. Abbruchanforderungen bleiben auch nach Dienstabsturz erhalten. Ein bereits begonnener Export wird nicht unterbrochen.
- Alle abbrechen: wartende Aufträge und automatische Wiederholungen beenden, laufende Transkription abbrechen, Warteschlange pausieren. Neue Dateien werden weiterhin erfasst; erst Fortsetzen startet sie. Einzelnes Pausieren lässt den aktuellen Auftrag fertiglaufen.
- Detailansicht: `Transkript öffnen` über `QDesktopServices.openUrl` mit lokaler Datei-URL. Das Betriebssystem wählt seine Standardanwendung. Fehlende TXT oder abgelehnte Öffnung liefern eine Meldung. Finder/Explorer bleibt eine eigene Aktion.

## Dateidatenbank

Die vorhandene lokale SQLite-Datenbank bleibt erhalten. Zusätzliche Tabellen verwalten Queuepositionen, Queuepause, Abbruchanforderungen und Beziehungen zu bekannten Ergebnissen; vorhandene Aufträge werden in bisheriger Reihenfolge migriert.

Eine TXT direkt neben einer Aufnahme wird schon beim Scan als `TXT bereits vorhanden` eingeordnet. Die App startet dafür keine automatische KI-Verarbeitung. Dies ist eine erkannte Bestandsdatei, keine nachträgliche Bestätigung ihrer inhaltlichen Richtigkeit. `Neu transkribieren` erzeugt weiterhin einen eigenen Ergebnisnamen und schützt das vorhandene TXT.

Bei neuen Namen/Pfaden wird der SHA-256-Inhalt der stabil übernommenen Aufnahme mit früher erfolgreich verarbeiteten Aufnahmen verglichen. Identische Bytes lösen keine erneute ASR aus. Ist das frühere TXT anhand seines gespeicherten Hashes unverändert verfügbar, übernimmt der normale geschützte Veröffentlichungspfad den Inhalt neben die neue Aufnahme. Das alte Ergebnis bleibt erhalten. Fehlt es, wird die frühere Verarbeitung angezeigt; eine neue Verarbeitung braucht eine ausdrückliche Neutranskription. Neu encodierte Dateien haben andere Bytes und sind durch diesen Vergleich nicht als gleicher Inhalt identifiziert.

Unter Windows prüft der Dienst vor Beginn, ob ein bestehender Schreibzugriff das Öffnen ohne `FILE_SHARE_WRITE` verhindert. So wird auch eine momentan unverändert große, weiterhin geöffnete Aufnahme zurückgestellt. Wiederholung nach fünf Sekunden ohne ASR. Grundlage: [Microsoft-Dateizugriff und Freigabemodi](https://learn.microsoft.com/en-us/windows/win32/fileio/creating-and-opening-files). Größen-/Zeitstabilität, verifizierte Kopie und Schutz gegen Änderungen während der Verarbeitung bleiben erhalten. Der native Test verwendet einen offenen synthetischen Schreiber; eine echte OBS-Aufzeichnung mit allen OBS-Ausgabevarianten wird dadurch nicht behauptet. Unter macOS bleibt die bisherige Stabilitäts-/Versionsprüfung erhalten; der Windows-Schreibzugriffsadapter ist dort nicht aktiv.

Die zuvor beobachtete UIA-Pfadabweichung wird über `onTextChanged` statt ausschließlich `onTextEdited` korrigiert. Ein echter QML-Test ändert den Text programmatisch und prüft den anschließend gespeicherten Controller-Entwurf.

## Prüfstand vor Paketabnahme

Native Windows-Suite auf dem vorliegenden Quellstand: 108 Fälle in 22,011 s, 101 bestanden und sieben bekannte explizite Skips (Mac-Migrationen/Windows-Symlinkrecht). Neu geprüft: 301 Einträge über der bisherigen Verlaufsgrenze, persistente Reihenfolge und erneute Claim-Prüfung, echtes QML-Maus-Drag-and-drop, Abbruch/Rücknahme/Neustart, echter Kind-/Enkelprozessabbruch mit temporärer Bereinigung, vorhandene TXT und separate Neutranskription, Umbenennung mit Wiederverwendung sowie unverändert offener Windows-Schreiber. Standardöffner mit lokaler URL und programmatischer Pfadänderung ebenfalls geprüft. Layout mit 233 synthetischen Einträgen gerendert und visuell kontrolliert.

Frühere Zwischenläufe enthielten eine ungültige neue Testkonfiguration (gleicher Legacy-Eingangs-/Ausgabeordner), einen QObject-Lookup statt visueller Delegate-Suche und eine alte Zwei-ASR-Erwartung für bytegleiche Testdateien. Testeinrichtung korrigiert; unabhängige Aufnahmen im Routingtest haben jetzt unterschiedliche synthetische Bytes, die Inhaltswiederverwendung hat einen eigenen Test. Diese Zwischenläufe waren keine bestandene Abnahme.

Paket-/CUDA-Abnahme und endgültiger getesteter SHA werden nach dem unveränderten nativen Build ergänzt. Installierter Produktivstand ist bis zum geprüften Update weiterhin Preview 4; automatische Folgeaufträge sind für die Updatevorbereitung pausiert, aktueller Auftrag bleibt erhalten. Keine gemeinsame Mac-Freigabe; Änderungen bleiben im Draft-PR.
