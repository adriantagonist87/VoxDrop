# VoxDrop für Windows 11

VoxDrop überwacht mehrere Ordner und transkribiert neue Audio- und Videodateien lokal. Die Arbeitsübersicht zeigt die Warteschlange und den Verlauf nebeneinander; im kleinen Fenster wechseln die Reiter zwischen den Listen. Der quadratische Play-/Stopp-Knopf und der aktuelle Auftrag bleiben auch in den Einstellungen erreichbar. Windows nutzt CUDA für Qwen3-ASR 1.7B, Whisper Large v3 Turbo und pyannote. Qwen lädt den Forced Aligner nach der Spracherkennung, damit beide Modelle nicht gleichzeitig Grafikspeicher belegen.

## Start

1. Die ZIP vollständig in einen lokalen Ordner entpacken und dort **VoxDrop.exe** öffnen.
2. Beim ersten Start lädt VoxDrop die Python- und CUDA-Laufzeit für das Benutzerkonto. Dafür braucht der PC Internet und freien Speicherplatz. Das Fenster öffnet sich nach der Einrichtung.
3. Unter **Einstellungen → Transkription** die gewünschten Modelle herunterladen und Sprach-/Sprecheroptionen wählen.
4. Für eine einmalige Transkription Dateien/Ordner ins Fenster ziehen oder oben hinzufügen. Für die laufende Überwachung unter **Einstellungen → Ordner & Überwachung** lokale Ordner, Netzlaufwerke oder UNC-Pfade wie **\\Server\Freigabe\Aufnahmen** hinzufügen und **Änderungen speichern** wählen. **Ordnerüberwachung aktiv** wirkt sofort. SMB-URLs wie **smb://Server/Freigabe/Aufnahmen** werden ebenfalls akzeptiert. Windows verwaltet die Anmeldedaten der Freigabe.

Neue Aufträge werden automatisch verarbeitet, sofern die Warteschlange nicht gestoppt ist. **Play** setzt sie fort, **Stopp** hält kontrolliert an und erhält die Aufträge. **Nach diesem Auftrag pausieren** lässt den aktuellen Auftrag fertig werden. **Aktionen → Warteschlange leeren** entfernt wartende Aufträge separat. Auftragsdetails, Reihenfolge, Einzelentfernung, Wildcardsuche und explizite start-/stoppbare TXT-Detailsuche bleiben erreichbar. Der Verlauf enthält 250 Einträge je Seite; alle Seiten sind erreichbar.

**Einstellungen → App & Daten** enthält den vollständigen Datenbankreset mit Bestätigung. Aufnahmen und TXT bleiben erhalten; aktive Überwachung liest danach erneut ein. Fenster-X blendet in den Tray aus, Minimieren geht in die Taskleiste. **VoxDrop beenden** beendet auch Überwachung und Modellprozesse. Es gibt keinen unabhängigen automatisierten Dienst.

Bei abgelegten Ordnern und bei aktiver Option **Unterordner mit einbeziehen** speichert VoxDrop die TXT-Dateien direkt neben den Aufnahmen. Die Originaldateien bleiben an ihrem Platz.

Voraussetzungen sind Windows 11 x64, ein NVIDIA-Treiber für CUDA 12.8 und eine RTX 5060 mit 8 GB VRAM oder eine leistungsfähigere kompatible RTX-Karte. Die Laufzeit verwendet die Microsoft Visual C++ Redistributable für x64. Falls diese auf dem PC fehlt, lässt sie sich separat installieren. [Microsoft Visual C++ Redistributable](https://learn.microsoft.com/cpp/windows/latest-supported-vc-redist)

Modelle samt Download-Cache liegen im Programmordner unter **Modelle**; Python, CUDA-Laufzeit und uv-Cache unter **Laufzeit**. Den gesamten VoxDrop-Ordner in einem beschreibbaren lokalen Verzeichnis ablegen. Bei Updates diese beiden Unterordner erhalten. Entfernen des Programmordners entfernt die dort gespeicherten großen Downloads. Einstellungen und Verlauf bleiben unter **%LOCALAPPDATA%\VoxDrop**. Alte Pakete haben ihre extern gespeicherten Modelle/Laufzeiten dort weiterhin; ein neues Paket entfernt diese Bestände nicht automatisch.

Falls Windows nach einer Netzwerkfreigabe fragt, diese im Systemdialog selbst bestätigen. Bei der Ersteinrichtung wartet VoxDrop mit **Wiederholen/Abbrechen**; nach der Freigabe **Wiederholen** wählen. Details stehen unter **Laufzeit/setup.log**. Bei einem verweigerten Modelldownload (WinError 10013) wartet die Oberfläche und prüft den Download automatisch erneut. **Warten abbrechen** beendet diesen Versuch, ohne vollständige Downloads zu entfernen.

Nach der Einrichtung arbeitet die Transkription lokal. **VoxDrop.exe --diagnose** zeigt an, ob CUDA, der Grafikspeicher und der Hintergrunddienst auf dem Windows-PC erkannt werden.

## Paket bauen

Auf dem Mac das vorhandene aTrain- und DOVER-Lap-Setup aus **scripts/bootstrap.sh** verwenden. **scripts/build-windows.sh** erstellt aus Zig und dem offiziellen Windows-Archiv von uv die portable Windows-ZIP. Der Installer erhält die Versionsstände und Prüfsummen seiner Python-Pakete aus **windows/uv.lock**. Die ZIP enthält die App-Quellen und den Quellstand der eingebundenen aTrain-Version.
