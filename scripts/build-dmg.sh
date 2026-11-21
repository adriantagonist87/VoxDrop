#!/bin/sh
set -eu

project=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
runtime="$project/.runtime"
bundle="$runtime/package/VoxDrop.app"
version=$(/usr/bin/plutil -extract CFBundleShortVersionString raw -o - "$bundle/Contents/Info.plist")
minimum=$(/usr/bin/plutil -extract LSMinimumSystemVersion raw -o - "$bundle/Contents/Info.plist")
reference=$(sed -n 's/^commit=//p' "$project/scripts/bootstrap.sh")
code_commit=$(/usr/bin/git -C "$project" rev-parse HEAD)
/usr/bin/git -C "$project" diff --exit-code HEAD --
output="$runtime/package/VoxDrop-$version-macOS-arm64.dmg"
stage=$(mktemp -d "$runtime/package/.dmg.XXXXXX")
trap 'rm -rf "$stage"' EXIT
contents="$stage/contents"
mkdir -p "$contents/Quellcode" "$contents/VoxDrop"

/usr/bin/codesign --verify --strict "$bundle"
/usr/bin/ditto "$bundle" "$contents/VoxDrop/VoxDrop.app"
ln -s /Applications "$contents/Applications"
/usr/bin/git -C "$runtime/aTrain" archive --format=tar.gz \
    --prefix="aTrain-$reference/" -o "$contents/Quellcode/aTrain-$reference.tar.gz" "$reference"
/usr/bin/git -C "$project" archive --format=tar.gz \
    --prefix="VoxDrop-$code_commit/" -o "$contents/Quellcode/VoxDrop-$code_commit.tar.gz" "$code_commit"
cat > "$contents/Installation.txt" <<EOF
VoxDrop $version
Automatic Media Transcription

Voraussetzung ist ein Mac mit Apple Silicon und macOS $minimum oder neuer.

1. Den gesamten Ordner „VoxDrop“ in den Programme-Ordner ziehen.
   Darin „VoxDrop.app“ öffnen.
2. Unter Einstellungen → Transkription die Modelle herunterladen.
3. Für eine einmalige Transkription Ordner ins Fenster ziehen. Für die
   laufende Überwachung Ordner hinzufügen, die Ordnerüberwachung einschalten
   und mit dem Play-Knopf die Verarbeitung starten. Für SMB muss die Freigabe
   vorher eingehängt sein.

X blendet das Fenster in die Menüleiste aus; Minimieren legt es ins Dock.
„VoxDrop beenden“ und Cmd-Q stoppen die gesamte App und ihre Verarbeitung.
Der GPU-Budgetregler gibt kooperativ Rechenzeit frei; er begrenzt nicht den RAM.

Der einmalige Modell-Download benötigt Internet. Die Transkription und
Sprecherzuordnung erfolgen anschließend lokal auf dem Mac.

Die Modelle und der Download-Cache liegen danach unter
VoxDrop/Modelle, neben VoxDrop.app. Zum Entfernen der App samt Modellen
den gesamten Programmordner „VoxDrop“ löschen.
Persönliche Einstellungen und Verlauf liegen im Benutzerordner unter
Library/Application Support/VoxDrop.

macOS fragt beim ersten Start möglicherweise nach einer Freigabe.
Nach dem ersten Öffnungsversuch in Systemeinstellungen unter
Datenschutz & Sicherheit die App über „Dennoch öffnen“ bestätigen.
Der Build ist lokal signiert und besitzt keine Apple-Notarisierung.
https://support.apple.com/de-de/102445

Quellcode und Build-Anleitung
https://github.com/adriantagonist87/VoxDrop

Die Archive im Ordner Quellcode enthalten diesen VoxDrop-Quellstand und
die genaue aTrain-Revision einschließlich ihrer Lizenztexte.
EOF

/usr/bin/hdiutil create -quiet -fs HFS+ -volname "VoxDrop $version" \
    -srcfolder "$contents" -format UDZO "$stage/VoxDrop.dmg"
/usr/bin/hdiutil verify "$stage/VoxDrop.dmg"
mv "$stage/VoxDrop.dmg" "$output"
printf '%s\n' "$output"
