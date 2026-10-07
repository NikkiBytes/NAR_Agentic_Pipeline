# HervD Atlas — Design Rationale

## Quick Stats

| Metric | Value |
|---|---|
| Source rows (herv_term.json) | 21,049 |
| Source rows (herv_element.json) | 741 |
| Documents yielded | **21,790** (21,049 `herv_term` + 741 `herv_element`) |
| Rows skipped | 0 |
| Deduplication | 0 collisions (HervID namespaces for terms `chr#_ERV#_#####` and elements `ERV#_####` never overlap; `seen_ids` guard in `load_data()` is a safety net, not exercised) |
| Total disease links embedded | 58,731 (56,987 from terms + 1,744 from elements) |
| Target API | `pending.api` |
| Data format | Disease Information.txt = TSV (35 KB); herv_term.json / herv_element.json = bulk JSON via single-call POST (6.0 MB / 0.21 MB) |
| Total file size | ~6.3 MB |

## Why These Dump Files Were Chosen

HervD Atlas's canonical "Download" page (`https://ngdc.cncb.ac.cn/hervd/download`) offers only 4 static files: `HERV-Terms Information.txt`, `HERV-Elements Information.txt`, `Disease Information.txt`, `Publication Information.txt`. These are entity-metadata-only — **none of them contain the HERV-disease association linkage**, which is the entire premise of the paper ("a curated knowledgebase of **associations** between human endogenous retroviruses and diseases").

The association linkage was found by inspecting the site's own DataTables-driven browse pages (`/hervd/herv`), which load their data from two backend JSON endpoints discovered in the page's own JS (`static/js/my/herv.js`):
- `POST https://ngdc.cncb.ac.cn/hervd/herv_term` → all 21,049 HERV-Term rows in one call, each with an aggregated, denormalized `Associated_disease` field (comma-joined disease names)
- `POST https://ngdc.cncb.ac.cn/hervd/herv_element` → all 741 HERV-Element rows, same pattern

Both were verified to return `application/json` (not `text/html`), require no auth, accept no query parameters, and return the **complete table** in a single call (confirmed by comparing row counts to the paper's stated totals: 21,049 + 741 = 21,790, matching exactly). Functionally these are single-shot bulk dumps, just served over POST instead of GET — this is why the plugin uses a custom `dumper.py` (see manifest-schema.md's documented "API-only source — custom dumper.py" pattern) rather than the standard GET-only `data_url` mechanism, while still declaring the underlying URLs in `manifest.json`'s `dumper.data_url` for documentation purposes.

`Disease Information.txt` (149 rows, plain GET, tab-delimited) was kept and used as a lookup table to resolve each disease *name* referenced in `Associated_disease` into structured ontology cross-references (EFO/DOID/NCI/OMIM/MESH/Others) plus category and free-text description. All 55 (term-level) and 126 (element-level) unique disease names referenced in the JSON endpoints were confirmed to match `Disease Information.txt` exactly — 0 unresolved names.

`HERV-Terms Information.txt` / `HERV-Elements Information.txt` were **not** used directly — `herv_term.json` / `herv_element.json` already contain every field present in those TXT files (position, strand, length, region, type, group / description, alias, reported name) *plus* the association linkage, so parsing the TXT files would have been redundant.

`Publication Information.txt` (254 rows, PMID/DOI/title/year/journal) was **not** ingested. It has no join key back to individual HERV-disease pairs at the granularity exposed by the bulk endpoints — see "Known Data Gap" below.

## Known Data Gap — Per-Association Evidence Not Bulk-Fetchable

Inspecting a HERV detail page (`/hervd/herv/term/{HervID}`) revealed a **third**, richer endpoint: `POST /hervd/herv/term/association` with `id=<HervID>` in the POST body, which returns full per-association evidence records (`association_id`, `Study_ID`, `PMID`, `DOI`, `Journal`, `Association_level`, `Trend`, `log2FC`, `Method`, `Sample_source`, `Related_gene`, `Pvalue`, etc.) — this is what the paper's headline **60,726 curated associations** figure is built from.

This endpoint is scoped **per HERV ID**, not a bulk table — retrieving the full evidence set would require ~21,790 sequential POST calls (one per HERV-Term/Element). This is a genuine API-crawl scenario, not a single bulk fetch, and was **not** performed in this ingestion pass (would take hours and constitutes a materially different ingestion strategy than the "single-call bulk JSON" approach used here). The 58,731 disease-links captured via `herv_term`/`herv_element` are the *entity-level, evidence-collapsed* view of the same association data — every HERV-disease pair is present, but without per-record PMID/DOI/trend/log2FC attribution. This is flagged in `hervd_inspection.json`'s `paper_vs_reality` and `risks`, and should be revisited as a follow-up crawl if per-association evidence becomes a priority.

