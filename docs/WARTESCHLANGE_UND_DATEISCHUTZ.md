# Warteschlange, Transkriptöffnung und Dateierkennung

Nutzerauftrag vom 18.11.2026: Die mittlere Spalte muss sämtliche wartenden Aufträge sichtbar und bedienbar machen. Zusätzlich TXT direkt mit der OS-Standardanwendung öffnen, frühere Ergebnisse erkennen und laufende Aufnahmen vor verfrühter Verarbeitung schützen.

## Aktueller geprüfter Windows-Stand

[Preview 5](https://github.com/adriantagonist87/VoxDrop/releases/tag/v1.3.2-windows-preview.5), App-Code `94e333153db90dc57c917575a8ba39040716a170`, ZIP-SHA-256 `c6ebc9d660e4ea9e2b9356bcc08023b28f73179f03f5d50b107f36dcf0c04d6c`. Interne Version weiterhin 1.3.1. Unverändertes natives ZIP vor Veröffentlichung über EXE geprüft, danach erneut unmittelbar von GitHub heruntergeladen, Prüfsumme und alle installierten Paketdateien verglichen. Keine Überlagerung aus dem Entwicklercheckout.

Echte Paketabnahme mit isoliertem Profil und synthetischen Medien in 80,542 s bestanden: Reihenfolge vor Start geändert und Einzelauftrag entfernt; tatsächlichen Qwen-Auftrag nach dekodierter Audioanlage abgebrochen, null verbleibende Inferenzprozesse und Arbeitsordner bereinigt. Deutscher CUDA-Auftrag erfolgreich. Umbenennung derselben Aufnahme übernahm das hashgeprüfte Ergebnis ohne neue ASR. Englische ausdrückliche Neutranskription erfolgreich unter eigenem Namen bei erhaltenem altem TXT. Ein unverändert offener Schreiber blockierte Verarbeitung bis zum Schließen. Alle abbrechen, Pause und Abbruchstatus blieben über einen echten Dienstneustart erhalten. Originalhashes und SQLite-Integrität bestätigt.

Der tatsächlich ausgelieferte Controller hat zusätzlich eine synthetische TXT mit realem Windows-Qt-Plattformadapter über eine lokale Datei-URL an die OS-Standardanwendung übergeben; `openUrl` wurde nicht durch einen Erfolgsmock ersetzt und das Betriebssystem akzeptierte den Aufruf. Die sichtbare Editoransicht ist damit nicht separat abgenommen.

Produktivupdate vor Beginn mit null aktiven Aufträgen und SQLite `ok` abgesichert. Vollständiges Profil und alter App-Code privat kopiert und pro Datei hashverglichen. Laufzeit-/Modellmanifeste bytegleich, Modelldateimetadaten unverändert, keine erneuten großen Downloads. Danach vorherige produktive Überwachung wieder aktiviert. Alle 241 bisherigen Auftrags-IDs, Quellen, Größen, Dateiversionen, Erkennungszeitpunkte und Ursprungsbeziehungen erhalten; Fremdschlüssel und SQLite `ok`. Alle 97 schon vor der Neuinstallation vorhandenen TXT weiterhin hashgleich.

Beim Kontrolllauf wurden 200 Aufträge mit vorhandenem benachbartem TXT erkannt; 31 warteten und einer wurde verarbeitet, neun waren bereits abgeschlossen. Die kleinere Arbeitswarteschlange beruht auf Bestands-/Ergebniserkennung; Medien wurden dafür nicht gelöscht. Im installierten Fenster bestätigt der Accessibility-Baum die neue Liste und ihre Bedienelemente. Eine Bildschirmaufnahme zeigte den darüberliegenden Browser; die eigenständige visuelle Layoutprüfung verwendet deshalb den tatsächlichen QML-Render mit synthetischen Einträgen. Keine produktiven Lösch-/Abbruch-/Reorder-Aktionen zu Testzwecken ausgeführt.

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

Paket-/CUDA-Abnahme und Produktivupdate sind im aktuellen Stand oben ergänzt. Die für das Update vorübergehend pausierte automatische Überwachung ist wieder aktiv. Keine gemeinsame Mac-Freigabe; Änderungen bleiben im Draft-PR. Auf dem Mac insbesondere neue Module in der Paketliste, SQLite-Migration, Prozessgruppenabbruch, QML-Drag-and-drop, Standardöffner und Pfadsignal gegenprüfen. Der Windows-Schreibzugriffsadapter ersetzt keine native Mac-Prüfung offener Schreiber.
