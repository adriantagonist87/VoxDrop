# Systemstillstand nach Transkriptionsstart am 23.11.2026

## Beobachtung und gesicherter Stand

Der Nutzer meldete nach dem Start einer Transkription starke Verlangsamung, unbewegliche Maus und einen vollständigen PC-Stillstand mit notwendigem hartem Ausschalten. Das ist ein **offener Stabilitätsfehler**. Die zuvor grünen Funktionstests der Papierkorblöschung sind keine Dauer- oder CUDA-Stabilitätsabnahme.

Zeitlicher Abgleich auf dem betroffenen Windows-PC (Europe/Berlin):

- Das lokale Papierkorb-Update und seine isolierten nativen Tests waren um 13:03 abgeschlossen.
- Der produktive Auftrag begann um **13:05:05**, Whisper Large v3 Turbo, `hardware=cuda`, 100 % GPU-Arbeitsbudget, CPU-Schutz ausgeschaltet. Das letzte Dienstlog zeigt Whisper-Fortschritt bis ungefähr 25 % der 136 Sekunden erkannten Sprache. Daraus lässt sich der spätere Kernelzustand nicht bestimmen.
- Windows meldet einen **WATCHDOG-Bericht vom 23.11. um 13:07**, `LiveKernelEvent 193`, Berichtskennung `4804795b-e5cf-4cf3-9bf7-a5152f72cf8e`. Meldungen um 13:10 und 13:13 verwenden dieselbe Kennung und denselben Dump: ein Vorfall, keine zwei weiteren Abstürze.
- Neustart um **13:10:01**, Kernel-Power 41 mit `BugcheckCode=0`. Das ist kein nachgewiesener neuer Bluescreen. Die ebenfalls erneut gemeldeten alten 141/117-/193-Berichte und der Bluescreen vom 20.11. werden nicht als Ursache dieses Vorfalls gewertet.

Laut [Microsoft: VIDEO_DXGKRNL_LIVEDUMP 0x193](https://learn.microsoft.com/en-us/windows-hardware/drivers/debugger/bug-check-0x193--video-dxgkrnl-livedump) stammt dieser Live-Dump vom DirectX-Grafikkernel; der Code ist selbst kein Bugcheck. Der zeitliche Zusammenhang stützt die Untersuchung des Grafik-/CUDA-Pfads, beweist aber weder einen bestimmten Treiberdefekt noch VRAM-Mangel oder eine konkrete fehlerhafte Modellphase. Ein Kernelstillstand kann durch einen später reagierenden App-Watchdog nicht zuverlässig verhindert werden.

Der aktuelle Dump und `Report.wer` sind für das normale Benutzerkonto **nicht lesbar (Zugriff verweigert)**. Es wurden keine Zugriffsrechte, Treiber, Registry-TDR-Werte oder Firewallregeln geändert. Ein privates Skript für die vom Nutzer auszuführende Administratorkopie genau dieses Dumps liegt im Diagnoseordner außerhalb des Repositorys bereit. Danach `!analyze -v` mit WinDbg sowie Stack/Modul-/Zeitabgleich ausführen; den Dump und private Medien nicht veröffentlichen.

## Sofortmaßnahmen auf dem betroffenen PC

Nach dem Neustart war VoxDrop per Autostart wieder als Hintergrund-App gestartet. Die genaue GUI-Prozessidentität und die profileigenen Dienste wurden geprüft und gestoppt. Vorher wurden die SQLite-Datenbank über deren Backup-API sowie Konfiguration und Protokolle privat gesichert. Nach dem Stoppen keine GUI, keine Inferenz und keine GPU-Last erneut gestartet.

Der vorhandene **Windows-CPU-Schutz wurde vorübergehend aktiviert** (`windows_cpu_only=true`), alle anderen Konfigurationsfelder erhalten. Die Queue bleibt pausiert; Aufträge/Reihenfolge und Medien erhalten. Diese Sicherung ist eine vorläufige Betriebsmaßnahme und keine Behebung der unbekannten Stillstandsursache. CUDA-Dauer-/Reproduktionstests auf diesem PC bis zur geklärten Diagnose nicht selbsttätig erneut starten. Es wurde kein Release erstellt.

## Gefundene Lücke im Grafikschutz

Der bestehende Schutz erkannte aktuelle 141/117-WER-Berichte, Display 4101 und NVIDIA 153. **193 wurde nicht abgefragt.** Dadurch fehlte dieser konkrete Hinweis im bestehenden Abbruch-/Wiederanlaufschutz.

Funktionscode **`c0aa811345bd87d5680534dd5e30d0eef6e520e7`**, Branch [`fix/windows-watchdog-193`](https://github.com/adriantagonist87/VoxDrop/tree/fix/windows-watchdog-193), [PR #32](https://github.com/adriantagonist87/VoxDrop/pull/32). `platform_io.graphics_timeout_since` fragt zusätzlich 193 ab und meldet ihn als Grafik-Watchdog. Bestehende Prüfung von ursprünglicher Report-ID-Zeit und Dumpdatum bleibt unverändert: alte, später erneut eingereichte Berichte dürfen keine frischen Aufträge stoppen. Bestehende Worker-/Queue-/Recovery-Behandlung kann den neuen Hinweis verwenden; keine neuen Treiberzugriffe oder globale Systemänderung.

**Geprüft:** 41 modellfreie Fälle in 12,774 s, alle bestanden, darunter zwei neue 193-Regressionen sowie bestehende Queue-/Crash-/CPU-Schutz-/Prozesstests. Anschließend nur `Engine/platform_io.py` lokal aktualisiert, die übrigen 101 Programmdateien unverändert gegen ihre bisherigen Hashes geprüft. Die installierte Erkennung liest den vorhandenen Vorfall tatsächlich als 193; eine neue Abfrage ab aktuellem Zeitpunkt liefert keinen Fehlalarm. App bleibt beendet, CPU-Schutz und Pause aktiv. [Bereinigter Nachweis](pruefungen/2026-11-23-windows-watchdog-193.json).

**Nicht geprüft und nicht behauptet:** Behebung oder gefahrlose Reproduktion des vollständigen Systemstillstands, neue CUDA-Dauerfreigabe, aktuelle RAM-/VRAM-Spitze oder native Mac-Abnahme. Die Änderung schließt eine Diagnoselücke; die Ursache bleibt offen. Neue Sprach-/Sprecherfunktionen werden dadurch nicht gleichzeitig geladen: die vorhandene ASR-Freigabe vor Sprecherzuordnung bleibt bestehen, ist aber kein Nachweis für den konkreten Speicherzustand beim Stillstand.

Auf `main` zunächst nur Dokumentationsübergabe; Funktionscode bleibt im Entwicklungs-PR. Native macOS-Freigabe unverändert 1.5.0 Build 27. Vor Zusammenführung die übrigen gemeinsamen Änderungen und Windows-Regressionsprüfung abgleichen.
