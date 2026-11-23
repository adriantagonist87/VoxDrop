# Verbindliche Arbeitsregeln für Codex

## Vor jeder Aufgabe

1. Lies diese Datei, `docs/PROJEKTSTATUS.md` und `docs/ENTWICKLUNG.md` vollständig. Für Windows-Arbeiten lies zusätzlich `docs/UEBERGABE_WINDOWS.md`. Beachte weitere `AGENTS.md` im betroffenen Verzeichnis und im eingebundenen Upstream-Projekt.
2. Prüfe `git status --short --branch`, den aktuellen Commit, Branch und Remotes. Erhalte vorhandene Änderungen. Verwende für parallele Arbeiten einen eigenen Branch oder Worktree.
3. Rufe bei verfügbarer GitHub-Verbindung `git fetch origin` auf und prüfe den Unterschied zu `origin/main`. `main` ist die gemeinsame geprüfte Basis. Neue Aufgaben beginnen auf diesem Stand. Integriere Änderungen bewusst. Bei fehlender Verbindung dokumentiere den zuletzt bekannten Remote-Stand.
4. Lies die betroffenen Implementierungen und die bestehenden Tests. Trenne implementiertes Verhalten, Nutzermeldungen, Prüfungen auf dem Zielsystem und offene Annahmen im Projektstatus.

## Produkt und Architektur

- VoxDrop besteht aus eigenständigen Apps für macOS und Windows. Jede Installation verarbeitet Medien auf ihrem eigenen Rechner. Windows-Geräte in anderen Netzwerken verwenden ihre eigene lokale KI-Laufzeit und die dort erreichbaren Ordner.
- Der Mac mini ist aktuell macOS-Installation, Entwicklungs- und Build-Rechner. Das bestätigte Betriebsmodell ist in `docs/ENTWICKLUNG.md` beschrieben. Eine zentrale Mac-Server-Anbindung ist ein eigener Architekturauftrag und benötigt einen entsprechenden Nutzerauftrag.
- Halte Oberfläche und Fachlogik gemeinsam. Die Oberfläche liegt in `desktop/qml/Main.qml`, ihre Anbindung in `desktop/controller.py`. Plattformcode gehört in die vorhandenen Launcher, Backends und Betriebssystemadapter.
- `main` ist die gemeinsame Entwicklungsbasis beider Plattformen. Der Mac-Produktivstand ist 1.5.0 Build 27 (21.11.2026), einschließlich nativ geprüfter Profilmigration und symmetrischer Unterordner-Checkboxen; maßgeblich sind `docs/IMPORT_EXPORT.md` und `releases/v1.5.0/macos-verification.json`. Die zugrunde liegende 1.4.1-Funktionsabnahme bleibt in `docs/MAC_ABNAHME_2026-11-21.md` erhalten. Der frühere Auftrag in `docs/MAC_PORTIERUNG_WINDOWS_2026-11-18.md` bleibt als Funktionsmatrix erhalten. Neue gemeinsame Quellintegration allein ist keine native Plattformfreigabe. Änderungen an `main` erfolgen über Pull Requests mit erfolgreichem aktuellem Windows-Check; Branchschutz nicht umgehen.
- Die Lebensdauer der Überwachung gehört zur App. Fenster-X blendet das Fenster in den Systemtray aus; die App und ihre Überwachung laufen weiter. Die Minimieren-Schaltfläche minimiert in die Taskleiste. Ohne verfügbaren Tray minimiert X ebenfalls in die Taskleiste, damit die App erreichbar bleibt. „VoxDrop beenden“ im Tray und natives App-Beenden stoppen sämtliche profileigenen Dienste, Scanner, Such-/Download-/Inferenzprozesse und geben deren RAM/VRAM frei. Erst die vollständig beendete App bedeutet keine Überwachung; Queue, Einstellungen und Modelldateien auf dem Datenträger bleiben erhalten. Autostart startet die App, keinen unabhängigen Dauerbetrieb.
- Qwen3-ASR 1.7B ist das Standardmodell. Whisper Large v3 Turbo bleibt auswählbar. Verwende die vorhandene aTrain-/pyannote-Pipeline sowie die vorhandenen Integrationen für Stille und DOVER-Lap.
- Verwende `uv`, die vorhandenen Lockfiles, Modellmanifeste und den gepinnten aTrain-Commit. Dokumentiere notwendige Änderungen an Versionen, Modellformaten und Laufzeitpfaden.
- Die ursprünglichen Spezifikationen und vorhandenen Lizenzhinweise bleiben erhalten. Im ursprünglichen Übergabepaket standen unter anderem Whisper als MVP-Modell und eine helle Oberfläche. Die später ausdrücklich beauftragten Änderungen zu Qwen, dem dunklen Layout, Windows und dem optionalen Medienverschieben sind im aktuellen Produktstand umgesetzt.

## Verbindliches Dateiverhalten

