#!/bin/sh
DEST="$HOME/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns"
SRC="$(cd "$(dirname "$0")" && pwd)/VVGenerator"
echo "Installing VV Generator to: $DEST/VVGenerator"
mkdir -p "$DEST" || exit 1
rm -rf "$DEST/VVGenerator"
cp -R "$SRC" "$DEST/VVGenerator" || { echo "Installation FAILED."; exit 1; }
[ -d "$DEST/VoronoiStructure" ] && echo "NOTE: old folder found: $DEST/VoronoiStructure - delete it by hand to avoid two buttons."
echo "Done. In Fusion: Utilities > Add-Ins (Shift+S) > VV Generator > Run."
echo "If Fusion was already running the add-in, Stop it and Run again."
echo "If the toolbar icon looks wrong after an update, restart Fusion once."
