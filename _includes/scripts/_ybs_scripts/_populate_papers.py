#!/usr/bin/env python3
"""
_populate_papers.py — keep `_bibliography/papers.bib` and the publications page
in sync with a curated `publication.json`.

Workflow on each invocation:
  1. (First run only) Bootstrap publication.json from the existing papers.bib.
  2. Compare each JSON record to its papers.bib counterpart; interactively
     apply diffs.
  3. For new JSON records, render and insert a fresh BibTeX entry; if the key
     is a DBLP key, fetch canonical metadata first and cross-verify.
  4. For records flagged `dblp_citation_verified: false` and a paper age <= 3
     years, retry DBLP — capture canonical data and flip the flag if found.
  5. Generate PDF preview thumbnails for any new local PDFs.
  6. Ask whether to refresh Google Scholar citations (runs fetch_citations.sh).
  7. Ask whether to rebuild the site (`bundle exec jekyll build`).

Usage:
    ./_populate_papers.py                # interactive
    ./_populate_papers.py --dry-run      # show actions, never write
    ./_populate_papers.py --yes          # auto-confirm every prompt
    ./_populate_papers.py --bootstrap    # regenerate publication.json from papers.bib

Stdlib only — no external Python packages required.
"""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]                      # site root
PUB_JSON = SCRIPT_DIR / "publication.json"
PAPERS_BIB = REPO_ROOT / "_bibliography" / "papers.bib"
PUB_PAGE = REPO_ROOT / "_pages" / "publications.md"
FULLTEXT_DIR = REPO_ROOT / "assets" / "fulltext"
PREVIEW_DIR = REPO_ROOT / "assets" / "img" / "publication_preview"
FETCH_CITATIONS_SH = SCRIPT_DIR / "fetch_citations.sh"

# DBLP-recheck cutoff: paper must be at most this many years old
DBLP_RECHECK_AGE_YEARS = 3

# Field name → display column width for diff
FIELDS_TO_COMPARE = (
    "type", "title", "authors", "year", "month",
    "venue_long", "venue_short", "pages", "volume", "number", "series",
    "publisher", "school", "editor", "isbn", "issn",
    "doi", "url", "abstract",
    "howpublished", "note",
    "pdf", "preview", "arxiv", "website", "video", "slides", "poster",
    "code_repo", "purchase",
    "selected", "bibtex_show",
)

# Type → bib `@kind{}` mapping
TYPE_TO_BIB = {
    "inproceedings": "inproceedings",
    "article":       "article",
    "book":          "book",
    "incollection":  "incollection",
    "phdthesis":     "phdthesis",
    "mastersthesis": "mastersthesis",
    "techreport":    "techreport",
    "misc":          "misc",
    "patent":        "misc",  # BibTeX has no @patent; render as @misc with howpublished
}

# Local-only fields preserved when re-syncing from DBLP
LOCAL_ONLY_FIELDS = {
    "abbr", "abstract", "pdf", "preview", "selected", "bibtex_show",
    "arxiv", "website", "video", "slides", "poster", "code_repo", "purchase",
}

# Sample template kept at the top of publication.json. Re-emitted on every
# rewrite so it never disappears, even if the user accidentally deletes it.
TEMPLATE_RECORD: Dict[str, Any] = {
    "_comment": ("TEMPLATE — copy this object and replace fields when adding a "
                 "new paper. The script skips any entry whose key starts with an "
                 "underscore. Required: key, type, title, authors, year. Set "
                 "dblp_citation_verified=false for new manual entries so the "
                 "script can verify against DBLP on the next run."),
    "key": "_TEMPLATE_NEW_ENTRY",
    "type": "inproceedings",
    "title": "",
    "authors": [],
    "editor": [],
    "year": 0,
    "month": "",
    "venue_long": "",
    "venue_short": "",
    "pages": "",
    "volume": "",
    "number": "",
    "series": "",
    "publisher": "",
    "isbn": "",
    "issn": "",
    "doi": "",
    "url": "",
    "abstract": "",
    "pdf": "",
    "preview": "",
    "arxiv": "",
    "website": "",
    "video": "",
    "slides": "",
    "poster": "",
    "code_repo": "",
    "purchase": "",
    "selected": True,
    "bibtex_show": True,
    "dblp_citation_verified": False,
}


