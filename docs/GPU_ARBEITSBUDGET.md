# GPU-Arbeitsbudget unter Windows

Der Regler links unter dem Rechengerät wählt 10–100 %, Standard 100 %. Änderungen werden nach kurzer Entprellung eigenständig gespeichert. Andere noch nicht gespeicherte Einstellungen werden dabei nicht übernommen. Das Budget gilt profilweit, einschließlich bereits eingereihter und laufender Aufträge, ab dem nächsten unterstützten Rechenschritt. Der Auftrag und seine ursprünglichen Erkennungseinstellungen werden dafür nicht neu gestartet.

Das ist ein zeitliches Arbeitsbudget für VoxDrop, kein exakter Grenzwert der systemweiten GPU-Anzeige. Bei 50 % fügt VoxDrop nach abgeschlossenen Modellschritten etwa ebenso viel freie Zeit ein wie zuvor für diese Schritte benötigt wurde. Die Verarbeitung dauert länger. Andere Anwendungen bekommen Rechenzeit, ohne Modellpräzision, Audioabschnitte oder Erkennungsparameter zu verändern. Kurze Lastspitzen bleiben möglich; der Grafikspeicherbedarf wird nicht halbiert.

## Umsetzung

`gpu_budget.py` liest die validierte globale Einstellung `gpu_budget_percent` aus der aktuellen Profilkonfiguration. Der Worker erhält deren Pfad getrennt von den historischen Auftragseinstellungen über `VOXDROP_GPU_BUDGET_CONFIG`; auch der isolierte Qwen-Unterprozess erbt ihn. Änderungen werden spätestens beim folgenden Modellaufruf und während längerer eingefügter Pausen erneut gelesen. Atomare Konfigurationswechsel/ungültige Zwischenstände behalten das letzte gültige Budget.

Qwen-ASR, Forced Aligner und die beiden Torch-Modelle der gepinnten pyannote-Pipeline verwenden ausschließlich temporäre Instanzhooks. Synchronisation wartet auf erledigte CUDA-Arbeit, bevor die GPU durch Schlafpausen freigegeben wird. Innere Hooks unterteilen lange Vorwärtsdurchläufe; alle Hooks werden auch bei Fehlern entfernt. Es werden keine globalen Torch-Hooks oder Treibereinstellungen verändert.

Whisper delegiert die unveränderten CTranslate2-Aufrufe `encode`, `generate`, `align` und `detect_language` und pausiert an deren Grenzen. Ein einzelner nativer Aufruf kann deshalb weiterhin eine Lastspitze verursachen. Bei 100 % entfallen zusätzliche Synchronisations-/Schlafpausen. CPU-Aufträge erhalten keine GPU-Hooks. Keine neue Abhängigkeit, kein zusätzliches Modell, keine Schemaänderung. Alle drei Paketbuilder enthalten das neue Engine-Modul.

Die vorhandenen Prozessbaum-/Abbruch-/App-Ende-Regeln bleiben zuständig. Eine GPU-Pause hält keine unabhängigen Dienste am Leben. Die Konfiguration ist eine globale Ressourcenregel; die Queue-Reihenfolge und gespeicherte Modell-/Sprachparameter bleiben erhalten.

## Prüfstand

Erste Windows-Regression: 173 Fälle in 51,087 s, 166 bestanden und sieben bekannte Plattformskips. Enthalten: reales QML-Tastaturereignis 100 → 50 mit Speicherung ohne fremde Entwurfsänderung, CPU-Sperre, alte Queueeinträge mit aktueller Budgetkonfiguration, verschachtelte echte Torch-Module mit unveränderten Ergebnissen/Hookbereinigung, native Whisper-Delegation, Livewechsel und ungültige Konfiguration.

Tatsächliche GPU-Messungen und Paket-/Modelltests folgen vor der Veröffentlichung; dieser Zwischenstand behauptet noch keine native Lastmessung. Der vollständige tatsächlich geprüfte Commit und Messwerte werden nachgetragen.

## Mac-Übergabe

Der Regler ist derzeit nur für NVIDIA-CUDA unter Windows aktiv. macOS/CPU werden nicht mit einem wirkungslosen Prozentversprechen dargestellt. Die gemeinsame Konfiguration bleibt lesbar, und `gpu_budget.py` wird auch im Mac-Bundle benötigt. Für Metal ist vor Aktivierung ein eigener MLX-/CTranslate2-Metal-/Torch-MPS-Pfad mit echter Synchronisation und nativer Last-/Bedienprüfung erforderlich. Die bisherige Mac-DMG bleibt unverändert.

NVIDIAs MPS-Ressourcenpartitionierung steht nicht unter Windows zur Verfügung: [offizielle Einschränkungen](https://docs.nvidia.com/deploy/mps/latest/when-to-use-mps.html). Die Synchronisationsgrenze folgt [Torch CUDA](https://docs.pytorch.org/docs/stable/notes/cuda.html). Der Regler verändert weder Powerlimit noch Takt oder Ressourcen anderer Anwendungen.
