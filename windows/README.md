# VoxDrop für Windows 11

VoxDrop überwacht mehrere Ordner und transkribiert neue Audio- und Videodateien lokal. Die Oberfläche bietet Einstellungen, aktuellen Auftrag und Verlauf. Windows nutzt CUDA für Qwen3-ASR 1.7B, Whisper Large v3 Turbo und pyannote. Qwen lädt den Forced Aligner nach der Spracherkennung, damit beide Modelle nicht gleichzeitig Grafikspeicher belegen.

## Start

1. Die ZIP vollständig in einen lokalen Ordner entpacken und dort **VoxDrop.exe** öffnen.
2. Beim ersten Start lädt VoxDrop die Python- und CUDA-Laufzeit für das Benutzerkonto. Dafür braucht der PC Internet und freien Speicherplatz. Das Fenster öffnet sich nach der Einrichtung.
3. Unter **Modell** die gewünschten Modelle herunterladen.
4. Für eine einmalige Transkription Ordner ins Fenster ziehen. Für die laufende Überwachung lokale Ordner, Netzlaufwerke oder UNC-Pfade wie **\\Server\Freigabe\Aufnahmen** hinzufügen und **Ordnerüberwachung aktiv** sowie **Dienst starten** wählen. SMB-URLs wie **smb://Server/Freigabe/Aufnahmen** werden ebenfalls akzeptiert. Windows verwaltet die Anmeldedaten der Freigabe.

Bei abgelegten Ordnern und bei aktiver Option **Unterordner mit einbeziehen** speichert VoxDrop die TXT-Dateien direkt neben den Aufnahmen. Die Originaldateien bleiben an ihrem Platz.

Voraussetzungen sind Windows 11 x64, ein NVIDIA-Treiber für CUDA 12.8 und eine RTX 5060 mit 8 GB VRAM oder eine leistungsfähigere kompatible RTX-Karte. Die Laufzeit verwendet die Microsoft Visual C++ Redistributable für x64. Falls diese auf dem PC fehlt, lässt sie sich separat installieren. [Microsoft Visual C++ Redistributable](https://learn.microsoft.com/cpp/windows/latest-supported-vc-redist)

Modelle, Einstellungen und Verlauf liegen unter **%LOCALAPPDATA%\VoxDrop**. Nach der Einrichtung arbeitet die Transkription lokal. **VoxDrop.exe --diagnose** zeigt an, ob CUDA, der Grafikspeicher und der Hintergrunddienst auf dem Windows-PC erkannt werden.

## Paket bauen

Auf dem Mac das vorhandene aTrain- und DOVER-Lap-Setup aus **scripts/bootstrap.sh** verwenden. **scripts/build-windows.sh** erstellt aus Zig und dem offiziellen Windows-Archiv von uv die portable Windows-ZIP. Der Installer erhält die Versionsstände und Prüfsummen seiner Python-Pakete aus **windows/uv.lock**. Die ZIP enthält die App-Quellen und den Quellstand der eingebundenen aTrain-Version.
