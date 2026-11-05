# `_ybs_scripts/`

Scripts that generate the site's publication list, service page, citation
counts and artifact files from hand-edited sources in `~/Dropbox/_control/`.

**`publication.json`** is the shared source of truth for recent papers (at most
3 years old, `WINDOW_YEARS`), read by this site and by the SSD Lab site
(`_populate_lab_papers.py`). Older papers live only in each site's
`_bibliography/papers.bib`; edit them there. Each record's `status` is `open`
(no verified DBLP entry yet) or `consolidated` (backed by one). Every paper
should be consolidated within 2 years of publication, and its record deleted
once it ages out after 3 years (the script lists those). The full workflow is in
`~/Dropbox/_control/README.md`.

**Rule of thumb:** edit the file in `~/Dropbox/_control/`, then run a script.
Never hand-edit `_pages/service.md`, `_data/citations.json`,
`assets/{fulltext,img,resources}/`, or `papers.bib` entries that have a record
in `publication.json` — they are overwritten. (Entries without a record are
edited by hand.)

## Tasks at a glance

| Task | Edit | Run |
| --- | --- | --- |
| Add / update a publication | `_control/publication.json` (+ PDF in `_control/fulltext/`) | `./_populate_papers.py` |
| Add / replace a PDF, image, slides, poster | `_control/{fulltext,img,resources}/` | `./_populate_papers.py` |
| Update the service page | `_control/service.json` | `./_populate_service.py` |
| Refresh Scholar citation counts | — | `python3 ./_fetch_citations.py` |
| Rebuild the site | — | `bundle exec jekyll build` (from repo root) |

All commands run from this directory. Add `--dry-run` to the two `_populate_*`
scripts to preview without writing anything.

## How to

### Add a new publication

1. Put the PDF in `~/Dropbox/_control/fulltext/` (slides/posters go in `_control/resources/`).
2. In `~/Dropbox/_control/publication.json`, copy the commented
   `_TEMPLATE_NEW_ENTRY` block at the top and fill in at least `key`, `type`,
   `title`, `authors`, `year`. Leave `dblp` empty; the paper starts `open`.
   - Once it is on DBLP, set `"dblp": "<dblp-key>"` (e.g. `conf/sigmod/SarkarPSA20`)
     and `"dblp_citation_verified": false`, then re-run: metadata is fetched and
     cross-checked, and the paper becomes `consolidated`. Keep the `key` unchanged.
   - dblp.org's `.bib` export is behind a bot check, so the script rebuilds
     the entry from DBLP's SPARQL endpoint (`sparql.dblp.org`) instead. If both
     fail, the run prints why and retries next time.
