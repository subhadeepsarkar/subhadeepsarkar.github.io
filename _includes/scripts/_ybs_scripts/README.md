# `_ybs_scripts/`

Helper scripts that keep this Jekyll site's auto-generated artifacts (citation counts, publication previews) in sync with their upstream sources. 
Run these manually before a `bundle exec jekyll build`/`serve` whenever the underlying data changes (new paper, new Scholar refresh, new local PDF).

`citations.json` in this folder is a data artifact, not a script — it is the local snapshot that `fetch_citations.sh` writes alongside the canonical copy in `_data/`. 
Jekyll reads only the `_data/` copy at build time.

---

## `fetch_citations.sh`

**Description.** Pulls the latest Google Scholar citation snapshot from a
Dropbox-controlled JSON and installs it into the two locations the site needs.

**Workflow.**

1. Reads the source file at the hard-coded path `/Users/sarkar-14/Dropbox/_control/citations.json`. This file is produced externally (Scholar scraper / manual export) and lives outside this repo so multiple machines can share it.
2. Copies the file verbatim to two destinations:
   - `_includes/scripts/_ybs_scripts/citations.json` — local snapshot in this folder, kept for traceability/diff.
   - `_data/citations.json` — the canonical location Jekyll reads via `site.data.citations` at build time. The `bib.html` layout looks up each entry's title here to render the Google Scholar citation badge (`scholar-badge`) next to the publication's icon row.
3. The next `bundle exec jekyll build` picks up the new counts; no other action is required. The badge only renders for entries with a non-zero `cited_by` value, so the site silently degrades for new/uncited papers.

**Prerequisites.** Dropbox is mounted; the source `citations.json` exists and is well-formed JSON with the `publications[].title` and `publications[].cited_by` fields populated. 
The script will fail loudly (via `cp`) if the source path is missing.

---

## `generate_previews.sh`

**Description.** Renders the first page of every PDF in `assets/fulltext/` into a PNG thumbnail under `assets/img/publication_preview/`, skipping any PDF whose preview already exists.

**Workflow.**

1. Iterates over every `*.pdf` file in `assets/fulltext/` (the directory that holds the locally-mirrored full-text PDFs of all publications).
1. For each PDF, computes the expected preview path as `assets/img/publication_preview/<basename>.png` — same filename, `.pdf` replaced with `.png`.
2. **Idempotency check:** if that PNG already exists, it is skipped — no work is repeated. This keeps the script safe to re-run and cheap on repeat invocations after only a few new PDFs are added.
3. For PDFs without a matching PNG, runs ImageMagick:
   - `magick -density 150 "<pdf>[0]" -resize 400x -quality 90 <png>`
   - `[0]` extracts only the first page.
   - `-density 150` rasterises at 150 DPI (sharp enough for thumbnails).
   - `-resize 400x` scales width to 400px, height auto-computed to preserve the original aspect ratio.
   - `-quality 90` sets the PNG filter/compression quality (90 ≈ nearly lossless, modest file size).
4. Prints `Generating preview for: <filename>` for each PDF actually rendered, then a trailing `Done.` once the loop finishes.
5. Output PNGs are consumed by [`_layouts/bib.html`](../../../_layouts/bib.html), which derives the preview path from each entry's `pdf` field (`pdf | remove: '.pdf' | append: '.png'`) and renders it in the left-hand `.col-sm-2.abbr` column of the publications page.

**Prerequisites.** ImageMagick 7+ is installed (`magick` on `$PATH`).
Ghostscript is required by ImageMagick to rasterise PDFs; on macOS it ships with the Homebrew `imagemagick` formula. 
If a PDF fails to render, ImageMagick will print to stderr and move on to the next file — re-run after fixing the source PDF to fill in the missing preview.

---

## `_populate_papers.py`

**Description.** Source-of-truth bridge between a hand-curated `publication.json`
in this folder and the site's `_bibliography/papers.bib`. It diffs the two,
applies user-confirmed changes, fetches/verifies DBLP metadata for new or
unverified entries, generates missing PDF previews, and (optionally) refreshes
Scholar citations and rebuilds the site.

**Workflow.**

