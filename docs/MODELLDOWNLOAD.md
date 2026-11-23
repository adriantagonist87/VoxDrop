# Fortschritt und Erreichbarkeit beim Modelldownload

## Bedienung

Unter **Einstellungen → Transkription** zeigt die Modelleinrichtung die bisher vorhandenen/heruntergeladenen Dateidaten, die Gesamtgröße und den daraus berechneten Prozentwert. „Dateien anzeigen“ öffnet die einzelnen Dateien mit Größe, Position und Status. Die aktuelle Downloadrate und die in diesem Versuch übertragenen Netzwerkbytes stehen getrennt darunter. Bereits vorhandene Dateien und Cache-Daten zählen zum Dateifortschritt, aber nicht als neuer Netzwerktransfer.

Solange die Größen noch nicht ermittelt sind, steht dort „Gesamtgröße noch unbekannt“ mit unbestimmtem Balken. Prüfsummenprüfung und Ablage im Modellspeicher haben eigene Phasen. 100 % der Dateidaten ist erst zusammen mit erfolgreicher Verifikation eine abgeschlossene Einrichtung. Bei fehlenden neuen Daten fallen Rate und Empfangsstatus ab; ein Zeitwert macht den Stillstand sichtbar. Download abbrechen beendet den eigenen Prozessbaum; ein späterer Versuch kann die vorhandenen Daten weiterverwenden.

**Server prüfen** prüft unabhängig vom Download die aktuell gewählten Modelle. Zuerst wird eine gepinnte Modelldatei auf Hugging Face angefragt, anschließend deren tatsächlicher Downloadpfad einschließlich Weiterleitung/CDN mit einem kleinen Range-Abruf. Ergebnis, Host, Uhrzeit und gemessene Verbindungsdauer werden angezeigt. HTTP-Fehler, Zeitlimit und lokales WinError 10013 sind unterschiedliche Befunde. Ein fehlgeschlagener lokaler Abruf behauptet keinen weltweiten Serverausfall. Die Prüfung lässt sich abbrechen und während eines Downloads erneut starten. Alte Ergebnisse für eine andere Modell-/Sprecherauswahl werden verworfen.

## Ursache und Implementierung

Vorher rief der Controller `setup-models` blockierend über `communicate()` auf. QML erhielt erst nach Prozessende das Ergebnis und zeigte währenddessen ausschließlich einen unbestimmten Balken.

Der eigene kurzlebige Prozess `Engine/model_download.py` gibt strukturierte, sofort gespülte JSON-Zeilen aus. `desktop/command_process.py` leert beide Pipes parallel, begrenzt gespeicherte Ausgabe und leitet Ereignisse vor Prozessende weiter. Der Controller übernimmt sie per Qt-Signal; Generationen verhindern verspätete Änderungen nach Auswahlwechsel, Abbruch oder App-Ende. Eine separate Serverprüfung ersetzt keine laufenden Fortschrittswerte.

Dateigrößen stammen aus der gepinnten Hub-Dateiliste bzw. dem tatsächlichen Datei-Transfer. Dateiposition, Resume-Offset und Netzwerktransfer sind getrennte Zähler. Beim gepinnten Windows-Hub **1.33.0** werden pro Datei die `tqdm_class`-Callbacks und bei Xet dessen `update_transfer` benutzt; rekonstruierte Dateibytes ergeben den Fortschritt, tatsächlich übertragene Bytes die Rate. Ein drei Sekunden umfassendes Zeitfenster glättet die Rate. Ein Prozess-lokaler Kontext setzt den HTTP-Leseblock auf 64 KiB für zeitnahe Aktualisierungen und stellt alle Downloader-Bindungen/Einstellungen auch im Fehlerfall wieder her. Vendorquellen und Abhängigkeitspins bleiben unverändert.