- Bei Drag-and-drop ganzer Ordner werden Aufnahmen samt Unterordnern einmalig eingereiht. Die TXT-Datei gehört neben die Originalaufnahme. Originaldateien, Ordner und ihre Hierarchie bleiben erhalten. Diese Regel gilt unabhängig von den sonstigen Einstellungen.
- Bei aktiver Option „Unterordner mit einbeziehen“ liegt jedes Transkript neben seiner Aufnahme. Beide Unterordner-Checkboxen bleiben anwählbar; das Einschalten einer Option schaltet die andere aus (Nutzerpräzisierung vom 21.11.2026).
- Bei regulärer Überwachung ohne rekursive Option darf die aktivierte Zielunterordner-Option Aufnahme und Transkript gemeinsam in den gewählten Unterordner verschieben. Erhalte die vorhandenen Prüfungen, exklusiven Veröffentlichungen und Wiederanlaufpfade.
- Bestehende Ergebnisse werden geschützt. Neutranskriptionen aus dem Verlauf erhalten eigene Ausgabedateien. Bewahre SQLite-Historie, Dateiversionsschutz und Wiederholbarkeit bei Fehlern.
- Die Auftragsdatenbank und temporäre Arbeitskopien liegen lokal. SMB ist ein Medien-/Ergebnisordner. Verwende die am jeweiligen Betriebssystem bereits eingerichtete Freigabe und dessen Zugangsdatenverwaltung.
- Die macOS-Distribution enthält den gemeinsamen Programmordner `VoxDrop` mit `VoxDrop.app` und dem später angelegten Modellspeicher `Modelle`. Modellgewichte und Download-Cache gehören in diesen Speicher. Erhalte bei Updates den vorhandenen Modellspeicher und die Benutzereinstellungen.

## Entwicklung und Prüfung auf beiden Systemen

- Prüfe zuerst den normalen Einstiegspunkt der betroffenen Plattform. Ein Importtest oder ein auf macOS gebautes Windows-ZIP belegt jeweils diesen begrenzten Prüfumfang.
- Kennzeichne Windows-Verhalten bis zum tatsächlichen Test auf Windows ausdrücklich als **UNGEPRÜFT unter Windows**. Pflege für jedes System den zuletzt geprüften vollständigen GitHub-Commit, Umgebung, Testbefehl und Ergebnis.
- Führe bestehende relevante Tests aus. Ergänze gezielte Regressionstests, wenn vorhandene Tests den konkreten Fehler oder neuen Datenpfad verfehlen.
- Teste Grafikänderungen mit schmalen Spalten, Mindestfenstergröße, langen Dateinamen, Skalierung und Details. Teste Dock/Taskleiste, Menüleiste/Infobereich sowie erneutes Öffnen am jeweiligen Betriebssystem.
- Verwende isolierte Profile über `VOXDROP_PROFILE`, lokale temporäre Verzeichnisse und synthetische Medien. Für persönliche Medien und produktive SMB-Ordner gelten die vorhandenen Nutzerfreigaben. Sichere bei beauftragten Updates die Konfiguration und den aktiven Auftrag.
- Audio, Transkripte, Zugangsdaten, private Pfade, Laufzeitdaten und vollständige persönliche Logs gehören außerhalb des öffentlichen Repositorys. Modell-Downloads erfolgen im vorgesehenen Setup. Die Transkription verwendet lokale Modelle.
- Behebe Netzwerkfehler anhand konkreter Diagnosen. Änderungen an Firewall, Endpoint-Schutz, Zertifikatsprüfung und Zugriffsrechten erfordern einen passenden Nutzerauftrag.
- Beachte `LICENSE`, die aTrain-Lizenz, `desktop/Qt-Lizenzen.md` und die Modelllizenzen bei Build und Weitergabe.

## Nach relevanten Änderungen und bei Übergabe

1. Aktualisiere `docs/PROJEKTSTATUS.md` nach funktionalen Änderungen, neuen Fehlerbefunden, Plattformprüfungen und Änderungen am Release- oder Integrationsstand.
2. Aktualisiere `docs/ENTWICKLUNG.md` bei Änderungen an Architektur, Einrichtung, Start, Build, Tests, Abhängigkeiten oder Konfiguration. Pflege den Windows-Übergabeauftrag bei neuen Windows-Befunden.
3. Dokumentiere je Fehler Reproduktion, betroffene Plattform und Version, beobachtete Ursache oder Hypothese, Änderung und nachweisbares Testergebnis. Markiere verbleibende Prüfungen.
4. Verwende bei Prüfständen den tatsächlich getesteten Code-Commit. Bei reinen Dokumentationscommits bleibt der letzte funktional geprüfte Code-Commit bestehen. Neue Fixes erhalten den exakten getesteten SHA in einem anschließenden Statusupdate.
5. Übergib den Branch, die Commits, betroffene Plattformen, Tests und offenen Punkte. Nutze vorhandene Nutzerautorisierungen für Push und lokale Installation. Führe geprüfte Änderungen im beauftragten Umfang auf `main` zusammen.

## Öffentliche GitHub-Releases

- Nutzerregel vom 23.11.2026: Der Nutzer bestimmt ausdrücklich, wann ein neuer öffentlicher GitHub-Release für Dritte veröffentlicht wird. Veröffentliche neue Releases oder neue öffentliche Builds erst auf eine konkrete Release-Anweisung.
- Einzelne Bugfixes, Featureaufträge, erfolgreiche Tests und lokale App-Updates sind keine Release-Freigabe. Verwende GitHub für Commits, Branches, Pull Requests und die nachvollziehbare Entwicklung; veröffentliche nicht automatisch mit jedem Fehler ein neues Release.
- Bis zur ausdrücklichen Release-Anweisung bleiben neue Builds lokale Testpakete. Arbeite die beauftragten Fehler weiter ab, ohne dafür jeweils eine Veröffentlichung anzubieten oder einzufordern. Erhalte die vorhandenen stabilen Downloads.

Gemeinsame Änderungen werden über GitHub-Commits und diese Dokumentation abgeglichen. Der nächste Codex-Lauf liest und prüft diesen Stand vor seiner Aufgabe.
