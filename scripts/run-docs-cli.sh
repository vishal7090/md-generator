#!/usr/bin/env bash
# Convert every supported file under docs/ using only md-* commands.
# Usage (from repo root): bash scripts/run-docs-cli.sh
# Requires: pip install -e ".[pdf,word,ppt,xlsx,image,text,archive]"

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOCS_DIR="${DOCS_DIR:-$REPO_ROOT/docs}"
OUT_DIR="${OUT_DIR:-$DOCS_DIR/cli-output}"
IMAGE_ENGINES="${IMAGE_ENGINES:-tess}"

for c in md-pdf md-word md-ppt md-xlsx md-image md-text md-zip; do
  command -v "$c" >/dev/null 2>&1 || { echo "Missing $c on PATH. Run: pip install -e '.[pdf,word,ppt,xlsx,image,text,archive]'" >&2; exit 1; }
done

mkdir -p "$OUT_DIR"

safe_name() {
  basename "$1" | sed -e 's/\.[^.]*$//' | tr -c 'A-Za-z0-9._-' '_' | sed 's/^[._]*//;s/[._]*$//'
}

fail=0
while IFS= read -r -d '' f; do
  case "$f" in
    *"/cli-output/"*) continue ;;
  esac
  ext="${f##*.}"
  ext=".$(printf '%s' "$ext" | tr '[:upper:]' '[:lower:]')"
  base="$(safe_name "$f")"
  dest="$OUT_DIR/$base"
  rel="${f#$DOCS_DIR/}"

  case "$ext" in
    .md)
      echo "[SKIP] $rel (already markdown)"
      continue
      ;;
  esac

  echo ""
  echo "=== $rel ==="
  mkdir -p "$dest"

  case "$ext" in
    .pdf)
      md-pdf "$f" "$dest" --artifact-layout || fail=1
      ;;
    .docx)
      md-word "$f" "$dest/document.md" --images-dir "$dest/images" || fail=1
      ;;
    .pptx)
      md-ppt "$f" "$dest" --artifact-layout --no-extract-embedded-deep || fail=1
      ;;
    .xlsx|.xlsm|.csv)
      md-xlsx -i "$f" -o "$dest" || fail=1
      ;;
    .zip)
      md-zip "$f" "$dest" || fail=1
      ;;
    .json|.xml|.txt)
      md-text "$f" "$dest/document.md" || fail=1
      ;;
    .png|.jpg|.jpeg|.webp|.tif|.tiff|.bmp|.gif)
      md-image "$f" "$dest/document.md" --engines "$IMAGE_ENGINES" --strategy best --title "$base" || fail=1
      ;;
    *)
      echo "[SKIP] $rel (extension $ext not mapped)"
      ;;
  esac
done < <(find "$DOCS_DIR" -type f ! -path "*/cli-output/*" -print0)

echo ""
echo "Done. Outputs under: $OUT_DIR"
exit "$fail"
