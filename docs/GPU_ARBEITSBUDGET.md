# GPU-Arbeitsbudget unter Windows

## Ergänzung: Metal auf macOS ab 1.4

Seit der Mac-Portierung vom 21.11.2026 ist derselbe Regler auch für die Apple-GPU aktiv. Temporäre MLX-Instanztypen evaluieren Encoder-/Decoderblöcke vor Synchronisation und Pause; CTranslate2-Metal gibt seine synchronen Aufrufe unverändert weiter. Beide pyannote-Torch-Modelle verwenden MPS-Synchronisation und Instanzhooks. CPU bleibt ohne GPU-Pacing. Livekonfiguration, keine Modell-/Präzisionsänderung und kein RAM-/exaktes Systemlastlimit gelten auf beiden Plattformen. Zwölf tatsächliche Metal-Sprachläufe und Bytegleichheit der jeweiligen 100-/50-%-ASR-Ergebnisse geprüft; [genauer Mac-Nachweis und Grenzen](MAC_ABNAHME_2026-11-21.md). Die bisherige Mac-Übergabe unten bleibt als historische Beschreibung erhalten.

Der Regler links unter dem Rechengerät wählt 10–100 %, Standard 100 %. Änderungen werden nach kurzer Entprellung eigenständig gespeichert. Andere noch nicht gespeicherte Einstellungen werden dabei nicht übernommen. Das Budget gilt profilweit, einschließlich bereits eingereihter und laufender Aufträge, ab dem nächsten unterstützten Rechenschritt. Der Auftrag und seine ursprünglichen Erkennungseinstellungen werden dafür nicht neu gestartet.

Das ist ein zeitliches Arbeitsbudget für VoxDrop, kein exakter Grenzwert der systemweiten GPU-Anzeige. Bei 50 % fügt VoxDrop nach abgeschlossenen Modellschritten etwa ebenso viel freie Zeit ein wie zuvor für diese Schritte benötigt wurde. Die Verarbeitung dauert länger. Andere Anwendungen bekommen Rechenzeit, ohne Modellpräzision, Audioabschnitte oder Erkennungsparameter zu verändern. Kurze Lastspitzen bleiben möglich; der Grafikspeicherbedarf wird nicht halbiert.

## Umsetzung

`gpu_budget.py` liest die validierte globale Einstellung `gpu_budget_percent` aus der aktuellen Profilkonfiguration. Der Worker erhält deren Pfad getrennt von den historischen Auftragseinstellungen über `VOXDROP_GPU_BUDGET_CONFIG`; auch der isolierte Qwen-Unterprozess erbt ihn. Änderungen werden spätestens beim folgenden Modellaufruf und während längerer eingefügter Pausen erneut gelesen. Atomare Konfigurationswechsel/ungültige Zwischenstände behalten das letzte gültige Budget.

Qwen-ASR, Forced Aligner und die beiden Torch-Modelle der gepinnten pyannote-Pipeline verwenden ausschließlich temporäre Instanzhooks. Synchronisation wartet auf erledigte CUDA-Arbeit, bevor die GPU durch Schlafpausen freigegeben wird. Innere Hooks unterteilen lange Vorwärtsdurchläufe; alle Hooks werden auch bei Fehlern entfernt. Es werden keine globalen Torch-Hooks oder Treibereinstellungen verändert.

Whisper delegiert die unveränderten CTranslate2-Aufrufe `encode`, `generate`, `align` und `detect_language` und pausiert an deren Grenzen. Ein einzelner nativer Aufruf kann deshalb weiterhin eine Lastspitze verursachen. Bei 100 % entfallen zusätzliche Synchronisations-/Schlafpausen. CPU-Aufträge erhalten keine GPU-Hooks. Keine neue Abhängigkeit, kein zusätzliches Modell, keine Schemaänderung. Alle drei Paketbuilder enthalten das neue Engine-Modul.

Die vorhandenen Prozessbaum-/Abbruch-/App-Ende-Regeln bleiben zuständig. Eine GPU-Pause hält keine unabhängigen Dienste am Leben. Die Konfiguration ist eine globale Ressourcenregel; die Queue-Reihenfolge und gespeicherte Modell-/Sprachparameter bleiben erhalten.

## Geprüfter Stand – Windows v1.3.4

