# Design Rationale — TarBase v9.0 Plugin

## Quick Stats
| Metric | Value |
|---|---|
| Source rows (CSV, incl. header) | 1,847,089 (1,847,088 data rows) |
| Documents yielded | 1,839,985 |
| Rows skipped | 0 (no rows had a missing `gene_id`/`mirna_id` in this export) |
| Duplicate (gene_id, mirna_id) pairs deduplicated | 7,103 (first-occurrence kept, matching the source file's descending-by-`experiments` sort order) |
| Target API | pending.api |
| Data format | Single CSV blob (POST response), ~115 MB, 8 columns |
| `_id` format | Composite `f"{gene_id}_{mirna_id}"`, e.g. `ENSG00000100697_MIMAT0000062` |
| `_id` collisions | 0 across 1,839,985 documents |

## Why This Dump File Was Chosen
TarBase v9.0's live site (`https://dianalab.e-ce.uth.gr/tarbasev9`) is a JS-rendered React SPA with no static bulk-download page. The paper's Data Availability statement describes only "boundless local retrieval" through the web interface, with no published file URL. Per the plugin generator's Step 1b-gate URL-verification workflow:

1. The static download-page probe (steps 1a) found nothing — the SPA has no `/download`, `/data`, `/bulk`, etc. static routes serving files.
2. Reading the compiled JS bundle (`https://dianalab.e-ce.uth.gr/tarbasev9/static/js/main.c6e27c3d.js`) surfaced the internal `get_all_interactions/` API route used by the site's own "download all" button, which accepts a POST with an empty JSON filter body (`{}`) and returns the entire unfiltered aggregated miRNA-gene-pair table in one response — no pagination, no auth.
3. This qualifies as **Type A — static files behind a JS UI** in spirit (a single-call, non-paginated full-table dump served by the canonical domain itself, not a query-scoped API and not a third-party mirror), so it was used directly rather than escalating to a mirror. Because the endpoint requires POST rather than GET, a custom `dumper.py` (subclassing `HTTPDumper`, overriding `download()` — same pattern as the existing `hervd` plugin) was written to issue the POST and save the response body as `tarbase_all_interactions.csv`.

**Rejected alternative**: per-pair drill-down endpoints (`get_interactions/`, `get_interaction_site/`) expose richer per-experiment metadata (individual tissue/cell-type, experimental method, sample, PMID, genomic coordinates of the binding site) that the paper describes as part of its ~6 million total-entries figure. Crawling per-pair detail for ~1.84M pairs individually is not practical at bulk-ingestion scale, so the pair-level aggregate (`experiments`/`publications`/`cell_lines` counts + `micro_tscore`) is used instead. This is flagged as a data-completeness limitation, not a blocker — the aggregate still captures the core miRNA-to-gene targeting relation and its evidence weight.

## Why the Parser Works the Way It Does
- **`_id` strategy**: composite `f"{gene_id}_{mirna_id}"` (Ensembl Gene ID + miRBase MIMAT accession). Neither ID alone is unique per row (a gene can be targeted by many miRNAs and vice versa); the composite pair key is the natural unique identifier for this data model and matches the `pending.api` convention of composite IDs for association-type sources.
- **Document structure**: all TarBase-specific fields are nested under a single `tarbase` sub-object, per the plugin generator's field-nesting convention. No cross-references beyond the identifiers themselves are added (gene/miRNA metadata is joinable downstream via `gene_id` → MyGene.info and `mirna_id` → miRBase).
- **Deduplication**: 7,103 of 1,847,088 raw rows share a duplicate `(gene_id, mirna_id)` composite key — different `gene_name` synonyms mapping to the same Ensembl gene ID observed in the raw export. The parser keeps the first occurrence encountered per key, which (given the source file's existing descending-`experiments` sort order) retains the best-evidenced synonym row for each pair. A `seen_ids` set guards this in a single streaming pass — no need to buffer the full 1.84M-row table in memory.
- **Fields extracted**: all 8 source columns are retained (`gene_name`, `gene_id`, `mirna_name`, `mirna_id`, `experiments`, `publications`, `cell_lines`, `micro_tscore`) — every column is meaningful evidence-strength or identifier information, none are dropped.
- **Data cleaning**: `experiments`/`publications`/`cell_lines` are coerced to `int`, `micro_tscore` to `float`, with `None` returned on any conversion failure or empty string; `dict_sweep(unlist(doc), [None])` strips any resulting `None` values before yielding, per SDK convention.
- **Rows skipped**: a row is skipped only if it lacks a usable `gene_id` or `mirna_id` after stripping whitespace. In this export, 0 of 1,847,088 rows met that skip condition — all rows had both IDs present.

## Sample Output Documents
Typical document (top-scoring, well-evidenced pair):
```json
{
  "_id": "ENSG00000100697_MIMAT0000062",
  "tarbase": {
    "gene_name": "DICER1",
    "gene_id": "ENSG00000100697",
    "mirna_name": "hsa-let-7a-5p",
    "mirna_id": "MIMAT0000062",
    "experiments": 63,
    "publications": 34,
    "cell_lines": 33,
    "micro_tscore": 0.84
  }
}
```
Source cross-reference: search `DICER1` / `hsa-let-7a-5p` on the TarBase v9.0 web interface at https://dianalab.e-ce.uth.gr/tarbasev9 (per-pair permalinks are not exposed by the SPA; the site only supports interactive gene/miRNA search, not stable per-record URLs).

Second example (different evidence profile):
```json
{
  "_id": "ENSG00000108256_MIMAT0000069",
  "tarbase": {
    "gene_name": "NUFIP2",
    "gene_id": "ENSG00000108256",
    "mirna_name": "hsa-miR-16-5p",
    "mirna_id": "MIMAT0000069",
    "experiments": 61,
    "publications": 31,
    "cell_lines": 33,
    "micro_tscore": 0.62
  }
}
```

## Field Coverage
Computed over the full 1,839,985-document set (not a sample — the entire live-downloaded export was parsed):
- `tarbase.gene_id`: 100%
- `tarbase.mirna_id`: 100%
- `tarbase.mirna_name`: 100%
- `tarbase.experiments`: 100%
- `tarbase.publications`: 100%
- `tarbase.cell_lines`: 100%
- `tarbase.micro_tscore`: 100%
- `tarbase.gene_name`: 99.9998% (4 of 1,839,985 documents have no usable `gene_name` value in the source row; `gene_id` is present for all of them, so the document remains fully identifiable)

## Test Results Summary
`biothings-cli` is broken in this sandbox (see Notes in `built-plugins-index.md` — every subcommand raises `AttributeError: module 'typer' has no attribute 'rich_utils'`, a known typer 0.26.7 / biothings 1.0.2 incompatibility already logged for ~15 other plugins in this project). It was not patched, since it is a shared environment. Validation was performed instead via direct execution:

1. **Data acquisition**: `curl -A "Mozilla/5.0" -X POST https://dianalab.e-ce.uth.gr/tarbasev9/api/get_all_interactions/ -d '{}'` downloaded the full live CSV (115,370,851 bytes, 1,847,088 data rows) into `scratch_data/tarbase_all_interactions.csv`, matching the row count independently observed during Stage 1 site inspection.
2. **Parser execution**: `parser.load_data("scratch_data")` was invoked directly in a standalone Python script (no biothings-cli `dump`/`upload` wrapper). It streamed the full 115 MB file in ~20 seconds and yielded **1,839,985 documents** with **0 duplicate `_id`s** — exactly matching the 1,839,985 unique-pairs figure independently derived during Stage 1 inspection (1,847,088 raw rows − 7,103 duplicate pairs).
3. **Field coverage**: computed over all 1,839,985 yielded documents (full set, not a `--limit 1000` sample) — see Field Coverage above.
4. **`_id` format check**: all `_id` values matched the expected `{gene_id}_{mirna_id}` composite pattern; max length 31 characters (well under the 512-char limit); 0 collisions.
5. **`dict_sweep`/`unlist` cleanliness**: spot-checked yielded documents — no `None`/empty-string values present, no nested list-of-list structures (all fields are flat scalars under the `tarbase` sub-object).

## Mapping Overview
`mapping.py` defines `get_customized_mapping(cls)` returning a single `tarbase` object with 8 leaf properties, all mapped directly from the flat document structure (no nested sub-objects in this data model):

| Field | ES type | Rationale |
|---|---|---|
| `gene_name` | `keyword` | Short categorical gene symbol string, exact-match/filter use, not full-text search |
| `gene_id` | `keyword` | Ensembl Gene ID, exact-match identifier |
| `mirna_name` | `keyword` | miRBase mature-miRNA name string, exact-match/filter use |
| `mirna_id` | `keyword` | MIMAT accession, exact-match identifier |
| `experiments` | `integer` | Small positive count (observed range fits well within 32-bit) |
| `publications` | `integer` | Small positive count |
| `cell_lines` | `integer` | Small positive count |
| `micro_tscore` | `float` | Continuous prediction score in [-1, 1] |

**Mapping Conflicts**: none. All 8 fields showed exactly one consistent Python type across the full 1,839,985-document set (no heterogeneous or incompatible field types encountered).

`uploader.mapping: "mapping:get_customized_mapping"` is wired into `manifest.json`.

**Validation**: `inspect --mode mapping` could not run (biothings-cli typer/rich_utils blocker, see above). Validated instead via a standalone script that ran `parser.load_data()` against the full 1,839,985-document live-downloaded set, recursively walked every yielded document recording the observed Python type at each field path (mapped through `str→keyword`, `int→integer`, `float→float`), and diffed those paths against `mapping.py`'s flattened `properties`:
- **Missing fields** (in `mapping.py`, absent from documents): 0
- **Extra fields** (in documents, absent from `mapping.py`): 0
- **Type mismatches**: 0

Result: **PASS** — full agreement between `mapping.py` and the actual post-parser document shape across the entire dataset (no sampling).
