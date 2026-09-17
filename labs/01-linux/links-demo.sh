#!/usr/bin/env bash
set -euo pipefail

DEMO_DIR="${1:-/tmp/link-demo}"

rm -rf "$DEMO_DIR"
mkdir -p "$DEMO_DIR"
cd "$DEMO_DIR"

echo "==> Step 1: create the original file"
echo "Hello from the original file" > original.txt
ls -li original.txt

echo
echo "==> Step 2: create a hard link and a soft link"
ln original.txt hardlink.txt
ln -s original.txt softlink.txt
ls -li

echo
echo "==> Step 3: inode number and link count"
stat -c '%n : inode %i, %h link(s), %s bytes, type %F' original.txt hardlink.txt softlink.txt

echo
echo "==> Step 4: every name reads the same data"
for f in original.txt hardlink.txt softlink.txt; do
    printf '%-14s -> %s\n' "$f" "$(cat "$f")"
done

echo
echo "==> Step 5: write through the hard link, read through the original"
echo "Line added through the hard link" >> hardlink.txt
cat original.txt

echo
echo "==> Step 6: delete the original file"
rm original.txt
ls -li

echo
echo "==> Step 7: the hard link still holds the data"
cat hardlink.txt

echo
echo "==> Step 8: the soft link is now dangling"
if cat softlink.txt 2>/dev/null; then
    echo "soft link still resolves"
else
    echo "cat softlink.txt failed: the target it pointed at is gone"
fi
ls -l softlink.txt

echo
echo "==> Step 9: delete both links and confirm the directory is empty"
rm -f hardlink.txt softlink.txt
ls -A "$DEMO_DIR" || true
echo "remaining entries: $(ls -A "$DEMO_DIR" | wc -l)"
