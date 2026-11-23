# Qt und Qt for Python

VoxDrop verwendet die dynamisch geladenen Bibliotheken Qt, PySide6 Essentials, PySide6 Addons (Qt Multimedia) und Shiboken6 in Version 6.10.2 unter der LGPL-3.0. Die Lizenztexte liegen in diesem Ordner. [LGPL-3.0](LGPL-3.0-only.txt) · [GPL-3.0](GPL-3.0-only.txt)

Der zugehörige Quellcode einschließlich der Drittanbieter-Lizenzhinweise ist als eigenes Archiv bei VoxDrop verfügbar. [Qt- und PySide-Quellcode für VoxDrop 1.3.1](https://github.com/adriantagonist87/VoxDrop/releases/download/v1.3.1/VoxDrop-1.3.1-Qt-6.10.2-Quellcode.tar)

Zusätzlicher Quellcode für den Audioplayer: [Qt Multimedia 6.10.2](https://download.qt.io/archive/qt/6.10/6.10.2/submodules/qtmultimedia-everywhere-src-6.10.2.tar.xz). Das unveränderte Windows-PySide6-Addons-Wheel enthält dynamische FFmpeg-7.1.2-Bibliotheken. [FFmpeg-Quellcode 7.1.2 samt Lizenz- und Copyright-Hinweisen](https://ffmpeg.org/releases/ffmpeg-7.1.2.tar.xz) · [Qt-Bauanweisungen und Drittanbieter-Hinweise](https://doc.qt.io/qt-6.10/qtmultimedia-attribution-ffmpeg.html). FFmpeg steht unter LGPL-2.1 oder später; die LGPL-3.0 liegt bei. Die jeweiligen Drittanbieter-Lizenzen bleiben erhalten.

Die dynamischen Bibliotheken lassen sich durch ABI-kompatible Builds ersetzen. Unter macOS liegen sie in `VoxDrop.app/Contents/Resources/Python/lib/python3.12/site-packages`. Nach dem Austausch in einer beschreibbaren Kopie lässt sich das geänderte Bundle mit `codesign --force --deep --sign - VoxDrop.app` lokal neu signieren. Unter Windows installiert der Launcher die Bibliotheken aus dem Lockfile in `Laufzeit/runtime-<Lockfile-Hash>/Lib/site-packages` im Programmordner. Der Launcher-Quellcode und das Lockfile sind im VoxDrop-Repository verfügbar.
