#!/usr/bin/env python3
"""
_populate_service.py — regenerate `_pages/service.md` from `service.json`.

`service.json` is the single source of truth for all service entries.
Edit that file to add or update entries, then run this script to propagate
changes into the Markdown page that Jekyll renders.

Usage:
    ./_populate_service.py              # write service.md
    ./_populate_service.py --dry-run    # print generated content, write nothing

Stdlib only — no external Python packages required.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
SERVICE_JSON = Path.home() / "Dropbox" / "_control" / "service.json"
SERVICE_MD = REPO_ROOT / "_pages" / "service.md"

FRONT_MATTER_RE = re.compile(r"^(---\n.*?\n---\n)", re.DOTALL)

# ---------------------------------------------------------------------------
# JSONC (JSON with // comments) — copied from _populate_papers.py
# ---------------------------------------------------------------------------

def strip_jsonc_comments(text: str) -> str:
    out: List[str] = []
    i, n = 0, len(text)
    in_string = False
    while i < n:
        c = text[i]
        if in_string:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1]); i += 2; continue
            if c == '"':
                in_string = False
            i += 1; continue
        if c == '"':
            in_string = True; out.append(c); i += 1; continue
        if c == "/" and i + 1 < n:
            if text[i + 1] == "/":
                while i < n and text[i] != "\n":
                    i += 1
                continue
            if text[i + 1] == "*":
                i += 2
                while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                    i += 1
                i += 2
                continue
        out.append(c); i += 1
    return "".join(out)

# ---------------------------------------------------------------------------
# Venue rendering
# ---------------------------------------------------------------------------

def format_venue(venue_long: str,
                 venue_short: Optional[str] = None,
                 venue_html: Optional[str] = None) -> str:
    """Return the HTML snippet for a venue name with the abbreviation bolded.

    Resolution order:
    1. `venue_html` — used verbatim when provided (escape hatch for unusual
       formatting like an abbreviation embedded mid-name alongside a second
       bold term, e.g. "ACM <b>MobiCom</b> workshop ... (<b>FICN</b>)").
    2. If `venue_short` appears as a whole word inside `venue_long`, it is
       bolded in-place: "ACM SIGMOD ..." → "ACM <b>SIGMOD</b> ...".
    3. Otherwise the abbreviation is appended in parentheses:
       "VLDB" → "International Conference ... (<b>VLDB</b>)".
    4. If there is no `venue_short`, `venue_long` is returned unchanged.
    """
    if venue_html:
        return venue_html
    if not venue_short:
        return venue_long
    pattern = r"\b" + re.escape(venue_short) + r"\b"
    if re.search(pattern, venue_long):
        return re.sub(pattern, f"<b>{venue_short}</b>", venue_long)
    return f"{venue_long} (<b>{venue_short}</b>)"

# ---------------------------------------------------------------------------
# Per-entry renderers
# ---------------------------------------------------------------------------

def _li(content: str) -> str:
    return f"      <li>{content}</li>"


def render_organization(entry: Dict[str, Any]) -> str:
    venue = format_venue(entry["venue_long"], entry.get("venue_short"), entry.get("venue_html"))
    if entry.get("track"):
        venue += f' <b>{entry["track"]}</b>'
    return _li(f'<i>{entry["role"]}</i>, {venue}, {entry["year"]}')


def render_pc_member(entry: Dict[str, Any]) -> str:
    venue = format_venue(entry["venue_long"], entry.get("venue_short"), entry.get("venue_html"))
    track_html = f' <b>{entry["track"]}</b>' if entry.get("track") else ""
    note_html  = f' ({entry["note"]})'        if entry.get("note")  else ""
    return _li(f'{venue}{track_html}, {entry["year"]}{note_html}')


def render_journal_reviewer(entry: Dict[str, Any]) -> str:
    venue = format_venue(entry["venue_long"], entry.get("venue_short"), entry.get("venue_html"))
    pub_html = f', {entry["publisher"]}' if entry.get("publisher") else ""
    return _li(f'{venue}{pub_html}')


def render_external_reviewer(entry: Dict[str, Any]) -> str:
    venue = format_venue(entry["venue_long"], entry.get("venue_short"), entry.get("venue_html"))
    years_str = ", ".join(str(y) for y in entry["years"])
    return _li(f'{venue} [{years_str}]')

# ---------------------------------------------------------------------------
# Section layout
# ---------------------------------------------------------------------------

SECTIONS = [
    {
        "key":           "organization",
        "title":         "organization",
        "margin_bottom": 0,
        "renderer":      render_organization,
    },
    {
        "key":           "pc_member",
        "title":         "program committee member",
        "margin_bottom": 20,
        "renderer":      render_pc_member,
    },
    {
        "key":           "journal_reviewer",
        "title":         "journal reviewer (selected)",
        "margin_bottom": 20,
        "renderer":      render_journal_reviewer,
    },
    {
        "key":           "external_reviewer",
        "title":         "external reviewer -- conferences (selected)",
        "margin_bottom": 120,
        "renderer":      render_external_reviewer,
    },
]


def render_section(title: str, margin_bottom: int, item_lines: List[str]) -> str:
    lines = [
        "",
        '<div class="projects">',
        "  <!-- Display categorized projects -->",
        f'  <h2 class="category" style="margin-top: -40px;">{title}</h2>',
        f'  <div style="width: 100%; float:left; margin-top: -20px; margin-bottom: {margin_bottom}px;">',
        "    <br> ",
        "    <ul>",
    ]
    lines.extend(item_lines)
    lines += [
        "    </ul>",
        "  </div>",
        "</div>",
        "",
    ]
    return "\n".join(lines)


def generate_body(data: Dict[str, Any]) -> str:
    parts: List[str] = []
    for sec in SECTIONS:
        entries = data.get(sec["key"], [])
        if not entries:
            continue
        item_lines = [sec["renderer"](e) for e in entries]
        parts.append(render_section(sec["title"], sec["margin_bottom"], item_lines))
    return "\n".join(parts)

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="print the generated content but do not write service.md")
    return ap.parse_args()


def main() -> int:
    args = parse_args()

    raw  = SERVICE_JSON.read_text(encoding="utf-8")
    data = json.loads(strip_jsonc_comments(raw))

    existing = SERVICE_MD.read_text(encoding="utf-8") if SERVICE_MD.exists() else ""
    m = FRONT_MATTER_RE.match(existing)
    front_matter = m.group(1) if m else "---\n---\n"

    body   = generate_body(data)
    output = front_matter + "\n" + body + "\n"

    if args.dry_run:
        print(output)
        print(f"  DRY-RUN: would write {SERVICE_MD.relative_to(REPO_ROOT)}")
        return 0

    SERVICE_MD.write_text(output, encoding="utf-8")
    print(f"  wrote {SERVICE_MD.relative_to(REPO_ROOT)}")

    ans = input("rebuild the site? [y/N] ").strip().lower()
    if ans in ("y", "yes"):
        try:
            subprocess.run(["bundle", "exec", "jekyll", "build"], cwd=REPO_ROOT, check=True)
            print("  site rebuilt")
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            print(f"  WARN: jekyll build failed: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
