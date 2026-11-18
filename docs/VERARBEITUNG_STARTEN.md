# Verarbeitung starten und Automatik sichtbar machen – v1.3.3

## Aktuell: Windows v1.3.3 – Verarbeitung starten und Status erkennen

Die Produktivdiagnose zeigte eine laufende, nicht pausierte Verarbeitung; der erste lange Auftrag befand sich in der Sprecherphase. Automatischer Start war aktiv. Dennoch fehlte eine klar erkennbare eigenständige Startaktion, und Phasen ohne Prozentangabe wirkten zu leicht wie Stillstand. V1.3.3 ergänzt den sichtbaren grünen Start-/Fortsetzen-Knopf, eine separate Pause und „Verarbeitung läuft“ auch ohne Prozentwert.

App-Code `ca9e3e8ca2ae6b6294eb667c61768bc8dd402506`, [Windows v1.3.3](https://github.com/adriantagonist87/VoxDrop/releases/tag/v1.3.3), ZIP-SHA-256 `8b213066f23c0a18e59bd4567a38a19fb8a053f16486d35d6136a3888dd5add4`. [Manifest mit 91 Dateien](../releases/v1.3.3/windows-release.json). Ein ausdrücklicher Start bearbeitet die bereits eingereihte Queue unabhängig von ausgeschalteter Ordnerüberwachung. Einstellungen, Reihenfolge, bewusste Abbrüche und Originale bleiben geschützt. Gespeicherte Pause wird beim normalen App-Start weiterhin respektiert; neue unpausierte Queues werden automatisch verarbeitet.

163 Regressionen in 55,421 s bestanden, sieben bekannte Plattformskips. Nach der abschließenden Trennung der beiden QML-Buttons zusätzlich alle 24 Qt-Fälle in 8,244 s bestanden. Finales natives Paket in 9.201 s: echter QML-Klick setzt eine normale pausierte Queue bei ausgeschalteter Überwachung fort und veröffentlicht einen vorbereiteten Export; Konfiguration, Originalhash und Eigentümer bleiben erhalten, SQLite/Fremdschlüssel ok, explizites Beenden ohne Orphans. Kein zusätzlicher GPU-Lauf neben dem laufenden Produktivauftrag. [Ursache, Bedienung und Update](VERARBEITUNG_STARTEN.md).


## Befund und Korrektur

Der Nutzer meldete eingereihte Dateien ohne erkennbaren Startknopf und minutenlang vermeintlich ausbleibende Arbeit. Die reine Statusdiagnose ergab `queue_paused=false`, einen aktiven Auftrag, spätere DOVER-Lap-Fortschrittsmeldungen und tatsächlich abgeschlossene Folgeaufträge. Die Diagnose hat keine hängende Gesamtqueue reproduziert. Ein langer erster Auftrag und Phasen ohne Prozentwert wurden aber unzureichend verständlich angezeigt.

Die alte dynamische Schaltfläche hieß entweder „Pausieren“ oder „Fortsetzen“ und bot keinen separat auffindbaren Start. Jetzt steht unter dem Queuetitel ein eigener grüner „Verarbeitung starten“-/„Fortsetzen“-Knopf. Daneben bleibt „Pausieren“ separat; bei pausierter Queue ist dieser Pauseknopf deaktiviert statt eine zweite, anders funktionierende Fortsetzen-Aktion anzubieten. Der Status erklärt laufende Verarbeitung, aktive Pause oder ausgeschalteten Dienst. Bei aktiver unpausierter Arbeit ist Start sichtbar, aber gegen Doppelstart deaktiviert. Phasen ohne messbaren Prozentwert sagen ausdrücklich, dass die Verarbeitung läuft.

`Controller.startProcessing()` startet gegebenenfalls den profileigenen Dienst und führt `start-queue` aus. Die atomare Datenbankaktion nimmt die bestehende Queue aus der Pause und markiert ihren aktuellen Bestand als ausdrücklich zur Bearbeitung ausgewählt. Damit funktionieren normale zuvor überwachte Queueeinträge auch dann, wenn die Ordnerüberwachung inzwischen ausgeschaltet wurde. Es wird keine Überwachung eingeschaltet und keine unsichtbare Entwurfsänderung gespeichert. Neue Ordnerfunde bei ausgeschalteter Überwachung werden dadurch nicht erzeugt.

Explizit gestartete `seen`-Einträge müssen nicht erst auf das nächste Scanintervall warten. Die vorhandenen Workerprüfungen für offene Windows-Schreiber, genaue Dateiversion, bestehende TXT und Veröffentlichung bleiben vorgeschaltet. Ein Windows-Regressionstest hält eine Aufnahme ohne Wachstum geöffnet: kein Engineaufruf, sichtbare Zurückstellung, nach Freigabe erfolgreiche Verarbeitung. Wiederholtes Starten ist idempotent, Reihenfolge und abgebrochene/abgeschlossene Einträge bleiben erhalten. Normale automatische Verarbeitung benötigt weiterhin keinen Klick, sofern die Queue nicht bewusst pausiert wurde.

## Prüfung und laufende Arbeit

Zusätzlich geprüft: echte QML-Klickfolge `start` → `start-queue`, klare Laufanzeige und deaktivierter Doppelstart bei aktivem Auftrag, bestehende Sofort-Auswahl weiterhin gezielt pausierbar. Der native Prüffall verwendet ein gültiges lokal vorbereitetes Ergebnis für einen wartenden Export. Er belegt Steuerung und echte Veröffentlichung, behauptet keinen weiteren GPU-ASR-Lauf. Die ASR-/Sprecherdateien, Modellpins und Laufzeit bleiben unverändert. Private Testberichte enthalten lokale Pfade und werden nicht öffentlich eingebunden.

Für das produktive Update darf der aktive Auftrag nicht abgebrochen oder durch GUI-Neustart wiederholt werden. Nur die nächste Übernahme wird vorübergehend pausiert; nach beendetem Auftrag im Leerlauf Profil/Code vollständig sichern, das geprüfte GitHub-Paket einsetzen, App öffnen und die vorherige Pause-/Überwachungseinstellung wiederherstellen. Auftragshistorie, Ergebnisse und Originale nicht leeren. Die Wiederaufnahme wird über den tatsächlichen produktiven Status kontrolliert.

`main` bleibt durch PR und erfolgreiche Windows-CI geschützt. [Mac-Portierungsauftrag](MAC_PORTIERUNG_WINDOWS_2026-11-18.md) ist um `start-queue` und die neue Anzeige ergänzt. Vor dem Mac-Binaryrelease Start/Fortsetzen mit und ohne Ordnerüberwachung, offene Aufnahmen, explizite Pause und native Fenster-/Quitpfade testen.
