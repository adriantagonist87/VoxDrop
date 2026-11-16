<img src="docs/images/voxdrop-icon.png" alt="VoxDrop-App-Icon" width="72" height="72">

# VoxDrop

VoxDrop ist eine kostenlose macOS-App auf Basis von aTrain. Sie überwacht lokale Ordner und eingehängte SMB-Freigaben und transkribiert neue Audio- und Videodateien automatisch auf dem Mac. Das Transkript wird als TXT neben der Aufnahme oder zusammen mit ihr in einem Unterordner gespeichert.

Voraussetzung ist ein Mac mit Apple Silicon und macOS 26.2 oder neuer.

Die Windows-Ausgabe richtet sich an Windows 11 x64 mit NVIDIA-RTX-GPU. [VoxDrop für Windows](windows/README.md)

## Modelle und Funktionen

- **Qwen3-ASR 1.7B** ist das Standardmodell. **Whisper Large v3 Turbo** ist als Alternative auswählbar.
- Transkripte mit Zeitstempeln und optionaler Sprecherzuordnung über pyannote. DOVER-Lap kann drei Durchgänge der Sprecherzuordnung zusammenführen.
- Lange Sprechpausen überspringen und Aufträge aus dem Verlauf mit anderen Einstellungen erneut transkribieren.
- Start bei der Anmeldung, Menüleistenstatus und Hinweise bei unerreichbaren oder schreibgeschützten Ordnern.

## Benchmark auf einem Mac mini M5 Pro

Je ein Lauf pro Modell und Aufnahme auf der Apple-GPU eines Mac mini mit M5 Pro und 64 GB gemeinsamem Speicher. Die Gesamtzeit umfasst Dekodierung, Modellladen, Transkription, Zeitabgleich und die gemeinsame Sprecheranalyse mit pyannote. Der RAM-Wert ist die physische Spitzenbelegung des jeweiligen Spracherkennungsprozesses.

| Aufnahme | Audiodauer (Std:Min:Sek) | Qwen gesamt (Min:Sek) | Qwen RAM | Whisper gesamt (Min:Sek) | Whisper RAM |
| --- | ---: | ---: | ---: | ---: | ---: |
| Telefon | 0:48:19 | 3:48 | 5,28 GiB | 4:22 | 7,34 GiB |
| Raum | 1:58:02 | 9:35 | 5,09 GiB | 12:58 | 25,06 GiB |
| Video | 2:48:03 | 12:17 | 5,13 GiB | 17:26 | 30,10 GiB |

## Lizenzhinweise

Die eingebundene aTrain-Version steht unter AGPL-3.0-or-later. Bei der Weitergabe der DMG ist der zugehörige Quellcode gemäß § 6 der AGPL bereitzustellen. [aTrain-Quellstand](https://github.com/aTrainTranscription/aTrain/tree/ea8a7057857220b4299c0ba0b2aaf6def2f35b87) · [Lizenztext](https://spdx.org/licenses/AGPL-3.0-or-later.html)

Qwen3-ASR und der Forced Aligner stehen unter Apache-2.0, Whisper unter MIT und das Sprechermodell unter CC BY 4.0. [Qwen3-ASR](https://huggingface.co/Qwen/Qwen3-ASR-1.7B) · [Forced Aligner](https://huggingface.co/Qwen/Qwen3-ForcedAligner-0.6B) · [Whisper](https://huggingface.co/aTrain-core/faster-whisper-large-v3-turbo) · [Sprechermodell](https://huggingface.co/aTrain-core/speaker-detection)
