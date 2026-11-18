# Mac auf den aktuellen Windows-Funktionsstand bringen

## Auftrag und Ausgangspunkt

Der Nutzer beauftragt am 18. November 2026 den Abschluss der Windows-Veröffentlichung und die Weiterentwicklung auf dem Mac auf denselben Funktionsstand. `main` ist dafür die gemeinsame Entwicklungsbasis. Diese Integration ist ausdrücklich keine native Mac-Freigabe: Die bisherige Mac-DMG v1.3.1 bleibt erhalten, bis der neue Stand auf einem echten Apple-Silicon-Mac geprüft und neu gebaut wurde. Frühere Hinweise „gemeinsamer Code bleibt im Windows-Draft“ beschreiben den vorherigen Übergabezustand.

| Referenz | Exakter Stand |
| --- | --- |
| Windows-Programm, identisch mit der abgenommenen PC-Installation | `48ff35f43f07c07b4b7abd0b22561c9096fbe1cc` |
| Finaler Windows-Download | [v1.4.0](https://github.com/adriantagonist87/VoxDrop/releases/tag/v1.4.0), SHA-256 `f91c03dbbd093fa983b8a55688e682ae47571a5772f2600495833884dfd00565` |
| Letzte vollständige native CUDA-/Beenden-/Wiederaufnahmeabnahme | `48ff35f43f07c07b4b7abd0b22561c9096fbe1cc`; Play/Stopp/Wiederaufnahme, beide ASR-Modelle und drei DOVER-Durchgänge bei 75 % Budget geprüft |
| Letzter belegter nativer Mac-Code | `df207f79aa812f70d090e4306443436d51d48952`, v1.3.1 / Build 23 |
| Aktuelle plattformübergreifende Quellen | `main`; vollständigen SHA beim Beginn mit `git rev-parse HEAD` erfassen |
| Paket-/Dateinachweis | [Manifest mit allen Programmdateien](../releases/v1.4.0/windows-release.json) und [Prüfwerkzeug](../scripts/verify_windows_release.py) |

## Ergänzung: neue gemeinsame Arbeitsübersicht

Der neue Windows-Stand 1.4.0 enthält bereits die freigegebene gemeinsame Qt-Oberfläche. **Nicht den alten Drei-Spalten-Aufbau erneut portieren.** `desktop/rows_model.py` wird zusätzlich benötigt; beide Builder übernehmen den gesamten Desktop-Ordner. `Main.qml`, `QueuePane.qml`, `PlaybackButton.qml` und der Controller gehören zusammen mit dem neuen Engine-Statusfeld `global_history_counts` und `status --offset` in dasselbe Paket. [Vollständige Funktionsmatrix und Testbefehle](WORKSPACE_LAYOUT.md).

Unter macOS zunächst die 203 gemeinsamen Regressionen und `scripts/check-workspace-ui.py --native --output <privat>` ausführen. Danach die echten nativen Adapter prüfen: Dock-/Menüleistenicon und Reaktivierung, X/Minimieren/Quit, Finder-Reveal und TXT-Standardapp, Login-Item, Datei-/Ordnerdialog, Metal/CPU, Qwen/Whisper/Sprecher/DOVER, SMB, Drop-/Dateiversionsschutz, Suche und Reset. Der CUDA-Budgetregler bleibt auf Metal deaktiviert; das ist ein dokumentierter Plattformunterschied. Qt-Skalierungsnachweise unter Windows zertifizieren macOS nicht. Bestehende Mac-DMG 1.3.1 bleibt bis dieser Abnahme unverändert. Die exakte Windows-Codeidentität steht im aktuellen Release-Manifest und Projektstatus.

## Im anderen Codex beginnen

Lokale Änderungen erhalten; vorhandenen Checkout verwenden und bei abweichender Arbeit einen eigenen Branch anlegen. Kein altes Mac-Arbeitsverzeichnis über `main` kopieren.

```sh
git status --short --branch
git fetch origin
git switch -c macos/windows-parity-20261118 origin/main
git rev-parse HEAD
```

Zuerst `AGENTS.md`, `docs/PROJEKTSTATUS.md`, `docs/ENTWICKLUNG.md` und diesen Auftrag lesen. Die historische Mac-Installation sowie Profil/Modelle vor einem produktiven Update sichern. Windows-Ordner, Windows-Profile und private Rohlogs werden nicht übernommen. Tests beginnen mit `VOXDROP_PROFILE` und synthetischen Medien in einem separaten lokalen Ordner.

```sh
sh scripts/bootstrap.sh
sh scripts/build-app.sh
lab=$(mktemp -d "${TMPDIR:-/tmp}/voxdrop-mac-parity.XXXXXX")
VOXDROP_PROFILE="$lab" .runtime/package/VoxDrop.app/Contents/MacOS/VoxDrop
```

Das prüft den echten nativen Bundle-Einstieg. Für Modelltests kann `VOXDROP_MODEL_DATA` auf einen vorhandenen passenden Modellspeicher zeigen; dessen Manifest prüfen und keine Gewichte überschreiben. Danach `sh scripts/build-dmg.sh`, die tatsächliche DMG installieren und den normalen Finder-/Dock-/Anmeldestart erneut testen. Erst nach nativer Abnahme Mac-Version und Build erhöhen und eine neue Mac-DMG veröffentlichen. Die Windows-ZIP nicht ersetzen.

## Funktionsparität abnehmen

| Bereich | Erwartung und wesentliche Quellen |
| --- | --- |
| Queue | Alle wartenden Aufträge, kompakt/ausklappbar, Einzeldetails, Pause, aktueller/Einzel-/Gesamtabbruch. Persistente globale Reihenfolge auch bei Suchfilter, Vor-/Nach-Anker, Menüs und Drag-and-drop. `queue_control.py`, `desktop/qml/QueuePane.qml`, `controller.py`. |
| Suche | Lupenfelder; schnelle Dateiname-/Pfad-Wildcards; ausdrücklich start-/stoppbare Inhaltssuche mit lokalem FTS und separatem Suchprozess. Unicode, fehlende TXT, erneuter Lauf und Abbruch. `desktop/transcript_search.py`, `history_store.py`, `SearchToggle.qml`. |
| Verlauf/Bestand | Fünf Kategorien samt globalen Anzahlen, positive Fehlerzahl rot, nie gestartete Queue-Abbrüche aus dem Verarbeitungsverlauf ausgeblendet. Fremd-TXT ohne erfundene Modell-/Laufzeitwerte. |
| Bereinigung | Nach Bestätigung alle Fach-/Queue-/Drop-/Hash-/Suchdaten und Arbeitskopien entfernen; Originale/TXT/Einstellungen/Pause erhalten. Nächstes reguläres Intervall importiert bei aktiver Überwachung neu. Alte Scan-/Such-/Statusantworten dürfen nichts zurückschreiben. |
| Drops | Mehrere Dateien/Ordner robust deduplizieren. Konfliktdialog mit passenden Optionen: priorisieren, geschützte Neutranskription, Sofort-Auswahl oder ignorieren. Eine pausierte Restqueue bleibt pausiert. |
| Dateiidentität | Vorhandene TXT erkennen; identisch umbenannte Medien wiederverwenden; geänderte Versionen getrennt behandeln; offene/unfertige Aufnahmen zurückstellen; Neustart ohne ständiges Wiedereinreihen. `media_history.py`, `watch_service.py`. |
| Dateiaktionen | TXT mit der Mac-Standardanwendung öffnen; tatsächliches TXT im Finder zeigen. Leerzeichen, Komma, Plus, Umlaute und Netzpfade testen. |
| Fenster | Rotes X blendet bei vorhandenem Menüleistenstatus nur aus; native Minimierung geht ins Dock. Menüleiste/Dock/erneuter App-Start öffnen dasselbe Fenster und erhalten normalen/maximierten/Vollbildzustand. Kein Logo-Header im Fenster. |
| Vollständig beenden | „VoxDrop beenden“ und Cmd-Q stoppen Scanner, Worker/Supervisor, Suche, Downloads und Inferenz; keine Modelle in RAM/Metal, keine Folgescans. Ausgeblendetes Fenster bedeutet weiterhin laufende App. Queue/Einstellungen/Modelldateien bleiben gespeichert. |
| Prozesse/Wiederanlauf | Eigene PID plus Erstellungszeit, begrenztes Beenden nur des jeweiligen Profils; GUI-Absturz und blockierte SQLite-/Netz-I/O ohne verwaiste Unix-Nachfahren. `app_lifecycle.py`, `desktop/command_process.py`, `transcription_worker.py`, `platform_io.py`. |
| Modelle | Qwen/Whisper sowie Sprecherzuordnung; ASR vor Sprecherphase entladen. Deutsch und Englisch getrennt, jeweils mit/ohne Stille; DOVER-Lap nicht nur Fallback. Originale, Zeitmarken und TXT-Anker vergleichen. |
| Icon/Paket | Transparentes `macos/VoxDropLogo.png`, aktueller Swift-ICNS-Generator; Dock/Finder/App korrekt, Menüleisten-Statuswelle unverändert. Alle neuen Module im Bundle und alle Lizenztexte enthalten. |

## Native Mac-Schwerpunkte

1. **Cmd-Q und Fenster-X unterscheiden.** QML weist normales Fensterschließen zum Ausblenden zurück. Deshalb ausdrücklich prüfen, dass Cmd-Q den vollständigen Abschluss erreicht und nicht ebenfalls nur versteckt. Gegebenenfalls den nativen Quit-Pfad vor dem Schließevent an `requestQuit()` anbinden. `shutdownComplete` muss den anschließenden echten Abschluss zulassen.
2. **Unix-Prozessbäume prüfen.** Windows-Jobobjekte belegen keine Mac-Bereinigung. Insbesondere GUI-Verlust und Supervisor-Zeitlimit während blockierter I/O dürfen keine separat gestarteten Inferenz-/Suchgruppen hinterlassen. Keine generischen Python-Prozesse beenden; zwei isolierte Profile gegentesten.
3. **Unfertige Aufnahmen.** `platform_io.file_is_being_written()` verwendet derzeit eine Windows-Sharing-Probe und gibt auf anderen Systemen `False` zurück. Auf dem Mac ist deshalb das Verhalten bei einer noch offenen OBS-Datei und einer Schreibpause ohne Größenwachstum ausdrücklich zu prüfen und gegebenenfalls anzupassen. Eine bloße kurze Größenstabilität ist kein gleichwertiger Nachweis einer abgeschlossenen Aufnahme.
4. **Dateisysteme und SQLite.** APFS, gemountetes SMB, Unicode, Dateiumbenennung, Veröffentlichung ohne Überschreiben, Exportwiederaufnahme, FTS5/Fallback, VACUUM und Such-/Speichersperren nativ prüfen. Vorhandene Transkripte immer schützen.
5. **Anmeldung.** Der LaunchAgent startet die App mit `--background`/RunAtLoad, ohne KeepAlive. Nach ausdrücklichem Beenden darf er sie in derselben Sitzung nicht wieder starten. Tatsächliche Ab-/Anmeldung separat nachweisen.

## Build- und Prüfhinweise

`scripts/build-app.sh` enthält die neuen Engine-Module `queue_control.py`, `media_history.py`, `history_store.py`, `app_lifecycle.py`, `runtime_logs.py` sowie die bestehenden Backends. Der gesamte Desktopordner einschließlich `command_process.py`, `transcript_search.py` und der QML-Komponenten muss ins Bundle. Pins, Modellmanifeste, aTrain-Commit und bestehende Metal-/Qwen-/Qt-Trennung erhalten. Die Windows-CI verwendet CPU-Torch für synthetische Tests; deren CPU-Wheel niemals in den Mac-/Produktivbuild übernehmen.

Die GitHub-Prüfung `Windows regression` testet synthetische Dateien, SQLite, Qt und Prozesslebensdauer. Sie ersetzt keine CUDA-, Metal- oder Cocoa-Abnahme. Tests auf dem Mac mit dessen vollständiger gepinnter Laufzeit ausführen; Anzahl, Skips, Befehl, Umgebung und vollständigen Code-SHA dokumentieren. Vorhandene Windows-Regressionschecks müssen grün bleiben.

Für `main` sind Pull Requests mit aktuellem erfolgreichen Windows-Check und gelösten Reviewdiskussionen erforderlich. Force-Pushes und Löschen sind auch für Administratoren gesperrt. Keine zusätzliche Freigabeperson ist im Ein-Personen-Repository vorausgesetzt. Eine rote Prüfung beheben, nicht den Schutz umgehen oder fehlgeschlagene Prüfungen als bestanden deklarieren.

Bei Abschluss: Funktionsmatrix mit tatsächlichen Mac-Ergebnissen aktualisieren, getesteten SHA festhalten, Änderungen über PR integrieren, DMG samt Prüfsumme veröffentlichen und den separaten Mac-Link in README ersetzen. Der technisch offene gemischtsprachige Qwen-/Stille-Fall bleibt außerhalb des ausdrücklich vereinbarten Umfangs getrennter deutscher/englischer Meetings und darf nicht als behoben behauptet werden.

Weitere Belege: [Queue und Dateischutz](WARTESCHLANGE_UND_DATEISCHUTZ.md), [Suche und Drop-Konflikte](SUCHE_UND_DROP_KONFLIKTE.md), [Verlauf und Bereinigung](VERLAUF_BESTAND_BEREINIGUNG.md), [Lebensdauer](APP_BEENDEN_UND_LEBENSDAUER.md), [Tray/Taskleiste](FENSTER_TRAY_UND_TASKLEISTE.md), [Icon](APP_ICON_UND_LAYOUT.md).

## Ergänzung v1.4.0

Sichtbaren grünen Start-/Fortsetzen-Knopf, separate Pause und eindeutigen Verarbeitungsstatus übernehmen. `start-queue` verarbeitet den aktuellen Queuebestand explizit auch ohne Ordnerüberwachung und ohne Konfigurationsänderung. Normale unpausierte Queues starten automatisch, bewusste Pause bleibt über Neustarts erhalten. Seen-Einträge werden bei explizitem Start sofort dem bestehenden sicheren Worker übergeben; offene Aufnahmen und Dateiversionen besonders auf Mac nativ prüfen. [Details und Nachweise](VERARBEITUNG_STARTEN.md).

## Zusätzlich: GPU-Arbeitsbudget

[Windows-Implementierung und native Lastmessungen](GPU_ARBEITSBUDGET.md). `gpu_budget.py` muss im Mac-Bundle liegen. `gpu_budget_percent` ist eine globale Live-Ressourceneinstellung; der Konfigurationspfad wird separat vom Auftrag an beide Worker weitergegeben. Aktuell ist der Regler auf dem Mac bewusst deaktiviert: CUDA-Hooks begrenzen keine MLX-/Metal-Arbeit. Vor Aktivierung MLX-ASR/Aligner, CTranslate2-Metal und Torch-MPS an echten abgeschlossenen Rechenschritten synchronisieren und Pausen einfügen; Livewechsel, Abbruch, Textgleichheit, Modellreihenfolge und sichtbare Lastentlastung nativ gegenprüfen. Die UI darf kein wirkungsloses 50-%-Versprechen machen. Die Windows-Speicherrace-Regression muss unter Cocoa ebenfalls bestehen.

## Zusätzlich: kompakter Play-/Stopp-Knopf

`PlaybackButton.qml` ist rekursiv im Desktop-Bundle enthalten. [44×44-Bedienung und Stopp-Semantik](PLAY_STOPP.md) auf Cocoa prüfen: Größe normal/maximiert/Vollbild unverändert, echte aktuelle Erkennung samt Unix-Prozessgruppe stoppen, Queueposition erhalten, gestoppten Zustand über Neustart bewahren und erst nach abgeschlossenem Stopp wieder starten. Bereits fertige Exporte sicher abschließen; ausdrücklich entfernte Aufträge nicht wiederbeleben. Eine unterbrochene Erkennung beginnt beim Fortsetzen neu. Keine neue Mac-DMG ohne native Gegenprüfung.