3. `./_populate_papers.py --dry-run` to preview, then `./_populate_papers.py`.
4. Answer the prompts (DBLP diff, add entry, PDF filename, citations refresh, rebuild).
5. Copy the new thumbnail from `assets/img/publication_preview/` into
   `~/Dropbox/_control/img/publication_preview/` (otherwise it is deleted and
   regenerated on every run — see [Gotchas](#gotchas)).
6. Commit `_bibliography/papers.bib`, `_pages/publications.md`, `assets/`, `_data/citations.json`.

New papers are always marked `selected` (featured). To un-feature one, set
`"selected": false` afterwards and re-run.

### Edit an existing publication

1. Change the record in `~/Dropbox/_control/publication.json`. For a
   `consolidated` paper, change only links and `selected`. (Papers with no record:
   edit `_bibliography/papers.bib` directly instead.)
2. `./_populate_papers.py` — review the field-by-field diff and confirm.
3. Commit.

### Add or replace files (PDFs, images, slides, posters)

1. Drop the file into `~/Dropbox/_control/{fulltext,img,resources}/`.
2. `./_populate_papers.py` — the first step mirrors these folders into `assets/`.
   Deleting a file from `_control/` deletes it from `assets/` too.

### Update the service page

1. Edit `~/Dropbox/_control/service.json` (schema [below](#servicejson-schema)).
2. `./_populate_service.py --dry-run` to preview, then `./_populate_service.py`.
3. Commit `_pages/service.md`.

### Refresh citation counts

1. `python3 ./_fetch_citations.py` (also offered at the end of `_populate_papers.py`).
2. Commit `_data/citations.json`.

If Scholar serves a CAPTCHA the script exits non-zero and leaves the JSON untouched — retry later or from another network.

---

# Reference

## Files and locations

| Source (hand-edited) | Generated (in repo) | Script |
| --- | --- | --- |
| `~/Dropbox/_control/publication.json` | `_bibliography/papers.bib`, `years:` in `_pages/publications.md` | `_populate_papers.py` |
| `~/Dropbox/_control/fulltext/` | `assets/fulltext/` | `_fetch_artifacts.py` |
| `~/Dropbox/_control/img/` | `assets/img/` | `_fetch_artifacts.py` |
| `~/Dropbox/_control/resources/` | `assets/resources/` | `_fetch_artifacts.py` |
| PDFs in `assets/fulltext/` | `assets/img/publication_preview/<pdf-stem>.png` | `_populate_papers.py` |
| `~/Dropbox/_control/service.json` | `_pages/service.md` (body only) | `_populate_service.py` |
| Google Scholar profile | `_data/citations.json` | `_fetch_citations.py` |

**Prerequisites:** Python 3.8+ (standard library only), Dropbox mounted,
ImageMagick 7 (`magick` on `$PATH`) for previews, network access for DBLP /
Scholar, Bundler + Jekyll for rebuilds.

## `_populate_papers.py`

### What a run does

0. **Sync artifacts** — runs `_fetch_artifacts.py` (skipped under `--dry-run`).
1. **Bootstrap** — only if `publication.json` is missing (or `--bootstrap`):
   builds it from the `papers.bib` entries at most 3 years old, sorted by year
   desc then key.
2. **Load** — reads `publication.json` (JSON with `//` and `/* */` comments
   allowed) and `papers.bib`. Skips records whose key starts with `_` or that
   have `"placeholder": true`.
3. **Existing entries** — for each key already in `papers.bib`, diffs every
   tracked field and, on confirmation, **re-renders the bib entry entirely from
   the JSON**. Only DBLP's `timestamp`, `biburl`, `bibsource` are carried over
   from the old bib entry; anything else edited only in `papers.bib` is lost.
4. **DBLP re-check** — for existing records with a DBLP key (the `dblp` field,
   or the key minus a `DBLP:` prefix) and `dblp_citation_verified: false`:
   - paper is ≤ 3 years old → fetch `https://dblp.org/rec/<dblp-key>.bib`, show
     diff, on confirmation adopt DBLP's
     `title, authors, year, venue_long, pages, volume, number, publisher, doi, url`
     and set the flag `true`. Older papers are skipped.
   - Records with no DBLP key are never looked up; their flag is kept `false`.
5. **New entries** — for each key not in `papers.bib`: prints the record,
   checks DBLP (same rules as above), asks to add it, resolves the PDF (if
   `pdf` is empty it looks for `<title>.pdf` in `assets/fulltext/` — spaces
   → `_`, colons/HTML/braces stripped — or asks for a filename), forces
   `selected: true`, and inserts the entry **at the top** of `papers.bib`.
6. **Status + persist** — sets each record's `status` (`consolidated` = DBLP
   key and verified flag, else `open`), writes `papers.bib` and
   `publication.json` if changed, then lists open papers and flags any older
   than 2 years. Rewriting `publication.json` keeps every record (including
   ignored ones) and drops all comments except the header and template block,
   which are re-added at the top.
7. **Years** — adds any missing year to the `years: [...]` front matter of `_pages/publications.md`.
8. **Previews** — for every record whose local PDF has no thumbnail:
   `magick -density 150 <pdf>[0] -resize 400x -quality 90 <stem>.png`.
   The venue badge is a CSS overlay, not burned into the image.
9. **Citations?** / **Rebuild?** — two prompts (default No); skipped under `--yes` and `--dry-run`.

### Flags

| Flag | Effect |
| --- | --- |
| `--dry-run` | Print planned actions; write nothing (artifact sync skipped too). |
| `--yes` | Auto-accept every diff/add prompt; skips (answers No to) citations refresh and rebuild. |
| `--bootstrap` | Regenerate `publication.json` from the `papers.bib` entries at most 3 years old (overwrites), then exit. |

### `publication.json` schema

One object per paper. Empty strings/lists are treated as absent.

| Field | Req. | Notes |
| --- | --- | --- |
| `key` | ✓ | `DBLP:<dblp-key>` or a custom key. Keys starting with `_` are ignored. Never change it. |
| `status` | | Set by the script: `open` or `consolidated`. Don't edit. |
| `dblp` | | DBLP key (e.g. `conf/sigmod/SarkarPSA20`) for a record whose `key` isn't `DBLP:…`. Set once the paper is on DBLP. |
| `type` | ✓ | `inproceedings`, `article`, `book`, `incollection`, `phdthesis`, `mastersthesis`, `techreport`, `misc`, `patent` (→ `@misc`) |
| `title` | ✓ | HTML and BibTeX braces preserved (e.g. `B<sup>+</sup>-tree`, `{TPCTC}`) |
| `authors` | ✓ | List of full names. Site owner is bolded via `scholar.first_name/last_name` in `_config.yml`. |
| `year` | ✓ | Integer |
| `venue_long` | | → `booktitle` (inproceedings, incollection, other types) or `journal` (article); ignored for books and theses |
| `venue_short` | | → `abbr`: badge text. Badge color comes from `_data/venues.yml`, else by type (article red, book blue, other green). |
| `school` | | For theses |
| `editor` | | List of names |
| `month`, `pages`, `volume`, `number`, `series`, `publisher`, `isbn`, `issn`, `howpublished`, `note`, `doi`, `url`, `abstract` | | Standard bibliographic fields |
| `pdf` | | Filename in `assets/fulltext/`, or a full URL. A local PDF drives the preview thumbnail. |
| `preview` | | Explicit thumbnail (filename in `assets/img/publication_preview/` or URL); used only when there is no `pdf` |
| `slides`, `poster` | | Filename in `assets/resources/`, or a full URL |
| `arxiv` | | arXiv ID (e.g. `2006.04777`) |
| `website`, `video`, `code_repo`, `purchase` | | URLs, rendered as icons |
| `selected` | | Featured on the home page. Forced `true` for new entries. |
| `bibtex_show` | | Show the BibTeX toggle |
| `dblp_citation_verified` | | `false` = verify against DBLP on the next run(s); `true` once done. Forced `false` when there is no DBLP key. |
| `placeholder` | | `true` = ignore this record |

## `_fetch_artifacts.py`

Mirrors `~/Dropbox/_control/{fulltext,img,resources}/` into
`assets/{fulltext,img,resources}/`: copies new/changed files and **deletes**
anything in `assets/` that is not in `_control/`. Prints a per-folder summary
when something changed, otherwise `artifacts: already up to date`; warns and
skips a missing source folder. Normally run by `_populate_papers.py`; can be
run standalone with `python3 ./_fetch_artifacts.py`.

## `_populate_service.py`

Regenerates the body of `_pages/service.md` from `service.json`, keeping the
existing YAML front matter, then asks whether to rebuild the site.
`--dry-run` prints the generated page instead of writing it.

### `service.json` schema

Top-level object with four arrays, rendered as sections in this order (empty
or missing arrays are omitted):

| Array | Section | Entry fields | Rendered as |
| --- | --- | --- | --- |
| `organization` | organization | `role`✓, `venue_long`✓, `venue_short`, `venue_html`, `track`, `year`✓ | `<i>role</i>, venue <b>track</b>, year` |
| `pc_member` | program committee member | `venue_long`✓, `venue_short`, `venue_html`, `track`, `year`✓, `note` | `venue <b>track</b>, year (note)` |
| `journal_reviewer` | journal reviewer (selected) | `venue_long`✓, `venue_short`, `venue_html`, `publisher` | `venue, publisher` |
| `external_reviewer` | external reviewer -- conferences (selected) | `venue_long`✓, `venue_short`, `venue_html`, `years`✓ (list) | `venue [2021, 2017]` |

`year` may be an integer or a string (e.g. `"2024-2026"`). `note` may contain HTML.

**Venue formatting:** if `venue_html` is set it is used verbatim. Otherwise,
if `venue_short` appears as a whole word in `venue_long` it is bolded in place;
if not, ` (<b>venue_short</b>)` is appended. Use `venue_html` only when extra
terms must also be bolded, e.g. `"North-East DataBase (<b>NEDB</b>) Day"`.

## `_fetch_citations.py`

Scrapes the Google Scholar profile (`SCHOLAR_USER_ID` in the script) and
writes `_data/citations.json` with `profile` (`name`, `affiliation`,
`citedby`, `hindex`, `i10index`) and `publications` (`title`, `authors`,
`year`, `venue`, `cited_by`, `url`, …), consumed by `_layouts/bib.html`.
Aborts without writing on a CAPTCHA / block.

## Gotchas

- **Previews live in `assets/img/`, which is mirrored from `_control/img/`.**
  A freshly generated thumbnail that is not copied back to
  `~/Dropbox/_control/img/publication_preview/` is deleted by the next sync
  and regenerated later in the same run — harmless churn, but copy it back.
- **Don't edit `papers.bib` entries that have a JSON record** — the next sync of that entry overwrites it from the JSON. Entries without a record (older papers, including ones whose record was removed after 3 years) are edited only in `papers.bib`.
- **Comments in `publication.json` are lost** whenever the script rewrites the file (only the header and template block are kept).
- **`HEADER_LINES` and `TEMPLATE_RECORD` must stay identical** in this script and the lab site's `_populate_lab_papers.py`; both rewrite the same file.
- **`--yes`** accepts every DBLP and diff prompt; use only when you trust the changes.
