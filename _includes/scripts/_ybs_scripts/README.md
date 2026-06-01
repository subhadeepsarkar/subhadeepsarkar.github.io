# `_ybs_scripts/`

Helper scripts that keep this Jekyll site's auto-generated artifacts (citation counts, publication previews) in sync with their upstream sources. 
Run these manually before a `bundle exec jekyll build`/`serve` whenever the underlying data changes (new paper, new Scholar refresh, new local PDF).

---

## `_fetch_artifacts.py`

**Description.** Mirrors three artifact folders from `~/Dropbox/_control/` into `assets/`, treating `_control/` as ground truth. Called automatically at the start of `_populate_papers.py` — no need to run manually.

**Folder pairs:**

| Source | Destination |
| --- | --- |
| `~/Dropbox/_control/fulltext/` | `assets/fulltext/` |
| `~/Dropbox/_control/img/` | `assets/img/` |
| `~/Dropbox/_control/resources/` | `assets/resources/` |

**Behaviour.** New and updated files are copied; files present in `assets/` but absent in `_control/` are deleted. Runs silently — output only appears when files are copied or deleted.

**Prerequisites.** Dropbox is mounted and the three source folders exist.

---

## `_populate_papers.py`

**Description.** Source-of-truth bridge between a hand-curated `publication.json`
(at `~/Dropbox/_control/publication.json`) and the site's `_bibliography/papers.bib`. It diffs the two,
applies user-confirmed changes, fetches/verifies DBLP metadata for new or
unverified entries, generates missing PDF previews, and (optionally) refreshes
Scholar citations and rebuilds the site.

**Workflow.**

1. **Bootstrap (first run only).** If `~/Dropbox/_control/publication.json` is missing, the
   script reads every `@TYPE{key,...}` block from `papers.bib`, converts each
   into a JSON record, and writes the full set to `publication.json` sorted
   by year (descending). Pass `--bootstrap` to regenerate explicitly.
2. **Load both sides.** Reads `~/Dropbox/_control/publication.json` (the curated source of
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
   runs `magick -density 150 <pdf>[0] -resize 400x -quality 90 <out>.png`
   (first page, density 150, width 400px). The site's existing CSS overlay
   handles the colored venue badge ("banner") on top — no image-side
   annotation is burned into the PNG.
7. **Refresh citations (optional).** Asks `refresh Google Scholar citations
   now?` — on yes, runs `_fetch_citations.py`.
8. **Rebuild site (optional).** Asks `rebuild the site?` — on yes, runs
   `bundle exec jekyll build` from the repo root.

**Flags.**

- `--dry-run` — print every action but write nothing. Safe for inspection.
- `--yes` — auto-confirm every prompt. Use only when you trust the diff.
- `--bootstrap` — (re)generate `~/Dropbox/_control/publication.json` from `papers.bib` and exit.

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

## `service.json` + `_populate_service.py`

**Description.** `service.json` lives at `~/Dropbox/_control/service.json` and is the single source of truth for the
`/service/` page. `_populate_service.py` reads it and regenerates
`_pages/service.md` (preserving the YAML front matter) so Jekyll can
render the page. The user never edits `service.md` directly.

**`service.json` schema.** Top-level object with four arrays:

| array | description |
| --- | --- |
| `organization` | Roles held in conference/workshop organization |
| `pc_member` | Program committee memberships |
| `journal_reviewer` | Journals reviewed for (selected list) |
| `external_reviewer` | External reviewer credits, grouped by venue with a year list |

**Entry fields by array:**

*`organization`*

| field | required | notes |
| --- | --- | --- |
| `role` | yes | e.g. `"Proceedings Chair"` — rendered in `<i>` |
| `venue_long` | yes | Full venue name, plain text |
| `venue_short` | | Abbreviation. If it appears as a whole word in `venue_long` it is bolded inline; otherwise appended as `(<b>abbr</b>)` |
| `venue_html` | | Raw HTML override for the full venue string — use when the abbreviation sits mid-name alongside other bold terms |
| `track` | | Track or sub-series name; rendered as `<b>track</b>` after the venue |
| `year` | yes | Integer or string (e.g. `"2024-2026"` for multi-year spans) |

*`pc_member`*

| field | required | notes |
| --- | --- | --- |
| `venue_long` | yes | |
| `venue_short` | | Same inline-vs-appended logic as above |
| `venue_html` | | Raw HTML override |
| `track` | | e.g. `"Demo"`, `"Reproducibility"` — rendered `<b>track</b>` |
| `year` | yes | Integer |
| `note` | | Rendered as `({note})` after the year; accepts raw HTML for mixed-italic phrases like `"Track Co-Chair: <i>RF System...</i>"` |

*`journal_reviewer`*

| field | required | notes |
| --- | --- | --- |
| `venue_long` | yes | |
| `venue_short` | | |
| `venue_html` | | Raw HTML override |
| `publisher` | | e.g. `"Elsevier"` — appended as `, publisher` |

*`external_reviewer`*

| field | required | notes |
| --- | --- | --- |
| `venue_long` | yes | |
| `venue_short` | | |
| `venue_html` | | Raw HTML override |
| `years` | yes | Array of integers, rendered as `[2021, 2017]` |

**`venue_html` override.** Most venues render correctly via the automatic
logic. Use `venue_html` only for entries where the abbreviation appears
embedded in the name *and* additional terms must also be bolded, e.g.
`"ACM <b>MobiCom</b> workshop ... (<b>FICN</b>)"` or
`"North-East DataBase (<b>NEDB</b>) Day"`.

**Flags.**

- `--dry-run` — print the generated `service.md` to stdout without writing.

**Prerequisites.** Python 3.8+. No packages outside the standard library.

---

## Typical usage

```bash
# First-time setup — generate ~/Dropbox/_control/publication.json from current papers.bib:
./_populate_papers.py --bootstrap

# Routine: edit ~/Dropbox/_control/publication.json, then sync:
./_populate_papers.py              # interactive
./_populate_papers.py --dry-run    # see what would happen

# Routine: edit ~/Dropbox/_control/service.json, then regenerate service.md:
./_populate_service.py             # write _pages/service.md
./_populate_service.py --dry-run   # preview output without writing

# Refresh Scholar citation counts:
python3 ./_fetch_citations.py

# Then rebuild the site:
bundle exec jekyll build
```
