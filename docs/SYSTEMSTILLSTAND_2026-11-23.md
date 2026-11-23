# Systemstillstand nach Transkriptionsstart am 23.11.2026

## Beobachtung und gesicherter Stand

Der Nutzer meldete nach dem Start einer Transkription starke Verlangsamung, unbewegliche Maus und einen vollständigen PC-Stillstand mit notwendigem hartem Ausschalten. Das ist ein **offener Stabilitätsfehler**. Die zuvor grünen Funktionstests der Papierkorblöschung sind keine Dauer- oder CUDA-Stabilitätsabnahme.

Zeitlicher Abgleich auf dem betroffenen Windows-PC (Europe/Berlin):

- Das lokale Papierkorb-Update und seine isolierten nativen Tests waren um 13:03 abgeschlossen.
- Der produktive Auftrag begann um **13:05:05**, Whisper Large v3 Turbo, `hardware=cuda`, 100 % GPU-Arbeitsbudget, CPU-Schutz ausgeschaltet. Das letzte Dienstlog zeigt Whisper-Fortschritt bis ungefähr 25 % der 136 Sekunden erkannten Sprache. Daraus lässt sich der spätere Kernelzustand nicht bestimmen.
- Windows erzeugte den Watchdog-Dump um **13:07:53,731** (UTC+1), 2 Minuten und 48 Sekunden nach Auftragsstart. Die WER-Meldungen um 13:10 und 13:13 verweisen auf diesen einen Dump mit `LiveKernelEvent 193` und Berichtskennung `4804795b-e5cf-4cf3-9bf7-a5152f72cf8e`.
- Neustart um **13:10:01**, Kernel-Power 41 mit `BugcheckCode=0`. Das ist kein nachgewiesener neuer Bluescreen. Die ebenfalls erneut gemeldeten alten 141/117-/193-Berichte und der Bluescreen vom 20.11. werden nicht als Ursache dieses Vorfalls gewertet.

