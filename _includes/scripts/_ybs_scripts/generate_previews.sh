#!/bin/bash

PDF_DIR="/Users/sarkar-14/Git/personal/subhadeepsarkar.github.io/assets/fulltext"
PREVIEW_DIR="/Users/sarkar-14/Git/personal/subhadeepsarkar.github.io/assets/img/publication_preview"

for pdf in "$PDF_DIR"/*.pdf; do
  filename="$(basename "$pdf" .pdf)"
  output="$PREVIEW_DIR/$filename.png"
  if [ ! -f "$output" ]; then
    echo "Generating preview for: $filename"
    magick -density 150 "${pdf}[0]" -resize 400x -quality 90 "$output"
  fi
done

echo "Done."
