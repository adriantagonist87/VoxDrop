# Windows-Übergabe vom 17. November 2026

Dieser reine Dokumentationsstatus macht die Windows-Arbeit auf `main` sichtbar. Gemeinsame Codeänderungen bleiben im [Draft-PR #1](https://github.com/adriantagonist87/VoxDrop/pull/1) auf [fix/windows-native-validation](https://github.com/adriantagonist87/VoxDrop/tree/fix/windows-native-validation). Der freigegebene Release v1.3.1 und seine Assets wurden nicht überschrieben.

## Exakte Prüfstände

| Gegenstand | Vollständiger Commit |
| --- | --- |
| Finaler getesteter Windows-Code und natives Testpaket | `8b80572b1fc8196f310a89b82b526fa2112098a3` |
| Ausführlicher Abschlussbericht im PR | `5ea307aaed0cbe7d75c15babc88ef7dfbe730123` |
| Native QML-/Modell-/Datei-/UNC-Abnahme vor der letzten Textpräzisierung | `436616ce527d4bbae5ad9922a9f175a39882da09` |
| 48,9-minütiger Qwen-/Aligner-Langlauf mit Stilleüberspringen | `284004ea5792cfee4c813cad5cb76df06a40487a` |
| Bisher bestätigter Mac-Code, unverändert bewahrt | `df207f79aa812f70d090e4306443436d51d48952` |

Die vorangehenden überschaubaren Windows-Commits sind `64eb517ad873698eb16726b23901d3d488bb380b` (Tests/Diagnose) und `0ea3316220443f8c80ee073066d12fc4df86348f` (portable Ablage/nativer Build). Details zu allen Änderungen, fehlgeschlagenen Prüfungen und Grenzen: [Projektstatus im PR](https://github.com/adriantagonist87/VoxDrop/blob/fix/windows-native-validation/docs/PROJEKTSTATUS.md), [Entwicklung im PR](https://github.com/adriantagonist87/VoxDrop/blob/fix/windows-native-validation/docs/ENTWICKLUNG.md), [Mac-Gegenprüfungen im PR](https://github.com/adriantagonist87/VoxDrop/blob/fix/windows-native-validation/docs/UEBERGABE_WINDOWS.md).

## Bestätigte Ergebnisse

- Windows 11 Pro 25H2, Build 26200.9457; NVIDIA RTX 5060, 8151 MiB, Treiber 596.36. Originalrelease zuerst über EXE reproduziert, später natives Windows-Paket gebaut und über EXE geöffnet. Finale Oberfläche meldet installierte Modelle, kein wartender Download.
- Neue Pakete speichern Modelle/Hugging-Face-Cache unter `VoxDrop/Modelle`; Python/CUDA und uv-Cache unter `VoxDrop/Laufzeit`. Einstellungen/Verlauf bleiben im Benutzerprofil. Ältere externe Bestände wurden erhalten, nicht als bereinigt behauptet.
- WinError 10013 am neuen Python-Pfad tatsächlich reproduziert. Nutzer erteilte gezielte Freigaben selbst; danach vollständige Modell-Downloads. Setup-Protokoll, Wiederholen/Abbrechen und Modell-Warte-/Abbruchlogik ergänzt. Die Meldung behauptet keine offene Firewall-Anfrage ohne sichtbare Anfrage. Ein künstlicher Fehlerdialog wurde nach Nutzerhinweis beendet; er war keine reale weitere Systemanfrage.
- Windows-QML-Vollbild verlor beim Minimieren über einen kurzzeitigen `Windowed`-Zustand den gespeicherten Modus. Neue vollständige QML-Regression schlägt am alten Code fehl und besteht nach der Korrektur. Native Fenster-/Layoutprüfungen mit 100/125/150 % Qt-Skalierung, Mindestgröße, langen Namen, Details und Spalten bestanden.
- Finale Suite: 76 Tests bestanden, sieben explizite Skips; letzter Offscreen-Lauf 13,143 s. Native Suite zuvor 14,108 s. Echte Qwen-/Aligner-, Whisper-, pyannote- und dreifache DOVER-Lap-CUDA-Läufe bestanden. Auf dem finalen Funktionsstand: Qwen 35,547 s und Whisper 19,672 s für 51,347 s synthetisches Audio mit Sprecherfusion.
- Fünf echte lokale GPU-Aufträge prüften rekursive Ordnerablage, Original-/Ergebnisschutz, Duplikate, Neutranskription, Archivpaar und Export-Retry. Echter UNC-Auftrag mit künstlicher Aufnahme, TXT neben Original und erneute Prüfung nach Anlage eines fehlenden SMB-Unterordners bestanden. Isolierter SMB-Testordner anschließend entfernt.
- Freigegebene persönliche Besprechung ausschließlich als lokale Testkopie: 2935,339 s Audio in 320,172 s mit Qwen/Aligner und Stilleüberspringen; 3,10 GiB Spitzen-RSS, GPU bis 99 %, GPU-Gesamtbelegung 6878 MiB. Originalhash unverändert. Keine persönlichen Dateien, Inhalte, Pfade, Zugangsdaten oder Logs veröffentlicht. Nach Modellende keine Inferenzprozesse; GPU-Belegung zurück auf Desktop-Niveau. GPU-Messwerte umfassen andere Desktop-Anwendungen.

Test-ZIP zum finalen Code: SHA-256 `3bd19325cdfe30a1a55a3b5b9a2c3e56ce4ed6dbc6a69ad3bb5a67db21ee1ed2`. Es handelt sich um einen unveröffentlichten Windows-Testbuild auf Basis v1.3.1.

## Offen und nächste Schritte

**UNGEPRÜFT unter macOS:** Alle gemeinsamen Änderungen dieses PRs. Auf dem Mac zuerst `git fetch origin`, PR prüfen, vollständige Suite nativ auf Cocoa ausführen; bewusste Normalgröße, Maximierung, Vollbild, Minimierung, Dock/Menüleiste/Einzelinstanz sowie unveränderte Modellablage und isolierte Profile gegenprüfen. Netzwerk-Warteanzeige/Abbruch prüfen. Erst danach gemeinsame Integration/Release entscheiden.

**Offener Qualitätsbefund WIN-05:** Im gemischtsprachigen synthetischen Qwen-Test mit Stilleüberspringen fehlt englischer Text, obwohl die VAD-Intervalle ihn enthalten. Roh-ASR-/Aligner-Ergebnisse mit und ohne Kompaktierung vergleichen. Ein erfolgreicher Langlauf ersetzt keine vollständige Inhaltsprüfung; Whisper ordnete in diesem kurzen Mischsprachenbeispiel trotz Fusion nur ein Textlabel zu.

**UNGEPRÜFT unter Windows:** tatsächlicher Neustart/Anmeldestart, physischer Explorer-Drop, physische Taskleisten-/Infobereichsklicks, systemweiter DPI-Wechsel, tatsächlicher SMB-Serverausfall, native erfolgreiche Wiederholen-Bedienung nach künstlicher Installationsverweigerung, mehrstündige Serien sowie gesicherte Migration/Bereinigung früherer externer Datenbestände. Die sieben Suite-Skips betreffen fünf Mac-Migrationstests und zwei fehlende Windows-Symlinkrechte.
