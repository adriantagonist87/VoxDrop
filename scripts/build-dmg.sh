#!/bin/sh
set -eu

project=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
runtime="$project/.runtime"
bundle="$runtime/package/VoxDrop.app"
version=$(/usr/bin/plutil -extract CFBundleShortVersionString raw -o - "$bundle/Contents/Info.plist")
minimum=$(/usr/bin/plutil -extract LSMinimumSystemVersion raw -o - "$bundle/Contents/Info.plist")
reference=$(sed -n 's/^commit=//p' "$project/scripts/bootstrap.sh")
output="$runtime/package/VoxDrop-$version-macOS-arm64.dmg"
stage=$(mktemp -d "$runtime/package/.dmg.XXXXXX")
trap 'rm -rf "$stage"' EXIT
contents="$stage/contents"
mkdir -p "$contents/Quellcode"

/usr/bin/codesign --verify --strict "$bundle"
/usr/bin/ditto "$bundle" "$contents/VoxDrop.app"
ln -s /Applications "$contents/Applications"
/usr/bin/git -C "$runtime/aTrain" archive --format=tar.gz \
    --prefix="aTrain-$reference/" -o "$contents/Quellcode/aTrain-$reference.tar.gz" "$reference"
cat > "$contents/Installation.txt" <<EOF
VoxDrop $version
Automatic Media Transcription

Voraussetzung ist ein Mac mit Apple Silicon und macOS $minimum oder neuer.

1. VoxDrop in den Programme-Ordner ziehen und dort öffnen.
2. Unter Modell auf „Modelle herunterladen“ klicken.
3. Für eine einmalige Transkription Ordner ins Fenster ziehen. Für die
   laufende Überwachung Ordner hinzufügen, die Ordnerüberwachung einschalten
   und den Dienst starten. Für SMB muss die Freigabe vorher eingehängt sein.

Der einmalige Modell-Download benötigt Internet. Die Transkription und
Sprecherzuordnung erfolgen anschließend lokal auf dem Mac.

Quellcode und Build-Anleitung
https://github.com/adriantagonist87/VoxDrop

Das Archiv im Ordner Quellcode enthält die genaue aTrain-Revision,
deren Code und Lizenz im App-Bundle enthalten sind.
EOF

/usr/bin/hdiutil create -quiet -fs HFS+ -volname "VoxDrop $version" \
    -srcfolder "$contents" -format UDZO "$stage/VoxDrop.dmg"
/usr/bin/hdiutil verify "$stage/VoxDrop.dmg"
mv "$stage/VoxDrop.dmg" "$output"
printf '%s\n' "$output"