1. **Bootstrap (first run only).** If `publication.json` is missing, the
   script reads every `@TYPE{key,...}` block from `papers.bib`, converts each
   into a JSON record, and writes the full set to `publication.json` sorted
   by year (descending). Pass `--bootstrap` to regenerate explicitly.
2. **Load both sides.** Reads `publication.json` (the curated source of
   truth) and parses `papers.bib` into a dict keyed by entry key.
3. **Sync existing entries.** For every record whose `key` is already in
   `papers.bib`, it diffs each tracked field (title, authors, year, venue,
   pages, DOI, all artifact links, etc.). On any difference it shows a
   field-by-field comparison and asks "apply changes?" — only on yes does it
   re-render and replace the bib block. Local-only fields (`abbr`, `abstract`,
   `pdf`, `slides`, …) are preserved.
4. **DBLP re-check (≤ 3 years).** For records flagged
   `dblp_citation_verified: false` whose paper age is at most three years,
   the script fetches `https://dblp.org/rec/<bare-key>.bib`, shows a diff
   against the current JSON, and (with confirmation) absorbs DBLP-canonical
   fields and flips the flag to `true`. Older missing entries are skipped —
   if DBLP hasn't indexed it after three years it likely never will.
5. **New entries.** Any record whose key is *not* in `papers.bib` is treated
   as new: the parsed JSON is shown, DBLP is queried (if the key starts
   `DBLP:` and is unverified), differences are surfaced, and the user
   confirms before the entry is appended to the bib. The flag is updated.
6. **Generate previews.** For each new paper with a `pdf` field, the script
   runs the same ImageMagick command as `generate_previews.sh` (first page,
   density 150, width 400px). The site's existing CSS overlay handles the
   colored venue badge ("banner") on top — no image-side annotation is
   burned into the PNG.
7. **Refresh citations (optional).** Asks `refresh Google Scholar citations
   now?` — on yes, runs `fetch_citations.sh`.
8. **Rebuild site (optional).** Asks `rebuild the site?` — on yes, runs
   `bundle exec jekyll build` from the repo root.

**Flags.**

- `--dry-run` — print every action but write nothing. Safe for inspection.
- `--yes` — auto-confirm every prompt. Use only when you trust the diff.
- `--bootstrap` — (re)generate `publication.json` from `papers.bib` and exit.

**`publication.json` schema.** One JSON object per paper, with these fields:

| field | required | notes |
|---|---|---|
| `key` | yes | DBLP key (with `DBLP:` prefix) or custom (e.g. `books/crc/MisraSC19`) |
| `type` | yes | `inproceedings` / `article` / `book` / `phdthesis` / etc. |
| `title` | yes | HTML and BibTeX braces preserved (e.g. `B<sup>+</sup>-tree`, `{TPCTC}`) |
| `authors` | yes | list of full-name strings; `Subhadeep Sarkar` is auto-emphasised by jekyll-scholar |
| `year` | yes | int |
| `venue_long` |   | renders as `booktitle` (inproceedings) or `journal` (article) |
| `venue_short` |   | becomes `abbr` → drives the badge text and color (`type` decides color) |
| `pages`, `volume`, `number`, `series`, `publisher`, `editor`, `isbn`, `issn`, `month` |   | optional bibliographic fields |
| `doi`, `url`, `abstract` |   | self-explanatory |
| `pdf` |   | filename (relative to `assets/fulltext/`) — drives the preview thumbnail |
| `arxiv`, `website`, `video`, `slides`, `poster`, `code_repo`, `purchase` |   | artifact links rendered as icons |
| `selected`, `bibtex_show` |   | display flags |
| `dblp_citation_verified` |   | `false` for new manual entries; flipped to `true` after DBLP sync |

**Prerequisites.** Python 3.8+, ImageMagick on `$PATH` for preview generation,
network access for DBLP fetches. No Python packages outside the standard
library are needed.

---

## Typical usage

```bash
# First-time setup — generate publication.json from current papers.bib:
./_populate_papers.py --bootstrap

# Routine: edit publication.json, then sync:
./_populate_papers.py              # interactive
./_populate_papers.py --dry-run    # see what would happen

# After adding a new publication PDF + bib entry (legacy script — populate
# papers handles previews automatically):
./generate_previews.sh

# After a Scholar refresh in Dropbox:
./fetch_citations.sh

# Then rebuild the site:
bundle exec jekyll build
```
