# Manuelle Datei- und Ordner-Drops unabhängig von der Überwachung

## Sollverhalten

Einzelne Dateien und ganze Ordner dürfen per Drag-and-drop oder Dateiauswahl von überall eingereiht werden, einschließlich nicht überwachter SMB-Laufwerke. Ordner werden einmalig mit Unterordnern erfasst. Die TXT gehört neben das jeweilige Original; Medien und Verzeichnisstruktur bleiben erhalten. Globale und pfadspezifische Archiv-/Überwachungsoptionen ändern diese manuelle Ausgabe nicht. Modell-, Sprach- und Sprecheroptionen bleiben die gewählte Transkriptionskonfiguration. Eine pausierte Queue bleibt pausiert; „Sofort transkribieren“ bearbeitet nur die ausdrücklich ausgewählte Auswahl.

## Befund und Korrektur vom 23.11.2026

Der Nutzer meldete „Ordner liegt außerhalb des überwachten Pfads“ beim manuellen Drop von einem SMB-Laufwerk. Unter Windows vor der Inferenz mit einer künstlichen Aufnahme reproduziert: Der Job speicherte einen Laufwerksbuchstaben, `resolve_folder` lieferte für denselben Stamm dessen UNC-Schreibweise. `verify_source_directory` verglich diese Schreibweisen lexikalisch. Es war keine tatsächliche Beschränkung des manuellen Drops auf die konfigurierten überwachten Ordner.

Die Stammprüfung akzeptiert jetzt auch die ursprüngliche Schreibweise, sofern genau dieser Stamm strikt zum bereits aufgelösten Quellstamm führt. Die Auftragspfade bleiben unverändert. Unterordner werden weiterhin einzeln auf versteckte Komponenten, Reparse Points/Symlinks und Gerätewechsel geprüft. Der gesamte Unterordner wird ausdrücklich nicht per `resolve()` aufgelöst, weil das einen während der Verarbeitung ausgetauschten Unterordnerlink verdecken könnte. Tatsächlich andere oder außerhalb liegende Quellen bleiben abgewiesen. Für eine Neutranskription mit benachbarter TXT wird dieselbe überprüfte Pfadschreibweise beibehalten.

Die Drop-Erstellung setzte bereits `folder_drop`, eigene `watch_path`, Rekursion und Ausgabe neben dem Original; Archivverschiebung, globale SMB-Pflicht und globaler Scope werden dabei nicht übernommen. Neue Tests sichern das ausdrücklich für einzelne Dateien innerhalb und außerhalb überwachter Pfade sowie für das alte Konfigurationsformat ab. Bereits fehlgeschlagene manuelle Jobs mit Laufwerksbuchstaben können nach dem lokalen Fix erneut versucht werden; ihre Originale müssen nicht erneut verschoben oder in die Überwachung aufgenommen werden.

## Prüfstand