Regler links unter dem Rechengerät: 10–100 % für Windows-CUDA, unabhängig von anderen Entwurfsänderungen sofort gespeichert und auch für laufende/alte Queueaufträge wirksam. Qwen, Aligner, Whisper und beide Sprechermodelle geben gezielt Rechenzeit frei. Kein exaktes systemweites Prozent-/VRAM-Limit; CPU/Mac-Regler deaktiviert. [Umsetzung, Messungen und Mac-Aufgabe](GPU_ARBEITSBUDGET.md).

Geprüfter Paket-Code `c2624c9e7465e273924e21d1ca279bd41f76f4a1`, [Windows v1.3.4](https://github.com/adriantagonist87/VoxDrop/releases/tag/v1.3.4), ZIP-SHA-256 `bea3500c659dfd8e8b703dc96de50cb0490e24e51c6368c30bdd710c8cef83b6`, [92-Dateien-Manifest](../releases/v1.3.4/windows-release.json). Laufzeit/Modellpins unverändert. 174 Fälle in 49,555 s: 167 bestanden, sieben Plattformskips. Nativer QML-Mauszug 100 → 50 einschließlich Mindestfenster und separater Speicherung bestanden; eine echte Status-/Speicherrace davor reproduziert und korrigiert.

RTX-5060-Kontrolllast: 100 % Budget → durchschnittlich 92,44 % GPU; 50 % → 42,29 %, unveränderte Ergebnistensoren. Echter Livewechsel 100 → 50 → 100 am selben CUDA-Modell bestanden. Fünf echte GPU-Sprachläufe mit Qwen/Whisper und jeweils drei DOVER-Prüfungen erfolgreich; deutsche Texte bei 100/50 je Modell bytegleich, separate englische Qwen-Aufnahme bei 50 % vollständig anhand Testankern geprüft. Echter CUDA-Abbruch bei 50 % ohne Modell-/Audioreste bestanden. Keine Behauptung eines exakten systemweiten 50-%-Limits oder einer physischen Desktop-Latenzmessung.

Die aufgeführten GPU-Werte stammen aus jeweils 14 Sekunden kontrollierter dichter CUDA-Rechenlast; die ersten zwei Sekunden jeder Stichprobe sind aus dem Mittel ausgeschlossen. Die 50-%-Variante erreichte 191 statt 405 Vorwärtsdurchläufe pro Sekunde. Natürliche CPU-/Lade-/I/O-Pausen der Transkription werden dadurch nicht beschleunigt. Der tatsächliche Laufzeitfaktor hängt vom Modell und Material ab. Beide deutschen ASR-Ausgaben waren einschließlich Zeitmarken bytegleich; die englische Aufnahme wurde separat geprüft.

Der alte QML-Stand konnte eine Regleränderung durch einen Statusrefresh vor dem verzögerten Speichern verlieren. Die neue Regression reproduzierte 100 statt 50 am alten Paket. Jetzt wird der gewählte Wert sofort im Entwurf und separat im Timer gehalten; eine andere laufende Bedienaktion verzögert das Speichern, verwirft es aber nicht. Native Mausbedienung und gespeicherte Konfiguration bestätigen den Fix. Ein früher privater Testtreiber war zusätzlich während seiner QTest-Wartezeit erneut eingetreten; dieser Treiberfehler ist getrennt korrigiert und nicht als Produktfehler gezählt.

Der Gesamtlauf vor der letzten Teststabilisierung meldete einmal die bereits falsche 30-ms-Annahme für eine Queue-Zeilenhöhe; die fertige kompakte Geometrie wird jetzt begrenzt auf dem Qt-Polish-Frame abgewartet. Keine Änderung am Produktverhalten dieser Queuefunktion.

## Mac-Übergabe

Der Regler ist derzeit nur für NVIDIA-CUDA unter Windows aktiv. macOS/CPU werden nicht mit einem wirkungslosen Prozentversprechen dargestellt. Die gemeinsame Konfiguration bleibt lesbar, und `gpu_budget.py` wird auch im Mac-Bundle benötigt. Für Metal ist vor Aktivierung ein eigener MLX-/CTranslate2-Metal-/Torch-MPS-Pfad mit echter Synchronisation und nativer Last-/Bedienprüfung erforderlich. Die bisherige Mac-DMG bleibt unverändert.

NVIDIAs MPS-Ressourcenpartitionierung steht nicht unter Windows zur Verfügung: [offizielle Einschränkungen](https://docs.nvidia.com/deploy/mps/latest/when-to-use-mps.html). Die Synchronisationsgrenze folgt [Torch CUDA](https://docs.pytorch.org/docs/stable/notes/cuda.html). Der Regler verändert weder Powerlimit noch Takt oder Ressourcen anderer Anwendungen.
