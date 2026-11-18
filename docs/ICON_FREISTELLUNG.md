# Transparente Icon-Vorlage

Die weiße Außenfläche der Nutzervorlage wurde am 18.11.2026 mit dem eingebauten Werkzeug `imagegen` gemäß der gleichnamigen Skill freigestellt. Die weißen Zeichen innerhalb der grünen Kachel bleiben erhalten. Der ausgewählte RGBA-Master liegt unter `macos/VoxDropLogo.png`; ICO und GitHub-Vorschau sind Größen-/Formatableitungen mit erhaltener Transparenz. Die Ecken des PNG sind vollständig transparent. Gegen hellen und dunklen Hintergrund geprüft; keine weiße Hintergrundkachel mehr. Statuswellen im Infobereich und in der Menüleiste sind unabhängig und unverändert.

Verwendeter Prompt des ausgewählten Ergebnisses:

> Use case: background-extraction. Asset: existing VoxDrop application icon, edit target is the supplied PNG. Remove ONLY the off-white/white background OUTSIDE the mint green rounded-square tile. Output a true RGBA PNG with alpha=0 at all corners and in the exterior surrounding the tile, clean antialiased perimeter. Preserve the entire green tile as opaque. Preserve all white shapes INSIDE the tile fully opaque: music note card, film/play card, arrow, subtitle speech bubble and the exact letters CC. Keep the source motif, colors, green texture, proportions, composition and rounded perimeter unchanged; no redesign, no new shapes, no crop, no shadow, no extra white backing, no flattening transparency. The goal is the SAME provided icon with just its external white background removed for Windows ICO, macOS ICNS and GitHub.

Eine weitere erzeugte Variante zur Kantenbereinigung wurde nicht übernommen. Die ausgewählte erste Freistellung und ihre Alpha-Ableitungen werden gemeinsam mit dem funktionalen Windows-Paket geprüft. Eine native Mac-ICNS-/Dock-Prüfung erfolgt auf dem Mac.
