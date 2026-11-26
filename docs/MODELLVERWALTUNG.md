# Installierte Modelle verwalten

## Löschknopf bei Leerlauf, 26.11.2026

Windows 1.6.0 deaktivierte **Löschen …** auch bei leerer, freigegebener Warteschlange, solange der Hintergrunddienst lief. In Code `5aed5c184cefeb27b0cde2f375c65a39623be99a` öffnet **Löschen …** bei Leerlauf ohne vorheriges Pausieren den bisherigen Bestätigungsdialog. Bei einem aktiven oder anstehenden Sofortauftrag bleibt die Aktion gesperrt. Das Backend reserviert den SQLite-Schreibzugriff und prüft die exklusive Modellsperre vor dem Entfernen.

Windows-Test mit synthetischer Whisper-Datei bei laufend gemeldetem Dienst und leerer, freigegebener Warteschlange. Beide Klickpfade, Abbrechen und bestätigtes Löschen, bestanden nativ bei 125 %. Der Qt-Regressionsfall prüft zusätzlich die weiterhin gesperrte Aktion während eines Sofortauftrags. Die produktiven Modellordner waren nicht Teil des Tests. Mac-Gegenprüfung offen. [PR #38](https://github.com/adriantagonist87/VoxDrop/pull/38)

In **Einstellungen → Modelle**, dem vierten Reiter, zeigt VoxDrop Qwen3-ASR, Qwen3 Forced Aligner, Whisper Large v3 Turbo und die pyannote-Sprechererkennung. Die Liste zeigt den Zustand und die Größe der lokalen Dateien. „Unvollständig“ weist auf fehlende oder leere Dateien im gepinnten Manifest hin. Beim Download prüft VoxDrop weiterhin Prüfsummen.

**Löschen …** öffnet eine Bestätigung für den einzelnen Eintrag. Der App-Modellordner und der zugehörige Hugging-Face-Repo-Cache werden dauerhaft gelöscht. Der gemeinsam genutzte Xet-Cache lässt sich keinem einzelnen Modell zuordnen. VoxDrop lässt ihn bei dieser Aktion stehen. Zum erneuten Download führt der Reiter zu den bestehenden Download-Optionen unter **Transkription**. Qwen benötigt Sprachmodell und Forced Aligner. Eine gespeicherte Modellauswahl und die Einstellungen bereits eingereihter Aufträge ändern sich durch das Löschen nicht.

Die Aktion ist bei aktiver Verarbeitung gesperrt. Das Backend prüft den Jobstatus unter einer SQLite-Schreibreservierung und kann erst löschen, wenn keine Modellzugriffe von Inferenz, Download oder Import/Export laufen. Der Sperrpunkt liegt neben dem Modellspeicher, damit er beim Import eines Modellordners erhalten bleibt. Unter Windows verwendet VoxDrop gemeinsame und exklusive Dateisperren mit LockFileEx, unter macOS flock. [Microsoft-Dokumentation zu LockFileEx](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-lockfileex)

Die Engine leitet alle Ziele aus den bestehenden Modellmanifesten ab und öffnet keine frei angegebenen Löschpfade. Vor der Ausführung prüft sie den im Dialog ausgewählten Modellbestand erneut. Verknüpfte Modellordner und Windows-Junctions werden abgewiesen. Reguläre Links in Hugging-Face-Snapshots können als Teil des Cache-Eintrags entfernt werden. VoxDrop folgt ihnen dabei nicht. Bei einem Löschfehler zeigt die App die Fehlermeldung und liest den verbliebenen Bestand erneut ein.

## Geprüfter Stand

Funktionscommit `5c2ebc7664b01b1be8674aa38ec2f92c34ca3daa`. Die macOS-, Windows- und Windows-Crossbuild-Skripte übernehmen das neue Engine-Modul. Es gibt keine neue Bibliothek und keine Datenbankmigration. [Entwicklungsbranch](https://github.com/adriantagonist87/VoxDrop/tree/feat/model-management) · [PR #34](https://github.com/adriantagonist87/VoxDrop/pull/34)

- **Windows 11:** 308 Tests des kombinierten lokalen Entwicklungsstands. 294 bestanden, 14 übersprungen. Der native Bestätigungsdialog wurde mit synthetischen Modelldateien bei Mindestgröße und 100, 125 sowie 150 Prozent Skalierung per Qt-Klick geprüft. Abbrechen, Löschen und die bestehenden Einstellungsreiter wurden dabei abgeglichen.
- **Lokale Installation:** fünf Programmdateien aktualisiert und alle 103 Programmdateien abgeglichen. Die Bestandsabfrage erkennt die vier vorhandenen Modelle. Alle 54 vorhandenen Modell- und Cachedateien blieben erhalten. Die installierten QML- und Engine-Dateien bestanden einen weiteren isolierten Klicktest. Ein separater Versuch mit einer Windows-Junction bestätigte, dass das externe Ziel erhalten bleibt. Die produktive App blieb für die Prüfung geschlossen. Warteschlange und CPU-Schutz sind weiter gesetzt.
- **macOS:** native Prüfung offen. Im App-Paket den Reiter im Mindestfenster öffnen und mit einem isolierten Modellspeicher die vier Einträge, Abbrechen, Löschen, den Qwen-Download und die Sperren bei laufender Nutzung prüfen. Einen normalen Hugging-Face-Snapshot mit verlinkten Blobs einbeziehen. Der gemeinsame Funktionscode liegt bis zur Mac-Gegenprüfung im PR.
