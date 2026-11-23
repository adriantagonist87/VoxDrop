# Überwachungsschalter und Stoppauswahl

## Bedienung seit 23.11.2026

Links neben „Überwachung an/aus · Ordner …“ schaltet ein eigener Schalter die Ordnerüberwachung sofort ein bzw. aus. Er zeigt den gespeicherten Zustand und folgt auch Änderungen über Einstellungen oder Tray. Andere noch nicht gespeicherte Einstellungsentwürfe bleiben erhalten. Die Warteschlange und die laufende Transkription werden durch diesen Schalter nicht angehalten oder fortgesetzt.

Der grüne Startknopf startet weiterhin direkt. Ein Klick auf den roten Stoppknopf öffnet zunächst ein modales Popup mit drei Optionen:

- **Transkription sofort stoppen?** pausiert die Queue und beendet die unvollständige Erkennung. Der Auftrag bleibt an seiner Position und kann erneut gestartet werden. Ein bereits fertig erkanntes Ergebnis wird weiterhin sicher exportiert.
- **Transkription geregelt fertigstellen und Warteschlange pausieren** lässt den laufenden Auftrag einschließlich Sprecherphase/Export fertigwerden. Danach startet kein weiterer Auftrag. Ist gerade keiner aktiv, pausiert die Warteschlange unmittelbar.
- **Abbruch** schließt nur das Popup. Auch Escape schließt es ohne Verarbeitungsaktion.

Das Öffnen des Popups verändert noch nichts. Die Optionen verwenden den bei ihrer Betätigung aktuellen Queuezustand. „Nach diesem Auftrag pausieren“ bleibt zusätzlich direkt erreichbar. Auch während anderer Desktopaktionen bleibt der sofortige Stopp verfügbar; die geregelte Pause folgt derselben Belegtsperre wie die vorhandene Pauseaktion. Die Warteschlange wird durch keine dieser Optionen geleert.

## Implementierung und Prüfstand