def write_publication_json(records: List[Dict[str, Any]]) -> None:
    """Serialise records to publication.json, with TEMPLATE_RECORD re-prepended
    as a JSONC `//`-commented block so it always stays at the top."""
    body = json.dumps(records, indent=2, ensure_ascii=False)
    tpl_text = json.dumps(TEMPLATE_RECORD, indent=2, ensure_ascii=False)
    tpl_block = "\n".join("  // " + ln for ln in tpl_text.split("\n")) + ","
    if body.startswith("[\n"):
        out = "[\n" + tpl_block + "\n" + body[2:]
    else:
        out = body
    PUB_JSON.write_text(out + "\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="show planned actions but do not write any files")
    ap.add_argument("--yes", action="store_true",
                    help="auto-confirm every interactive prompt (use with care)")
    ap.add_argument("--bootstrap", action="store_true",
                    help="(re)generate publication.json from papers.bib and exit")
    return ap.parse_args()


# ---------------------------------------------------------------------------
# IO helpers
# ---------------------------------------------------------------------------

def ask(prompt: str, default: bool = True, force: Optional[bool] = None) -> bool:
    """Yes/no prompt. `force` overrides interactive (used by --yes)."""
    if force is not None:
        return force
    suffix = " [Y/n] " if default else " [y/N] "
    while True:
        ans = input(prompt + suffix).strip().lower()
        if ans == "":
            return default
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        print("  please answer y or n")


def info(msg: str) -> None:
    print(f"  {msg}")


def heading(msg: str) -> None:
    print(f"\n=== {msg} ===")


# ---------------------------------------------------------------------------
# JSONC (JSON with comments) — pre-processor
# ---------------------------------------------------------------------------

def strip_jsonc_comments(text: str) -> str:
    """Strip `// line` and `/* block */` comments from a JSON-with-comments text.
    Comment-like sequences inside string literals are preserved."""
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
# Bib parsing (just enough to round-trip our entries)
# ---------------------------------------------------------------------------

def parse_bib_entry_block(text: str, start: int) -> Tuple[Dict[str, Any], int]:
    """Parse a single @TYPE{key, fields...} block starting at `start`.
    Returns (entry_dict, end_index_inclusive_of_closing_brace).
    """
    m = re.match(r"@(\w+)\s*\{\s*([A-Za-z0-9_:./\-]+)\s*,\s*", text[start:])
    if not m:
        raise ValueError(f"not an @entry at offset {start}")
    btype = m.group(1).lower()
    key = m.group(2)
    body_start = start + m.end()

    depth = 1
    i = body_start
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    body = text[body_start:i]
    end = i  # at the closing brace
    fields = parse_bib_fields(body)
    return {"type": btype, "key": key, "fields": fields, "raw": text[start:end + 1]}, end


def parse_bib_fields(body: str) -> Dict[str, str]:
    """Parse `field = {value}, field = "value", field = bareword,` style."""
    fields: Dict[str, str] = {}
    i = 0
    n = len(body)
    while i < n:
        while i < n and body[i] in " \t\n,":
            i += 1
        if i >= n:
            break
        m = re.match(r"(\w+)\s*=\s*", body[i:])
        if not m:
            break
        name = m.group(1).lower()
        i += m.end()
        if i >= n:
            break
        if body[i] == "{":
            depth = 1
            j = i + 1
            while j < n and depth > 0:
                if body[j] == "{":
                    depth += 1
                elif body[j] == "}":
                    depth -= 1
                j += 1
            value = body[i + 1: j - 1]  # strip outer braces
            i = j
        elif body[i] == '"':
            j = i + 1
            while j < n and body[j] != '"':
                if body[j] == "\\":
                    j += 1
                j += 1
            value = body[i + 1: j]
            i = j + 1
        else:
            j = i
            while j < n and body[j] not in ",\n":
                j += 1
            value = body[i:j].strip()
            i = j
        fields[name] = value
    return fields


def load_bib_entries(path: Path) -> Dict[str, Dict[str, Any]]:
    """Return key → entry dict for all @TYPE{} blocks in the file."""
    text = path.read_text()
    entries: Dict[str, Dict[str, Any]] = {}
    for m in re.finditer(r"@\w+\{", text):
        try:
            entry, _ = parse_bib_entry_block(text, m.start())
        except ValueError:
            continue
        entries[entry["key"]] = entry
    return entries


# ---------------------------------------------------------------------------
# Bib emission
# ---------------------------------------------------------------------------

def render_authors(authors: List[str]) -> str:
    """List of names → BibTeX author string."""
    return " and ".join(authors)


def render_bib_entry(rec: Dict[str, Any], dblp_extras: Optional[Dict[str, str]] = None) -> str:
    """Render a publication.json record as a BibTeX entry block.

    `dblp_extras` lets the caller inject DBLP-only fields (timestamp/biburl/
    bibsource) when known.
    """
    btype = TYPE_TO_BIB.get(rec.get("type", "misc"), "misc")
    key = rec["key"]
    out: List[Tuple[str, str]] = []

    # author/editor first
    if rec.get("authors"):
        out.append(("author", render_authors(rec["authors"])))
    if rec.get("editor"):
        out.append(("editor", render_authors(rec["editor"])))
    out.append(("title", rec["title"]))

    if rec["type"] in ("inproceedings", "incollection") and rec.get("venue_long"):
        out.append(("booktitle", rec["venue_long"]))
    elif rec["type"] == "article" and rec.get("venue_long"):
        out.append(("journal", rec["venue_long"]))
    elif rec["type"] in ("phdthesis", "mastersthesis") and rec.get("school"):
        out.append(("school", rec["school"]))
    elif rec["type"] == "book" and rec.get("publisher"):
        # Book uses publisher as the "venue"; emit it later in standard place.
        pass
    elif rec.get("venue_long"):
        out.append(("booktitle", rec["venue_long"]))

    for field in ("series", "volume", "number", "pages"):
        if rec.get(field):
            out.append((field, str(rec[field])))
    if rec.get("year"):
        out.append(("year", str(rec["year"])))
    if rec.get("month"):
        out.append(("month", rec["month"]))
    if rec.get("publisher"):
        out.append(("publisher", rec["publisher"]))
    for field in ("howpublished", "note", "isbn", "issn", "doi", "url"):
        if rec.get(field):
            out.append((field, rec[field]))

    if dblp_extras:
        for f in ("timestamp", "biburl", "bibsource"):
            if f in dblp_extras:
                out.append((f, dblp_extras[f]))

    if rec.get("venue_short"):
        out.append(("abbr", rec["venue_short"]))
    if rec.get("abstract"):
        out.append(("abstract", rec["abstract"]))
    if rec.get("preview"):
        out.append(("preview", rec["preview"]))

    # Local artifacts
    for field in ("pdf", "arxiv", "website", "video",
                  "slides", "poster", "code_repo", "purchase"):
        if rec.get(field):
            out.append((field, rec[field]))

    # Display flags
    if rec.get("selected"):
        out.append(("selected", "true"))
    if rec.get("bibtex_show"):
        out.append(("bibtex_show", "true"))

    width = max(len(f) for f, _ in out)
    lines = [f"@{btype}{{{key},"]
    for f, v in out:
        lines.append(f"  {f.ljust(width)} = {{{v}}},")
    if lines[-1].endswith(","):
        lines[-1] = lines[-1][:-1]
    lines.append("}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Bib → publication.json (bootstrap)
# ---------------------------------------------------------------------------

def bib_authors_to_list(s: str) -> List[str]:
    return [a.strip() for a in re.split(r"\band\b", s) if a.strip()]


def bib_to_record(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a parsed papers.bib entry to a publication.json record."""
    f = entry["fields"]
    btype = entry["type"]
    rec: Dict[str, Any] = {
        "key": entry["key"],
        "type": btype,
    }
    if "title" in f:        rec["title"] = f["title"]
    if "author" in f:       rec["authors"] = bib_authors_to_list(f["author"])
    if "editor" in f:       rec["editor"] = bib_authors_to_list(f["editor"])
    if "year" in f:
        try: rec["year"] = int(f["year"])
        except ValueError: rec["year"] = f["year"]
    if "month" in f:        rec["month"] = f["month"]
    if "booktitle" in f:    rec["venue_long"] = f["booktitle"]
    elif "journal" in f:    rec["venue_long"] = f["journal"]
    if "series" in f:       rec["series"] = f["series"]
    if "volume" in f:       rec["volume"] = f["volume"]
    if "number" in f:       rec["number"] = f["number"]
    if "pages" in f:        rec["pages"] = f["pages"]
    if "publisher" in f:    rec["publisher"] = f["publisher"]
    if "school" in f:       rec["school"] = f["school"]
    if "isbn" in f:         rec["isbn"] = f["isbn"]
    if "issn" in f:         rec["issn"] = f["issn"]
    if "doi" in f:          rec["doi"] = f["doi"]
    if "url" in f:          rec["url"] = f["url"]
    if "howpublished" in f: rec["howpublished"] = f["howpublished"]
    if "note" in f:         rec["note"] = f["note"]
    if "abstract" in f:     rec["abstract"] = f["abstract"]
    if "abbr" in f:         rec["venue_short"] = f["abbr"]
    if "preview" in f:      rec["preview"] = f["preview"]
    for art in ("pdf", "arxiv", "website", "video",
                "slides", "poster", "code_repo", "purchase"):
        if art in f:
            rec[art] = f[art]
    if f.get("selected", "").lower() == "true":
        rec["selected"] = True
    if f.get("bibtex_show", "").lower() == "true":
        rec["bibtex_show"] = True
    # Default the flag — bootstrap assumes existing entries are already in
    # whatever state they are; user can flip to false to force re-verify.
    rec["dblp_citation_verified"] = entry["key"].startswith("DBLP:") and "biburl" in f \
                                    or not entry["key"].startswith("DBLP:")
    return rec


def bootstrap(args: argparse.Namespace) -> None:
    if PUB_JSON.exists() and not args.bootstrap:
        return  # nothing to do
    if PUB_JSON.exists() and args.bootstrap:
        info(f"overwriting existing {PUB_JSON.name}")
    heading("Bootstrapping publication.json from papers.bib")
    bib = load_bib_entries(PAPERS_BIB)
    records = [bib_to_record(e) for e in bib.values()]
    # sort by year desc, then key
    records.sort(key=lambda r: (-(r.get("year") or 0), r.get("key", "")))
    if args.dry_run:
        info(f"DRY-RUN: would write {len(records)} records to {PUB_JSON}")
        return
    write_publication_json(records)
    info(f"wrote {len(records)} records to {PUB_JSON}")


# ---------------------------------------------------------------------------
# DBLP fetch
# ---------------------------------------------------------------------------

def fetch_dblp_record(dblp_key: str) -> Optional[Dict[str, Any]]:
    """Fetch DBLP bibtex for a key like 'conf/sigmod/SarkarPSA20'.
    Returns parsed entry dict, or None if not found / network failure.
    """
    url = f"https://dblp.org/rec/{dblp_key}.bib"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "populate_papers/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            text = r.read().decode("utf-8")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return None
    if "@" not in text:
        return None
    m = re.search(r"@\w+\{", text)
    if not m:
        return None
    entry, _ = parse_bib_entry_block(text, m.start())
    return entry


# ---------------------------------------------------------------------------
# Diffing & sync
# ---------------------------------------------------------------------------

def _norm(v: Any) -> Any:
    """Normalise empty strings / empty lists / False to None for diff comparison.
    `False` is treated as absent because the bib emission only writes
    boolean flags (`selected`, `bibtex_show`) when they're true."""
    if v is None:
        return None
    if isinstance(v, str) and v.strip() == "":
        return None
    if isinstance(v, (list, tuple)) and len(v) == 0:
        return None
    if v is False:
        return None
    return v


def field_diff(rec_json: Dict[str, Any], rec_bib: Dict[str, Any]) -> List[Tuple[str, Any, Any]]:
    """Return list of (field, value_in_bib, value_in_json) for differing fields.
    Empty strings/lists in JSON are treated as equivalent to absent in bib."""
    diffs: List[Tuple[str, Any, Any]] = []
    bib_view = bib_to_record(rec_bib)
    for f in FIELDS_TO_COMPARE:
        jv = _norm(rec_json.get(f))
        bv = _norm(bib_view.get(f))
        if jv == bv:
            continue
        diffs.append((f, bib_view.get(f), rec_json.get(f)))
    return diffs


def show_diffs(key: str, diffs: List[Tuple[str, Any, Any]]) -> None:
    heading(f"{key}: {len(diffs)} field(s) differ")
    for f, bib_val, json_val in diffs:
        b = json.dumps(bib_val, ensure_ascii=False) if bib_val is not None else "(absent)"
        j = json.dumps(json_val, ensure_ascii=False) if json_val is not None else "(absent)"
        print(f"  {f}:")
        print(f"    bib:  {b}")
        print(f"    json: {j}")


# ---------------------------------------------------------------------------
# Bib file mutation
# ---------------------------------------------------------------------------

def replace_bib_entry(text: str, key: str, new_block: str) -> Tuple[str, bool]:
    pat = re.compile(r"@\w+\{\s*" + re.escape(key) + r"\s*,")
    m = pat.search(text)
    if not m:
        return text, False
    start = m.start()
    depth = 0
    i = start
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    return text[:start] + new_block + text[i + 1:], True


def prepend_bib_entry(text: str, new_block: str) -> str:
    """Insert a new entry just above the first existing @entry block.
    Any leading file-header comments remain on top."""
    m = re.search(r"^@\w+\{", text, re.MULTILINE)
    if not m:
        # empty bib — just put the entry in
        return new_block + "\n"
    head = text[:m.start()]
    rest = text[m.start():]
    return head + new_block + "\n\n" + rest


# ---------------------------------------------------------------------------
# Preview generation
# ---------------------------------------------------------------------------

def ensure_publications_years(records: List[Dict[str, Any]], dry_run: bool) -> bool:
    """Make sure `_pages/publications.md`'s `years:` front-matter list contains
    every year found in `records`. Years are kept in descending order. Returns
    True if a change was needed."""
    if not PUB_PAGE.exists():
        return False
    text = PUB_PAGE.read_text()
    m = re.search(r"^years:\s*\[([^\]]*)\]\s*$", text, re.MULTILINE)
    if not m:
        info(f"WARN: {PUB_PAGE.name} has no `years:` front-matter; skipping")
        return False
    existing = [int(y.strip()) for y in m.group(1).split(",") if y.strip().isdigit()]
    needed = {int(r["year"]) for r in records if r.get("year")}
    merged = sorted(set(existing) | needed, reverse=True)
    if merged == existing:
        return False
    added = sorted(set(merged) - set(existing), reverse=True)
    info(f"adding year(s) {added} to {PUB_PAGE.name}")
    if dry_run:
        info(f"DRY-RUN: would update {PUB_PAGE.name}")
        return True
    new_line = "years: [" + ", ".join(str(y) for y in merged) + "]"
    PUB_PAGE.write_text(text[:m.start()] + new_line + text[m.end():])
    return True


def derive_pdf_filename(title: str) -> str:
    """Title → expected filename in `assets/fulltext/`. Strips HTML/BibTeX
    braces, collapses whitespace and `:` to `_`, leaves hyphens/`+` intact."""
    s = re.sub(r"<[^>]+>", "", title)        # strip HTML tags
    s = re.sub(r"[{}]", "", s)                # strip BibTeX braces
    s = s.replace(":", "")                    # drop colons
    s = re.sub(r"\s+", "_", s.strip())        # whitespace → _
    return s + ".pdf"


def resolve_pdf_for_new_entry(rec: Dict[str, Any], force_yes: bool) -> None:
    """If the new record has no `pdf` field set, try to derive it from the
    title and prompt the user to confirm/edit. Mutates `rec` in place."""
    if rec.get("pdf"):
        return
    candidate = derive_pdf_filename(rec.get("title", ""))
    candidate_path = FULLTEXT_DIR / candidate
    if candidate_path.exists():
        info(f"auto-detected PDF: {candidate}")
        if ask("use this PDF?", default=True, force=force_yes or None):
            rec["pdf"] = candidate
            return
    if force_yes:
        return
    typed = input("  PDF filename in assets/fulltext/ (blank to skip): ").strip()
    if typed:
        rec["pdf"] = typed


def prompt_optional_fields(rec: Dict[str, Any], force_yes: bool) -> None:
    """For a new entry, walk the user through any empty optional fields so
    they can be filled at creation time (otherwise they'd silently render as
    nothing on the publications page)."""
    if force_yes:
        return
    field_prompts = [
        ("abstract",   "Abstract (single line)"),
        ("doi",        "DOI"),
        ("url",        "URL"),
        ("arxiv",      "arXiv ID (e.g. 2006.04777)"),
        ("code_repo",  "Code repo URL"),
        ("slides",     "Slides (filename in assets/resources/ or URL)"),
        ("poster",     "Poster (filename or URL)"),
        ("video",      "Video URL"),
        ("website",    "Project website URL"),
    ]
    empty = [(f, label) for f, label in field_prompts if not _norm(rec.get(f))]
    if not empty:
        return
    if not ask(f"fill any of {len(empty)} optional fields now?", default=True):
        return
    info("press Enter to skip a field; type a value to set it.")
    for field, label in empty:
        val = input(f"  {label}: ").strip()
        if val:
            rec[field] = val


def has_imagemagick() -> bool:
    try:
        subprocess.run(["magick", "-version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def generate_preview(pdf_filename: str, dry_run: bool) -> bool:
    """Generate an `_assets/img/publication_preview/<basename>.png` if missing.
    Returns True if it created a file (or would in dry-run)."""
    pdf_path = FULLTEXT_DIR / pdf_filename
    if not pdf_path.exists():
        info(f"skip preview: PDF missing → {pdf_path}")
        return False
    out_path = PREVIEW_DIR / (pdf_path.stem + ".png")
    if out_path.exists():
        return False
    if dry_run:
        info(f"DRY-RUN: would generate preview {out_path.name}")
        return True
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["magick", "-density", "150", f"{pdf_path}[0]",
         "-resize", "400x", "-quality", "90", str(out_path)],
        check=True,
    )
    info(f"generated preview {out_path.name}")
    return True


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------

def current_year() -> int:
    return dt.date.today().year


def process_existing(rec: Dict[str, Any], bib_entry: Dict[str, Any],
                     bib_text: str, args: argparse.Namespace) -> Tuple[str, bool]:
    """Sync an existing JSON record to papers.bib if user accepts diffs."""
    diffs = field_diff(rec, bib_entry)
    if not diffs:
        return bib_text, False
    show_diffs(rec["key"], diffs)
    if not ask("apply these changes to papers.bib?", default=True, force=args.yes or None):
        return bib_text, False
    new_block = render_bib_entry(rec, _dblp_extras_from(bib_entry))
    if args.dry_run:
        info("DRY-RUN: would replace bib entry")
        return bib_text, True
    new_text, ok = replace_bib_entry(bib_text, rec["key"], new_block)
    if not ok:
        info(f"WARN: failed to replace {rec['key']} in papers.bib (key not found)")
        return bib_text, False
    return new_text, True


def _dblp_extras_from(bib_entry: Dict[str, Any]) -> Dict[str, str]:
    return {f: bib_entry["fields"][f] for f in ("timestamp", "biburl", "bibsource")
            if f in bib_entry["fields"]}


def process_new(rec: Dict[str, Any], bib_text: str,
                args: argparse.Namespace) -> Tuple[str, bool]:
    """Create a fresh papers.bib entry for a new JSON record."""
    heading(f"NEW: {rec['key']}")
    print(json.dumps(rec, indent=2, ensure_ascii=False))

    dblp_extras: Dict[str, str] = {}
    if rec["key"].startswith("DBLP:") and not rec.get("dblp_citation_verified", False):
        bare = rec["key"][len("DBLP:"):]
        info(f"verifying with DBLP: {bare}")
        dblp = fetch_dblp_record(bare)
        if dblp:
            dblp_diff = compare_with_dblp(rec, dblp)
            if dblp_diff:
                heading("DBLP returned different metadata")
                for f, dval, jval in dblp_diff:
                    print(f"  {f}:")
                    print(f"    json: {json.dumps(jval, ensure_ascii=False)}")
                    print(f"    dblp: {json.dumps(dval, ensure_ascii=False)}")
                if ask("adopt DBLP values for these fields?", default=True, force=args.yes or None):
                    apply_dblp(rec, dblp)
            rec["dblp_citation_verified"] = True
            dblp_extras = {f: dblp["fields"][f] for f in ("timestamp", "biburl", "bibsource")
                           if f in dblp["fields"]}
        else:
            info(f"DBLP has no record for {bare} (yet)")
            rec["dblp_citation_verified"] = False

    if not ask("add this entry to papers.bib?", default=True, force=args.yes or None):
        return bib_text, False
    # Make sure we know which PDF this entry maps to before rendering the bib.
    resolve_pdf_for_new_entry(rec, args.yes)
    # Default new entries to `selected = true` so they appear in the
    # featured-publications section unless the user explicitly opts out.
    rec.setdefault("selected", True)
    if rec["selected"] is False:
        rec["selected"] = True
    new_block = render_bib_entry(rec, dblp_extras or None)
    if args.dry_run:
        info("DRY-RUN: would append entry")
        return bib_text, True
    return prepend_bib_entry(bib_text, new_block), True


def compare_with_dblp(rec: Dict[str, Any], dblp: Dict[str, Any]) -> List[Tuple[str, Any, Any]]:
    """Return diff (field, dblp_value, json_value) for a new record vs. DBLP."""
    dblp_view = bib_to_record(dblp)
    diffs: List[Tuple[str, Any, Any]] = []
    for f in ("title", "authors", "year", "venue_long",
              "pages", "volume", "number", "publisher", "doi", "url"):
        jv = rec.get(f)
        dv = dblp_view.get(f)
        if dv is not None and jv != dv:
            diffs.append((f, dv, jv))
    return diffs


def apply_dblp(rec: Dict[str, Any], dblp: Dict[str, Any]) -> None:
    """Mutate `rec` to absorb DBLP-canonical fields."""
    dblp_view = bib_to_record(dblp)
    for f in ("title", "authors", "year", "venue_long",
              "pages", "volume", "number", "publisher", "doi", "url"):
        if f in dblp_view:
            rec[f] = dblp_view[f]


def recheck_dblp_missing(rec: Dict[str, Any], bib_text: str,
                         args: argparse.Namespace) -> Tuple[str, bool]:
    """For dblp_citation_verified=false records within age cutoff, retry DBLP."""
    if rec.get("dblp_citation_verified", True):
        return bib_text, False
    if not rec["key"].startswith("DBLP:"):
        rec["dblp_citation_verified"] = True
        return bib_text, True
    age = current_year() - int(rec.get("year", 0))
    if age > DBLP_RECHECK_AGE_YEARS:
        return bib_text, False
    bare = rec["key"][len("DBLP:"):]
    info(f"re-checking DBLP for {rec['key']} (age {age}y) ...")
    dblp = fetch_dblp_record(bare)
    if not dblp:
        info("  still missing; will retry next run")
        return bib_text, False
    info("  found! showing diff vs JSON")
    diffs = compare_with_dblp(rec, dblp)
    for f, dv, jv in diffs:
        print(f"    {f}: dblp={json.dumps(dv, ensure_ascii=False)}  json={json.dumps(jv, ensure_ascii=False)}")
    if ask("adopt DBLP values & mark verified?", default=True, force=args.yes or None):
        apply_dblp(rec, dblp)
        rec["dblp_citation_verified"] = True
        new_block = render_bib_entry(rec, _dblp_extras_from(dblp))
        if args.dry_run:
            info("DRY-RUN: would update bib entry from DBLP")
            return bib_text, True
        new_text, ok = replace_bib_entry(bib_text, rec["key"], new_block)
        if ok:
            return new_text, True
        return prepend_bib_entry(bib_text, new_block), True
    return bib_text, False


def main() -> int:
    args = parse_args()

    # 1. Bootstrap if missing
    if args.bootstrap or not PUB_JSON.exists():
        bootstrap(args)
        if args.bootstrap:
            return 0

    # 2. Load both sides
    raw = PUB_JSON.read_text()
    had_comments = ("//" in raw) or ("/*" in raw)
    all_records: List[Dict[str, Any]] = json.loads(strip_jsonc_comments(raw))
    # Skip template entries (keys starting with underscore) and any record
    # explicitly flagged `placeholder: true` (e.g. al-folio sample entries).
    records = [r for r in all_records
               if not r.get("key", "").startswith("_")
               and not r.get("placeholder")]
    bib_entries = load_bib_entries(PAPERS_BIB)
    bib_text = PAPERS_BIB.read_text()

    json_dirty = False
    bib_dirty = False
    new_pdfs: List[str] = []

    # 3. Existing — compare and sync
    for rec in records:
        key = rec["key"]
        if key in bib_entries:
            bib_text, changed = process_existing(rec, bib_entries[key], bib_text, args)
            if changed:
                bib_dirty = True
            # Re-check missing DBLP
            bib_text, drec = recheck_dblp_missing(rec, bib_text, args)
            if drec:
                json_dirty = True
                bib_dirty = True

    # 4. New — append entries
    for rec in records:
        key = rec["key"]
        if key not in bib_entries:
            bib_text, changed = process_new(rec, bib_text, args)
            if changed:
                bib_dirty = True
                json_dirty = True
                if rec.get("pdf"):
                    new_pdfs.append(rec["pdf"])

    # 5. Persist
    if json_dirty and not args.dry_run:
        if had_comments:
            info(f"NOTE: {PUB_JSON.name} contained // or /* */ comments — "
                 f"those are stripped on rewrite (the sample template is "
                 f"re-prepended automatically; other comments need to be re-added).")
        write_publication_json(records)
        info(f"wrote {PUB_JSON.name}")
    if bib_dirty and not args.dry_run:
        PAPERS_BIB.write_text(bib_text)
        info(f"wrote {PAPERS_BIB.relative_to(REPO_ROOT)}")

    # 5b. Ensure publications.md exposes every year present in records
    ensure_publications_years(records, args.dry_run)

    # 6. Generate previews — for new PDFs *and* any existing record whose
    # preview thumbnail is missing (handles `pdf` field changes on edits).
    pdfs_to_preview: List[str] = list(new_pdfs)
    for r in records:
        pdf = r.get("pdf")
        if not pdf or pdf in pdfs_to_preview:
            continue
        if not (PREVIEW_DIR / (Path(pdf).stem + ".png")).exists():
            pdfs_to_preview.append(pdf)
    if pdfs_to_preview:
        if not has_imagemagick():
            info("WARN: ImageMagick not on PATH; skipping preview generation")
        else:
            heading("Generating PDF previews")
            for pdf in pdfs_to_preview:
                generate_preview(pdf, args.dry_run)

    # 7. Optionally refresh citations (skip prompt under --yes or --dry-run)
    if not args.yes and not args.dry_run \
            and ask("refresh Google Scholar citations now?", default=False):
        if FETCH_CITATIONS_SH.exists():
            subprocess.run(["bash", str(FETCH_CITATIONS_SH)], check=False)
            info("citations refreshed")
        else:
            info(f"WARN: {FETCH_CITATIONS_SH.name} not found")

    # 8. Rebuild the site (unless --dry-run)
    if not args.dry_run:
        try:
            subprocess.run(["bundle", "exec", "jekyll", "build"], cwd=REPO_ROOT, check=True)
            info("site rebuilt")
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            info(f"WARN: jekyll build failed: {e}")

    print()
    info("done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