Laut [Microsoft: VIDEO_DXGKRNL_LIVEDUMP 0x193](https://learn.microsoft.com/en-us/windows-hardware/drivers/debugger/bug-check-0x193--video-dxgkrnl-livedump) stammt dieser Live-Dump vom DirectX-Grafikkernel; der Code ist selbst kein Bugcheck. Der zeitliche Zusammenhang stützt die Untersuchung des Grafik-/CUDA-Pfads, beweist aber weder einen bestimmten Treiberdefekt noch VRAM-Mangel oder eine konkrete fehlerhafte Modellphase. Ein Kernelstillstand kann durch einen später reagierenden App-Watchdog nicht zuverlässig verhindert werden.

## Auswertung der Dump-Kopie

Der Nutzer kopierte den 280.936 Byte großen Dump mit Administratorrechten in den privaten Arbeitsordner. Mit den lokalen Windows-Modulen und passenden öffentlichen Microsoft-Symbolen lief `!analyze -v` in KD erfolgreich. Der erste Lauf ohne lokale Windows-Module konnte das Kernelsymbol nicht zuordnen. Die Auswertung hier beruht auf dem zweiten Lauf mit aufgelöstem Stack.

- Der Live-Dump hat Code `0x193 VIDEO_DXGKRNL_LIVEDUMP` und Reason Code `0x810`. Die Microsoft-Referenz erläutert diesen konkreten Reason Code nicht. Der Stack zeigt `dxgkrnl!ProcessDeadlockThread+0xe4` im Prozess `System` und die Erfassung des Dumps. WinDbg gruppiert ihn als `LKD_0x193_dxgkrnl!ProcessDeadlockThread`. [Microsoft-Referenz zu 0x193](https://learn.microsoft.com/en-us/windows-hardware/drivers/debugger/bug-check-0x193--video-dxgkrnl-livedump)
- `dxgkrnl.sys` hat Version `10.0.26100.9444`. Der NVIDIA-Kerneltreiber `nvlddmkm.sys` (596.36, Windows-Version `32.0.15.9636`) ist in der Modulliste geladen. Im aufgezeichneten Stack steht kein NVIDIA-Treiberframe. Die Modulliste allein erlaubt keine Zuordnung des Fehlers zum NVIDIA-Treiber.
- Der kleine Dump zeigt den Windows-Thread, der den Bericht erfasst hat. Abfragen mit `!thread`, `!process` und `!locks` konnten die beteiligten Sperren und den blockierten Auftragsthread wegen fehlender Speicherseiten nicht rekonstruieren. Ob Treiber, GPU, VRAM-Druck oder ein bestimmter Aufruf den Stillstand ausgelöst hat, bleibt offen. [Microsoft zur Auswertung kleiner Kernel-Dumps](https://learn.microsoft.com/en-us/windows-hardware/drivers/debugger/small-memory-dump)

Dump und Debuggerprotokolle bleiben lokal. Die Diagnose verwendet die vorhandene Datei und startet keine GPU-Verarbeitung.

## Sofortmaßnahmen auf dem betroffenen PC

Nach dem Neustart war VoxDrop per Autostart wieder als Hintergrund-App gestartet. Die genaue GUI-Prozessidentität und die profileigenen Dienste wurden geprüft und gestoppt. Vorher wurden die SQLite-Datenbank über deren Backup-API sowie Konfiguration und Protokolle privat gesichert. Nach dem Stoppen keine GUI, keine Inferenz und keine GPU-Last erneut gestartet.

Der vorhandene **Windows-CPU-Schutz wurde vorübergehend aktiviert** (`windows_cpu_only=true`), alle anderen Konfigurationsfelder erhalten. Die Queue bleibt pausiert; Aufträge/Reihenfolge und Medien erhalten. Diese Sicherung ist eine vorläufige Betriebsmaßnahme und keine Behebung der unbekannten Stillstandsursache. CUDA-Dauer-/Reproduktionstests auf diesem PC bis zur geklärten Diagnose nicht selbsttätig erneut starten. Es wurde kein Release erstellt.

## Gefundene Lücke im Grafikschutz

Der bestehende Schutz erkannte aktuelle 141/117-WER-Berichte, Display 4101 und NVIDIA 153. **193 wurde nicht abgefragt.** Dadurch fehlte dieser konkrete Hinweis im bestehenden Abbruch-/Wiederanlaufschutz.

Funktionscode **`c0aa811345bd87d5680534dd5e30d0eef6e520e7`**, Branch [`fix/windows-watchdog-193`](https://github.com/adriantagonist87/VoxDrop/tree/fix/windows-watchdog-193), [PR #32](https://github.com/adriantagonist87/VoxDrop/pull/32). `platform_io.graphics_timeout_since` fragt zusätzlich 193 ab und meldet ihn als Grafik-Watchdog. Bestehende Prüfung von ursprünglicher Report-ID-Zeit und Dumpdatum bleibt unverändert: alte, später erneut eingereichte Berichte dürfen keine frischen Aufträge stoppen. Bestehende Worker-/Queue-/Recovery-Behandlung kann den neuen Hinweis verwenden; keine neuen Treiberzugriffe oder globale Systemänderung.

**Geprüft:** 41 modellfreie Fälle in 12,774 s, alle bestanden, darunter zwei neue 193-Regressionen sowie bestehende Queue-/Crash-/CPU-Schutz-/Prozesstests. Anschließend nur `Engine/platform_io.py` lokal aktualisiert, die übrigen 101 Programmdateien unverändert gegen ihre bisherigen Hashes geprüft. Die installierte Erkennung liest den vorhandenen Vorfall tatsächlich als 193; eine neue Abfrage ab aktuellem Zeitpunkt liefert keinen Fehlalarm. App bleibt beendet, CPU-Schutz und Pause aktiv. [Bereinigter Nachweis](pruefungen/2026-11-23-windows-watchdog-193.json).

**Nicht geprüft und nicht behauptet:** Behebung oder gefahrlose Reproduktion des vollständigen Systemstillstands, neue CUDA-Dauerfreigabe, aktuelle RAM-/VRAM-Spitze oder native Mac-Abnahme. Die Änderung schließt eine Diagnoselücke; die Ursache bleibt offen. Neue Sprach-/Sprecherfunktionen werden dadurch nicht gleichzeitig geladen: die vorhandene ASR-Freigabe vor Sprecherzuordnung bleibt bestehen, ist aber kein Nachweis für den konkreten Speicherzustand beim Stillstand.

Auf `main` zunächst nur Dokumentationsübergabe; Funktionscode bleibt im Entwicklungs-PR. Native macOS-Freigabe unverändert 1.5.0 Build 27. Vor Zusammenführung die übrigen gemeinsamen Änderungen und Windows-Regressionsprüfung abgleichen.