Funktionaler Code **`5405d8e365171e6cecbc636c586fba866b0a7f87`**, Branch [`feat/watch-toggle-stop-options`](https://github.com/adriantagonist87/VoxDrop/tree/feat/watch-toggle-stop-options), [PR #27](https://github.com/adriantagonist87/VoxDrop/pull/27). Gemeinsame QML-Änderung in `Main.qml` und `PlaybackButton.qml`, keine getrennte Windows-Oberfläche. `PlaybackButton` meldet im Stoppmodus `stopRequested`; erst die Dialogauswahl ruft `stopProcessing()` oder `pauseQueue(true)` auf. Der Überwachungsschalter benutzt `setMonitoring()` und bindet seine Anzeige an den gespeicherten Status. Bestehende SQLite-/CLI-, Export-, Modellfreigabe- und Wiederanlaufpfade bleiben unverändert. Keine Pin-/Schemaänderung.

Neue Qt-Regressionen prüfen den Header-Schalter samt beidseitiger Zustandssynchronisation, unabhängige Konfigurationsspeicherung, Popup ohne Vorabaktion, Abbruch/Escape, geregelte Auswahl und vollständige Anzeige bei Mindestgröße. Der bisherige echte Stoppklicktest und der Stopp während anderer Desktoparbeit berücksichtigen jetzt die ausdrückliche sofortige Auswahl. Der Arbeitsübersichtstest mit 8.000 wartenden und 20.000 historischen Aufträgen rendert zusätzlich den Stoppdialog.

Der finale kombinierte Windows-Gesamtlauf umfasst **280 Fälle: 268 bestanden und zwölf bekannte Plattform-Skips in 153,465 s**. Er enthält die bisherigen Player-, SMB- und Download-Regressionen zusammen mit der neuen Bedienung. Der [aktuelle Windows-Check des funktionalen Commits](https://github.com/adriantagonist87/VoxDrop/actions/runs/45160251099) ist ebenfalls erfolgreich.

Native Windows-Prüfung bei **1010 × 630 logischen Pixeln und Qt-Skalierung 100/125/150 %**, mit lokal kombiniertem Player-/SMB-/Download-Stand: echte QML-Mausereignisse → Controller-Worker → echte CLI → isolierte SQLite-Queue. Eine kontrolliert angehaltene künstliche Engine erlaubt die Prüfung während eines aktiven Auftrags. Abbruch ließ ihn aktiv; geregelte Pause veröffentlichte genau eine vollständige TXT und ließ den Folgeauftrag warten; sofortiger Stopp veröffentlichte keine unvollständige TXT und erhielt beide Queueeinträge. Originalhashes, gespeicherte Pause und SQLite-Integrität stimmten. Der Header schaltete nur die gespeicherte Überwachung, ohne Spracheinstellung im Entwurf zu übernehmen oder die Queuepause zu verändern. Keine zusätzlichen KI-/GPU-Modelle geladen. Qt-Skalierung ist keine Änderung der physischen Windows-Anzeigeskalierung.

Der erste neue Header-Test war noch im Vorschauprofil und erlaubte anschließend die vorhandenen Validierungsaufrufe nicht; beides wurde im Testaufbau korrigiert. Der erste native Prüfaufbau hatte bei abgeschalteter Überwachung keine künstlichen Aufträge eingereiht und schloss seine Testverbindungen nicht ausdrücklich. Der korrigierte Aufbau reiht vorab ein und schließt sie; die anschließenden echten Abläufe bestanden. Diese Befunde betrafen die neuen Tests, nicht einen weiteren App-Fehler.

Der [bereinigte Prüfnachweis](pruefungen/2026-11-23-windows-ueberwachung-stopp.json) enthält den abschließenden Gesamtlauf, die nativen Prüfungen, das lokale Update und den erfolgreichen Windows-Check. Kein neuer Release und kein öffentliches Build. Der vorhandene lokale Entwicklungsstand behält Audioplayer, SMB-Fix und Modell-Downloadfortschritt; ausschließlich die beiden QML-Dateien werden aktualisiert. Profil und alter Code werden gesichert, bestehende Queuepause/Einstellungen/Modelle/Runtime bleiben erhalten. `local-development.json` dokumentiert die kombinierten Dateihashes, `build-info.json` weiterhin das bisherige Basispaket.

Das lokale Update ist abgeschlossen: nur `Desktop/qml/Main.qml` und `Desktop/qml/PlaybackButton.qml` ersetzt, alle übrigen **99 vorherigen Programmdateien** erhalten. Normale EXE neu gestartet, lebenden registrierten GUI-Eigentümer und erhaltene produktive Pause bestätigt. Die installierten Dateien wurden anschließend mit denselben isolierten nativen CLI-/SQLite-Klickfällen erneut erfolgreich geprüft; kein produktiver Auftrag wurde als Test gestartet oder abgebrochen.

## Mac-Übergabe

Diese Bedienungsänderung ist **UNGEPRÜFT unter macOS** und bleibt bis zur nativen Gegenprüfung im PR. `main` erhält ausschließlich den beauftragten separaten Dokumentationsstatus. Letzter bestätigter Mac bleibt 1.5.0 Build 27.

Auf dem Mac Header-Schalter per Maus/Tastatur, Synchronisation mit Einstellungen/Tray und getrennte Queue-Steuerung prüfen. Danach alle drei Popupoptionen und Escape während echter laufender Transkription, Sprecherphase und Export abnehmen: geregelter Abschluss genau eines Auftrags, sofortiger Stopp mit sicherem Wiederanlauf, Abbruch ohne Wirkung. Mindestfenster, Retina-Skalierung, Maximieren/Vollbild und Cmd-Q erhalten. Bei Zusammenführung Player-, SMB- und Download-PRs bewusst berücksichtigen.

Gezielte Regressionen mit gepinnter Qt-Laufzeit: `python -m unittest discover -s tests -p test_workspace.py` und `test_desktop_window.py`; vollständiger Windows-CI-Weg wie bisher über `scripts/ci-tests.py`. Die nativen Queueprüfungen verwendeten ausschließlich künstliche Aufnahmen/Ergebnistexte und eigene Profile. In diesem Auftrag keine neue ASR-/GPU-, physische Neustart-/Autostart-, Deinstallations- oder Langzeitabnahme behaupten.
