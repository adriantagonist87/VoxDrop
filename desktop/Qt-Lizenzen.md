# Qt und Qt for Python

VoxDrop verwendet die dynamisch geladenen Bibliotheken Qt, PySide6 Essentials und Shiboken6 in Version 6.10.2 unter der LGPL-3.0. Die Lizenztexte liegen in diesem Ordner. [LGPL-3.0](LGPL-3.0-only.txt) · [GPL-3.0](GPL-3.0-only.txt)

Der zugehörige Quellcode einschließlich der Drittanbieter-Lizenzhinweise ist als eigenes Archiv bei VoxDrop verfügbar. [Qt- und PySide-Quellcode für VoxDrop 1.1.0](https://github.com/adriantagonist87/VoxDrop/releases/download/v1.1.0/VoxDrop-1.1.0-Qt-6.10.2-Quellcode.tar)

Die dynamischen Bibliotheken lassen sich durch ABI-kompatible Builds ersetzen. Unter macOS liegen sie in `VoxDrop.app/Contents/Resources/Python/lib/python3.12/site-packages`. Nach dem Austausch in einer beschreibbaren Kopie lässt sich das geänderte Bundle mit `codesign --force --deep --sign - VoxDrop.app` lokal neu signieren. Unter Windows installiert der Launcher die Bibliotheken aus dem Lockfile in einem versionsabhängigen Runtime-Unterordner unter `%LOCALAPPDATA%\VoxDrop`. Der Launcher-Quellcode und das Lockfile sind im VoxDrop-Repository verfügbar.
