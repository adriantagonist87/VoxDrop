# GitHub-Abschluss und Windows-Release v1.3.2

## Auftrag und gemeinsame Basis

Der Nutzer beauftragt den vollständigen GitHub-Abschluss: denselben Windows-Programmstand öffentlich herunterladen können, README/Logo/Funktionen aktualisieren, `main` schützen und die Mac-Weiterarbeit auf derselben Quellbasis ermöglichen. Der gemeinsame Entwicklungsstand wird deshalb über PR #1 nach `main` integriert. Die bisherige Mac-DMG v1.3.1 bleibt separat verfügbar; ein neuer Mac-Funktionsrelease benötigt die native Gegenprüfung aus dem [Mac-Übergabeauftrag](MAC_PORTIERUNG_WINDOWS_2026-11-18.md). Frühere Draft-/Integrationssperren in historischen Berichten beschreiben den vorherigen Stand.

## Identität der herunterladbaren Windows-App

| Gegenstand | Nachweis |
| --- | --- |
| Release | [v1.3.2 – Windows](https://github.com/adriantagonist87/VoxDrop/releases/tag/v1.3.2) |
| ZIP | `VoxDrop-1.3.2-Windows-x64.zip` |
| ZIP-SHA-256 | `be621da30940ab64ff3dfe14ac2d29a9c18b5a05ee6b76edc8deb0cfa8cc9775` |
| Tatsächlich gebauter/geprüfter App-Code | `a5efd22a241368e5e0d8e5b9c933e39cf965b20b` |
| Programmdateien | 91, jede einzeln mit Größe und SHA-256 im [Manifest](../releases/v1.3.2/windows-release.json) |
| Vorheriger identischer Download | Windows Preview 13; die ZIP-Bytes werden unverändert unter dem eindeutigen finalen Windows-Namen veröffentlicht |
| Eingebundene Laufzeit-/Modellpins | Unverändert; `runtime-fc8909c264e4`, aTrain `ea8a7057857220b4299c0ba0b2aaf6def2f35b87` |

Release v1.3.2 bezeichnet die Freigabe dieses Windows-Stands. Die interne Basisversion in `build-info.json`, Info.plist und dem unveränderten Windows-Lockfile lautet noch 1.3.1. Sie wurde bewusst nicht nachträglich in der bestehenden Installation verändert: Ein neuer Lockfile-Hash würde einen anderen Laufzeitpfad erzeugen, und ein Neuverpacken wäre nicht mehr byteidentisch. Der vollständige App-Code-SHA und das Dateimanifest identifizieren den tatsächlichen Funktionsstand. Ein späterer Versionswechsel erfolgt als reguläres gebautes und geprüftes Update.

Der Release-Tag enthält zusätzlich die fertige Dokumentation, CI und Prüfscripte. Der App-Code-SHA im eingefrorenen ZIP bleibt der exakte native Prüfstand. Zwischen diesem Stand und der gemeinsamen Entwicklungsbasis werden keine neuen App-Funktionsänderungen für die Veröffentlichung eingeführt. Nutzerprofile, persönliche Medien/TXT, Modelle und bereits installierte Laufzeitverzeichnisse sind nicht Teil der Distribution. Jeder neue Rechner richtet seine eigenen Ordner ein und lädt die gepinnten Abhängigkeiten.

Nachweis wiederholen:

```powershell
python scripts/verify_windows_release.py --download
python scripts/verify_windows_release.py --zip "C:/Downloads/VoxDrop-1.3.2-Windows-x64.zip" --app-dir "D:/Apps/VoxDrop"
```

Das Werkzeug prüft ZIP-Prüfsumme, sichere Archivpfade, vollständigen Dateisatz und jede einzelne Programmdatei. Bei `--app-dir` vergleicht es dieselben 91 Dateien mit der Installation; zusätzliche lokale Einstellungen/Modelle bleiben unberührt. Manipuliertes Archiv, ausgetauschte Programmdateien und Pfadtraversal werden durch gezielte Regressionen abgedeckt.

Die native Preview-13-Abnahme umfasst X zum Tray bei fortgesetzter Überwachung, Windows-Minimierung, Wiederöffnung und ausdrückliches Beenden ohne Orphans/Folgescans. Die 34 unveränderten Engine-Dateien behalten die native CUDA-/Wiederaufnahmeabnahme auf `53e69cee39ac5a0721f02eb79034db33e792c6a7`. Kein pauschaler Nachweis für alle denkbaren DPI-/Langzeit-/SMB-Ausfälle oder für macOS wird daraus abgeleitet.

## Branchschutz und CI

Die Screenshot-Meldung wurde durch tatsächlichen Branchschutz behoben, nicht durch Ausblenden des Hinweises. `main` ist geschützt, auch für Administratoren. Force-Pushes und Löschen sind gesperrt. Änderungen kommen über Pull Requests; der Check **Windows regression** von GitHub Actions muss erfolgreich und der Branch aktuell sein, Diskussionen müssen gelöst sein. Im Ein-Personen-Repository wird kein unerfüllbarer zusätzlicher Fremdreview verlangt.

Die CI nutzt festgehaltene offizielle Action-Commits, nur Leserechte, `uv 0.13.7` und denselben verwalteten Python-Stand 3.12.13 wie die App. aTrain/DOVER-Quellen stammen aus einem SHA-geprüften Paket. Testabhängigkeiten folgen dem Windows-Lockfile, mit CPU-Torch derselben Basisversion für synthetische Sprecherprüfungen; keine Modellgewichte oder CUDA-Installation auf dem Runner. Produktionsabhängigkeiten werden nicht verändert.

Die erste GitHub-Einrichtung scheiterte vor Testbeginn: `actions/setup-python` bot 3.12.13 für Windows Server 2025 nicht an. Der korrigierte Ablauf installiert Python über `uv`, statt die Version von einer nicht vorhandenen GitHub-Cachekombination abhängig zu machen. Eine zusätzliche frische lokale CI-Probe fand die CPU-Torch-Voraussetzung eines synthetischen Sprechertests; sie ist nun ausdrücklich enthalten. Frische lokale CI: 159 Fälle in 47,992 s, 152 bestanden, sieben bekannte Plattformskips; vier Release-Manipulationsprüfungen enthalten. Die korrigierte [GitHub-Prüfung 44357386673](https://github.com/adriantagonist87/VoxDrop/actions/runs/44357386673) auf `efd209bca441828143273227ddd6ea0c406b3c03` bestand 159 Fälle in 70,690 s: 154 bestanden/fünf reine Mac-Skips; die beiden Symlink-Fälle laufen dort mit. Abschließende GitHub-Läufe und Merge sind über [Actions](https://github.com/adriantagonist87/VoxDrop/actions/workflows/windows-regression.yml) und [PR #1](https://github.com/adriantagonist87/VoxDrop/pull/1) nachvollziehbar.

## README und Lizenzen

README verwendet den transparenten kanonischen PNG-Master, getrennte eindeutige Windows-/Mac-Downloads und eine vollständige Übersicht der heute hinzugefügten Queue-, Such-, Drop-, Verlaufs-, Dateischutz- und Tray-Funktionen. Die bestehende Mac-Ausgabe wird dabei nicht als bereits nachgezogen ausgegeben.

App-Quellen stehen unter dem Release-Tag bereit. aTrain ist mit exaktem Commit und Lizenz im Paket enthalten. Die unveränderte Qt-Version 6.10.2 samt passendem Quellcode bleibt über die [Qt-Quellcodeausgabe](https://github.com/adriantagonist87/VoxDrop/releases/download/v1.3.1/VoxDrop-1.3.1-Qt-6.10.2-Quellcode.tar) erhältlich; [Qt-Lizenzhinweise](../desktop/Qt-Lizenzen.md) und Modelllizenzen bleiben Bestandteil der Distribution.