Die bisherigen vollständigen SHA-256-Prüfungen und die atomare Qwen-Ablage bleiben maßgeblich. Vollständig vorhandene Modelle lassen sich ohne Größenauskunft oder Downloadserverzugriff erneut verifizieren. Modellgewichte und Hub-Cache bleiben im vorgesehenen Modellspeicher des App-Ordners. Keine Datenbankmigration, keine zusätzliche Laufzeit, kein neuer öffentlicher Release.

## Windows-Prüfstand vom 23.11.2026

Funktionaler Code **`79d42538022573fc32d6927115c99ebf3c4dc9c3`**, Branch [`fix/model-download-progress`](https://github.com/adriantagonist87/VoxDrop/tree/fix/model-download-progress), [PR #25](https://github.com/adriantagonist87/VoxDrop/pull/25). Python 3.12.13, Qt 6.10.2 und Hugging Face Hub 1.33.0 unter Windows 11. [Bereinigter Nachweis](pruefungen/2026-11-23-windows-modelldownload.json).

Der [GitHub-Windows-Check des funktionalen Commits](https://github.com/adriantagonist87/VoxDrop/actions/runs/45157030808) ist erfolgreich; dieser führt auch den Arbeitsübersichtstest mit 8.000 wartenden und 20.000 historischen Aufträgen aus.

- Vollständige Quell-Suite vor den letzten Randfalltests: 251 Fälle, 239 bestanden/zwölf bekannte Plattform-Skips in 154,982 s. Anschließend alle 48 betroffenen Regressionen mit finalem Code: 47 bestanden/ein Skip in 16,725 s.
- Vollständiger lokal kombinierter Stand mit vorhandenem Player aus `6278335acb6589a97b4973c26cf0e931fb5ac369` und SMB-Fix aus `f43e27fdf74dda4b1a492513cc548b9f7a4a54f1`: **276 Fälle, 264 bestanden/zwölf Skips in 155,678 s**. Enthält neue Größen-/Resume-/Xet-/Server-/CLI-/QML-/Abbruchregressionen sowie die bisherigen Player- und Drop-Fälle.
- Echter HTTPS-Download zweier kleiner gepinnter Whisper-Dateien: 2.483.945 Byte, zehn Ereignisse, SHA-256 korrekt, Cache-Wiederholung null neue Transferbytes. Zusätzlich echte gepinnte binäre Xet-Datei: 133.852 Dateibytes und 133.876 Transferbytes, SHA-256 korrekt. Dieser Unterschied bestätigt die notwendige Trennung beider Zähler.
- Künstlicher HTTP-Test mit realem gepinntem Hub-Transport: Übertragung von 524.288 Byte nach 131.072 Byte zwangsweise getrennt; Range-Wiederaufnahme am exakten Offset, unveränderter Inhalt, Zwischenfortschritt und positive aktuelle Rate bestanden.
- Native Windows-QML bei Mindestgröße 1010 × 630 und Qt-Skalierung 100/125/150 %: sichtbarer 25-%-Balken, Byte-/Ratenanzeige, langer Dateiname, aufklappbare Liste, unbekannte Gesamtgröße und Verifikationsphase bestanden. Echter QML-Serverknopf → Controller → CLI → API/CDN → Qt-Signal mit allen drei Modell-Dateipfaden erfolgreich. Dies ist keine Prüfung physischer Windows-Skalierungseinstellungen.
- Serverprüfung vom betroffenen PC: gepinnte Sprecher-, Qwen-ASR- und Aligner-Gewichte über Hugging Face sowie `us.aws.cdn.hf.co` erreichbar. Das ist eine zeitpunktbezogene lokale Messung.
- Nach lokaler Installation normaler EXE-Neustart mit lebendem registrierten GUI-Eigentümer. Die tatsächlich installierte Engine verifiziert Whisper (sieben Dateien/1.621.440.951 Byte) sowie Qwen, Aligner und Sprecher (23 Dateien/5.968.549.656 Byte) vollständig gegen ihre Pins; Netzwerkaufrufe waren im Test untersagt, Transfer jeweils null Byte.

Ein erster Testlauf in der eingeschränkten Werkzeug-Sandbox scheiterte an verweigertem Windows-Registry-/Temp-Zugriff. Der normale native Testlauf bestand. Der erste kombinierte Paket-Testaufbau war kein Python-Quellcheckout und konnte die Test-Pakete nicht importieren; der korrekt aufgebaute kombinierte Checkout bestand anschließend vollständig. Beide Befunde betrafen den Testaufbau.

Kein erneuter großer Gewichtsdownload nur für diesen Test, keine neue Inferenz-/GPU-Freigabe, kein physischer Neustart-/Autostart- oder wochenlanger Dauertest in diesem Änderungsschritt. Die geplante vollständige Deinstallation, Bereinigung und Installation von GitHub mit anschließender Produktivabnahme bleibt ein eigener späterer Test auf Nutzeranweisung.

## Lokales Update und Mac-Übergabe

Die vorhandene Windows-App wurde als lokaler Entwicklungsstand aktualisiert. Profil und alte Programmdateien sind gesichert. Fünf bisherige Dateien wurden ersetzt, drei neue ergänzt; die übrigen 93 vorherigen Programmdateien einschließlich SMB-Engine bleiben erhalten. Controller und Haupt-QML kombinieren ausdrücklich Player und Downloadänderung. `local-development.json` enthält alle Overlay-Dateihashes und die beteiligten Code-Commits; `build-info.json` bezeichnet weiterhin das Basispaket 1.5.1. Queue, Reihenfolge, Konfiguration, Layout, Modelle, Runtime und die bereits vorhandene Pause blieben erhalten. **Kein neuer Release und kein öffentliches Build.**

Der gemeinsame Funktionscode bleibt bis zur nativen Mac-Gegenprüfung in PR #25. `main` erhält gemäß Auftrag nur den separaten Dokumentationsstatus. Native Mac-Freigabe bleibt 1.5.0 Build 27; diese Downloadänderung ist **UNGEPRÜFT unter macOS**. Vor Integration auf dem Mac:

1. Gegen die dort tatsächlich verwendete Hub-Version prüfen; die separate Qwen-Umgebung pinnt einen anderen Hub als Windows. Pro-Datei-Callbacks, Snapshot-Bindung und Xet-Zähler nativ nachweisen, gegebenenfalls einen Adapter im PR ergänzen.
2. Whisper sowie Qwen/Aligner/Sprecher herunterladen, abbrechen/wiederaufnehmen und aus Cache verifizieren. Rate darf Cache-/Resume-Dateibytes nicht als aktuellen Transfer zählen. Fehler, fehlende Größen und Prüfsummenfehler durchspielen.
3. API-/CDN-Test, Zeitlimit, Abbruch und Modellwechsel einschließlich verspäteter Ergebnisse prüfen; Oberfläche mit schmalem Fenster, langen Namen und Retina-Skalierung abnehmen.
4. App-Ende/Cmd-Q während Download/Serverprüfung muss eigene Kindprozesse beenden. Bestehende Modelle bleiben offline nutzbar und im App-Modellspeicher. Player-/SMB-PRs beim gemeinsamen Abgleich bewusst erhalten.

Gezielt reproduzierbar mit den gepinnten Abhängigkeiten: `python -m unittest discover -s tests -p test_model_download.py`, entsprechend `test_download_process.py` und `test_desktop_window.py`; vollständige CI über `scripts/ci-tests.py prepare` und `scripts/ci-tests.py run`. Der native Server-CLI-Aufruf lautet `python -BEs -Xutf8 Engine/model_download.py check-model-server --model-data <App-Modellspeicher> --model qwen3-asr-1.7b`. Persönliche Medien, Rohlogs, signierte URLs und private Pfade bleiben außerhalb des Repositorys.