## Why the Parser Works the Way It Does

- **`_id` strategy**: `HervID` (terms, e.g. `chr10_ERV1_00043`) / `HERVID` (elements, e.g. `ERV1_0001`). Verified no collisions between the two ID namespaces across all 21,790 rows.
- **Document structure**: one document per HERV entity, nested under a top-level `hervd` key. `entity_type` (`herv_term` / `herv_elements`) distinguishes the two source tables since they share one `_id` space and one uploader.
- **Association embedding**: each HERV document embeds an `associated_diseases` list, where each entry is the disease resolved via the `Disease Information.txt` lookup (name, category, description, `xrefs`). `disease_count` mirrors the source's own `Number_of_associated_disease` field (kept as a derived `len()` of the resolved list rather than trusted verbatim, since the raw field is a string in the source JSON).
- **Data cleaning**: `dict_sweep(unlist(doc), [None, "", "-"])` — the source uses the literal string `"-"` for "no value" (seen in `Alias`, ontology xref columns), so `"-"` is swept alongside `None`/`""`. `unlist()` collapses single-item lists (e.g. a HERV with exactly one associated disease yields a scalar object under `associated_diseases` rather than a one-item list) — this is expected BioThings SDK behavior and is accounted for in the mapping (Elasticsearch has no distinct array type, so `properties` under `associated_diseases` applies whether it holds one object or many).
- **Deduplication**: a `seen_ids` set spans both the term and element loops in `load_data()` as a defensive backstop; in practice the two ID namespaces never collide (confirmed on the full dataset), so `on_duplicates: "error"` is safe.

## Sample Output Documents

**Typical HERV-Term** (`_id`: `chr10_ERV1_00043`) — source cross-reference: https://ngdc.cncb.ac.cn/hervd/herv/term/chr10_ERV1_00043
```json
{
  "_id": "chr10_ERV1_00043",
  "hervd": {
    "herv_id": "chr10_ERV1_00043",
    "herv_name": "HERVH-int",
    "entity_type": "herv_term",
    "position": "chr10:100383553-100385005",
    "chromosome": "chr10",
    "strand": "+",
    "length": 1453,
    "region_type": "Intronic",
    "type": "ERV1",
    "group": "HERVHF",
    "disease_count": 12,
    "associated_diseases": [
      {
        "name": "Breast Cancer",
        "category": "Cancer",
        "description": "A thoracic cancer that originates in the mammary gland.",
        "xrefs": {"doid": "DOID:1612", "nci": "NCI:C9335", "omim": "OMIM:114480"}
      }
    ]
  }
}
```
(full document has 12 entries in `associated_diseases`; truncated here for readability — see `hervd_plugin/parser.py` output for the complete record)

**Edge case — HERV-Element with rich name aliasing and a partially-unmapped disease** (`_id`: `ERV1_0001`) — source cross-reference: https://ngdc.cncb.ac.cn/hervd/herv/element/ERV1_0001
```json
{
  "_id": "ERV1_0001",
  "hervd": {
    "herv_id": "ERV1_0001",
    "herv_name": "ERVW-1",
    "entity_type": "herv_element",
    "description": "Endogenous retrovirus group W member 1, envelope",
    "alias": ["ENV", "ENVW", "ERVWE1", "HERV-7q", "HERV-W-ENV", "HERV7Q", "HERVW", "HERVWENV", "Syncytin-1", "Syncytin"],
    "reported_name": ["Syncytin", "HERV-W-env", "ERVW-1", "ERVW-1-env", "ERVWE1", "ERVWE1 env", "Syncytin-1"],
    "type": "ERV1",
    "group": "HERVW9",
    "disease_count": 32,
    "associated_diseases": [
      {"name": "Influenza A/WSN/33 Virus Infection", "category": "Viral infectious disease"},
      {"name": "Neuropsychological Disease", "category": "Nervous system disease"}
    ]
  }
}
```
(this entity has 32 associated diseases; 2 shown above — note `"Influenza A/WSN/33 Virus Infection"` and `"Neuropsychological Disease"` resolve to only `name`/`category` in `Disease Information.txt` since that row has `-` for every ontology column — an intentional "no xref" outcome, not a parser bug)

## Field Coverage

(from full-dataset run against all 21,790 documents, since the entire source is small enough to process without sampling)

