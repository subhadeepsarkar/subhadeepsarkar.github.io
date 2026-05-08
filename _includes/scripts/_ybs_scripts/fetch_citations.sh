#!/bin/bash
# Refresh Scholar citation data by scraping the live profile.
# Falls back to the Dropbox snapshot only if Scholar served a CAPTCHA.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
DROPBOX_SNAPSHOT="/Users/sarkar-14/Dropbox/_control/citations.json"

if python3 "$SCRIPT_DIR/_fetch_citations.py"; then
  exit 0
fi

echo "WARN: live Scholar fetch failed; falling back to Dropbox snapshot" >&2
if [ -f "$DROPBOX_SNAPSHOT" ]; then
  cp "$DROPBOX_SNAPSHOT" "$SCRIPT_DIR/citations.json"
  cp "$DROPBOX_SNAPSHOT" "$REPO_ROOT/_data/citations.json"
  echo "  copied stale snapshot from $DROPBOX_SNAPSHOT" >&2
else
  echo "ERROR: no Dropbox fallback at $DROPBOX_SNAPSHOT" >&2
  exit 1
fi