Funktionaler Code **`f43e27fdf74dda4b1a492513cc548b9f7a4a54f1`**, [Branch `fix/manual-drop-paths`](https://github.com/adriantagonist87/VoxDrop/tree/fix/manual-drop-paths), [PR #23](https://github.com/adriantagonist87/VoxDrop/pull/23). Python 3.12.13 unter Windows 11; Laufzeit/Modellpins und DB-Schema unverändert. [Bereinigter Prüfnachweis](pruefungen/2026-11-23-windows-drag-drop.json). Keine neue Release-Veröffentlichung.

- Sieben neue gezielte Regressionen in 0,728 s bestanden. Aliasgleichheit, fremder Stamm, Quelle außerhalb des Stamms, unveränderte Reparse-/Geräteprüfung und unabhängige moderne/alte Drop-Konfiguration.
- Vollständige Suite: **243 Fälle in 143,062 s, 231 bestanden/zwölf bekannte Plattform-Skips**. Der aktuelle [GitHub-Windows-Check des funktionalen Commits](https://github.com/adriantagonist87/VoxDrop/actions/runs/45148861471) ist erfolgreich.
- Echtes SMB-Dateisystem: Fehler vor Änderung reproduziert, danach direkte Datei mit Laufwerksbuchstaben, direkte UNC-Datei, verschachtelter Ordner, alter fehlgeschlagener Job/Retry und geschützte Neutranskription bestanden. Originalhash, erste TXT, benachbarte Ausgabe, unveränderte Einstellungen und pausierte übrige Queue geprüft. Diese Dateifälle verwenden einen festen künstlichen Engine-Ausgabetext.
- Zusätzlich echte vollständige Whisper-Large-v3-Turbo-Transkription auf der CPU einer künstlichen 15,09-Sekunden-Sprachaufnahme vom gemappten SMB-Laufwerk: **15,109 s Gesamtzeit**, nichtleere erkannte Sprache, TXT neben Original, Originalhash erhalten. Leere Überwachungsliste, Überwachung aus und globale Archivoption an. Nur vorhandene lokale Modelle im Offline-Modus; keine Modell-Downloads.
- Der erste reine Quell-ASR-Versuch fand die nur im Paket mitgelieferten aTrain-Vendorquellen im Kindprozess nicht. Die Wiederholung verwendete eine isolierte vollständige Engine-Kopie mit identischem neuem `watch_service.py` und bestand. Das war ein fehlender Testaufbau, kein weiterer SMB-Fehler.

Der native Mac-Test des neuen Pfadfalls bleibt **UNGEPRÜFT**. Der gemeinsame Fix bleibt gemäß Übergabeauftrag in PR #23; `main` erhält nur Regel, Dokumentation und Nachweis. Auf dem Mac native Datei-/Ordner-Drops außerhalb der Überwachung, SMB-Volume-Pfade, Retry, geschützte Neutranskription und unveränderte Symlink-/Ausgabegrenzen gegenprüfen. Mac 1.5.0 Build 27 bleibt der bestätigte Plattformstand.

## Lokaler Entwicklungsstand auf Windows

Der Fix ist in der vorhandenen lokalen App eingebaut, ohne einen neuen Release oder einen vollständigen Paketwechsel. Basis bleibt der Windows-Prüfstand 1.5.1 mit Paketcode `6278335acb6589a97b4973c26cf0e931fb5ac369` und dem Audioplayer aus PR #20. Ausschließlich `Engine/watch_service.py` wurde durch den oben genannten Fix ersetzt. Die übrigen 97 Paketdateien einschließlich Player wurden gegen das bisherige Manifest erhalten. `local-development.json` im App-Ordner zeichnet Basis und Datei-/Code-SHA des lokalen Overlays auf; `build-info.json` bezeichnet weiterhin das Basispaket. Der lokale Programmordner ist damit bewusst ein Entwicklungsstand und entspricht für diese eine Datei nicht mehr dem ursprünglichen öffentlichen ZIP-Manifest.

Vor dem Austausch liefen keine Aufträge, die Queue war bereits pausiert. Aktuelles Profil und alte Engine-Datei wurden gesichert; Queue/Reihenfolge, Jobdaten, Konfiguration, Layout, Modelle und Laufzeit blieben erhalten. Der normale EXE-Neustart registrierte einen lebenden App-Eigentümer. Die bestehende Pause blieb bestehen. Die SMB-Dateifälle wurden danach mit der tatsächlich installierten Engine erneut erfolgreich ausgeführt. Persönliche Aufnahmen und Fehlereinträge wurden nicht als Test verändert.

Reproduktion mit der gepinnten Laufzeit: `python -m unittest discover -s tests -p test_manual_drop_paths.py`; vollständige bestehende Suite mit dem vorhandenen CI-Prepare/Install und `python -BEs -Xutf8 scripts/ci-tests.py run`. SMB-Tests nur mit isoliertem Profil und eigenen künstlichen Dateien in einer ausdrücklich freigegebenen Testablage. Eine physische Explorer-Geste sowie ein Server-Verbindungsabbruch wurden in diesem Fix nicht neu abgenommen.