- `position` / `chromosome` / `length`: 96.6% (herv_term only; herv_element rows don't carry genomic coordinates)
- `region_type`: 96.3%
- `group`: 88.7%
- `strand`: 47.9% (many HERV-Term rows have unresolved/ambiguous strand)
- `description`: 3.3% (herv_element only)
- `reported_name`: 3.4% (herv_element only)
- `alias`: 0.3% (herv_element only; most elements have no alias, e.g. `"-"` swept)

Disease-link ontology cross-reference coverage (of 58,731 total disease links):
- `xrefs.doid`: 84.2%
- `xrefs.nci`: 84.0%
- `xrefs.mesh`: 48.1%
- `xrefs.efo`: 42.6%
- `xrefs.omim`: 30.3%
- `xrefs.other` (HPO/SNOMED): 0.1%
- no xref at all (category/description only): 0.1% (57 links)

## Test Results Summary

`biothings-cli` is broken in this sandbox — every subcommand raises `AttributeError: module 'typer' has no attribute 'rich_utils'` at import time (typer 0.26.7 / biothings 1.0.2 incompatibility, the same known issue logged for ~15 other plugins in `built-plugins-index.md`, e.g. chemprob, molbic, geneasso). Per instructions, the shared environment was **not** patched. Validation was instead performed directly:

1. **Download verification**: all 3 source URLs (`Disease Information.txt` via GET, `herv_term`/`herv_element` via POST) fetched live with `curl -A "Mozilla/5.0"`, confirmed `HTTP 200` and non-HTML content-type (`text/plain` and `application/json` respectively).
2. **Parser execution**: `parser.load_data()` run directly against the live-downloaded files placed in a scratch `data_folder`. Yielded **21,790 documents**, 0 exceptions, 0 silent-zero-doc failures.
3. **`_id` integrity**: 21,790 unique `_id` values (no collisions), max length 39 chars (well under the 512-char BioThings limit).
4. **Field coverage**: computed across the full 21,790-document set (see above) — no sampling needed given the dataset's small size.
5. **Disease resolution audit**: of 58,731 total disease links embedded across all documents, 0 referenced a disease name absent from `Disease Information.txt` (100% name-level resolution); 57 links (0.1%) resolved to a disease with no ontology xref code at all (category/description-only rows in the source, e.g. `"Others"`-category HPO-coded diseases).
6. **Mapping validation** (replacing `inspect --mode mapping`): a standalone script recursively walked all 21,790 documents, recorded the observed Python type at every field path (23 distinct paths), and diffed against `mapping.py`'s flattened `properties`. Result: **0 missing fields, 0 unused mapping entries, 0 type mismatches.**

## Mapping Overview

Top-level `hervd` object fields and their Elasticsearch types (see `mapping.py`):

| Field | ES type |
|---|---|
| `herv_id`, `herv_name`, `entity_type`, `position`, `chromosome`, `strand`, `region_type`, `type`, `group`, `alias`, `reported_name` | `keyword` |
| `length`, `disease_count` | `integer` |
| `description` (top-level and nested under `associated_diseases`) | `text` + `.raw` keyword subfield |
| `associated_diseases` | `object` (`properties`: `name` keyword, `category` keyword, `description` text+raw, `xrefs` nested object) |
| `associated_diseases.xrefs.{efo,doid,nci,omim,mesh,other}` | `keyword` |

**Mapping Conflicts**: none. All 23 observed field paths across the combined `herv_term` + `herv_element` document set had a single, consistent Python type (no field was observed as sometimes-string/sometimes-number or sometimes-scalar/sometimes-object). `description` fields (both the top-level HERV-Element description and the per-disease description) were deliberately mapped as `text` with a `.raw` keyword subfield rather than plain `keyword`, since they are free-text prose (avg. ~150 chars, max 826 chars) suited to full-text search, per the plugin-generator skill's guidance on `text` vs `keyword`.

## Notes / Risks Carried to `README.md`

- License: the NAR article's text is licensed CC BY-NC (per PMC), but the HervD Atlas *site* — via its shared NGDC/BIG Data Center footer template (`static/js/outsource/headerfooter-full.js`) — states **CC BY 3.0 China Mainland** (`http://creativecommons.org/licenses/by/3.0/cn/`) with no NC restriction for the database content itself. `manifest.json` uses the site's stated data license since it's the license governing redistribution of the downloaded data, not the article text.
- Filenames on `download.cncb.ac.cn` contain literal spaces requiring percent-encoding (`%20`) in URLs.
- The two POST JSON endpoints require a custom `dumper.py` (standard `HTTPDumper.download()` only issues GET); see that file's docstring for the rationale and implementation.
