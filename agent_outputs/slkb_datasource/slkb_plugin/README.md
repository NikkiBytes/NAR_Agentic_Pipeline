# SLKB (Synthetic Lethality Knowledge Base) — Design Rationale

## Quick Stats

| Metric | Value |
|---|---|
| Source rows (`cdko_original_sl_results`) | 280,483 |
| Documents yielded | 280,483 |
| Rows skipped | 0 |
| Deduplication count | 0 (composite key is unique by construction; `seen_ids` guard never triggers on real data) |
| Target API | `pending.api` |
| Data format | ZIP containing a self-contained sqlite3 SQL dump (schema + `INSERT` + views); ~229.7 MB compressed / ~913 MB uncompressed (both mysql and sqlite3 dumps + schema files; only `SLKB-sqlite3_dump.sql`, ~943 MB uncompressed, is used by the parser) |

## Why These Dump Files Were Chosen

SLKB is hosted as an R Shiny web application (`https://slkb.osubmi.org`) whose "Download" tab exposes only ad hoc, query-scoped CSV exports of whatever table/filter the user has currently selected in the UI — there is no stable, directly-curlable bulk file on the datasource's own domain (Type B: dynamically generated download links, per the plugin generator skill's JS-rendered-download-page decision tree).

The paper's Data Availability statement explicitly names a permanent, versioned Figshare deposit as the canonical full-database export: `https://doi.org/10.6084/m9.figshare.22902839` (DOI resolves to Figshare article 22902839, "SLKB - Deposited Data"). This is the Type B case described in the skill: the authors publish the archive as the release mechanism, so it is the correct `data_url`, not a lazy third-party fallback. Confirmed via the Figshare API (`https://api.figshare.com/v2/articles/22902839`): `is_public: true`, `download_disabled: false`, license `GPL 3.0+`, single file `SQL_Dumps.zip` (240,825,452 bytes) plus a `README.md` describing its contents.

`SQL_Dumps.zip` contains:
- `SQL_Dumps/SLKB-sqlite3_dump.sql` (943 MB uncompressed) — **used**. A complete, self-contained sqlite3 dump: `CREATE TABLE` + `INSERT INTO` statements for all 10 base tables plus the 2 `CREATE VIEW` definitions (`joined_counts`, `calculated_sl_table`) that the live Shiny app itself uses to present joined data.
- `SQL_Dumps/SLKB-mysql_dump.sql` (716 MB uncompressed) — **not used**. Same data as the sqlite3 dump but in mysqldump format requiring a running MySQL server to load; sqlite3 is stdlib in Python and loads the same content with `sqlite3.connect(":memory:").executescript()`.
- `SQL_Dumps/schemas/*.sql` — **not used** directly (schema is already embedded in both full dumps).

Both dump files are supersets of each other (same data, different SQL dialect); the sqlite3 dump was selected as the single file the parser reads, since it needs no external database engine.

## Why the Parser Works the Way It Does

**Loading strategy**: The zip is downloaded and unzipped by the Hub (`uncompress: true`), landing the whole `SQL_Dumps/` tree in `data_folder`. The parser globs for `SLKB-sqlite3_dump.sql` anywhere under `data_folder` (tolerant of the exact folder depth the Hub produces), loads it into an **in-memory** sqlite3 database via `executescript()` (~33s for the full ~4.1M total rows across all 10 tables), and queries it with a single SQL `JOIN` — rather than parsing the SQL text with regex or shelling out to `sqlite3`.

**Table selection**: SLKB's relational schema (`SQL_Dumps/schemas/SLKB_sqlite3_schema.sql`) has two tiers of tables:
1. `cdko_experiment_design` (45,430 rows) and `cdko_sgrna_counts` (3,578,017 rows) — raw per-sgRNA guide sequences and per-replicate count data. These are analysis *inputs*, not gene-pair-level results, and are excluded: they are guide-level (not gene-pair-level) records, an order of magnitude larger, and redundant with the derived scores below for BioThings purposes.
2. `cdko_original_sl_results` (280,483 rows, the paper's reported 16,059 SL + 264,424 non-SL pairs) plus 7 scoring-method tables (`horlbeck_score`, `median_b_score`, `median_nb_score`, `gemini_score`, `mageck_score`, `sgrna_derived_b_score`, `sgrna_derived_nb_score`), all keyed by `gene_pair_id`. These are gene-pair-level results — the entity type the paper is about — and are what the parser ingests.

The parser issues its own `LEFT JOIN` of `cdko_original_sl_results` against all 7 scoring tables on `gene_pair_id`, rather than reusing SLKB's built-in `calculated_sl_table` view: that view is `GROUP BY gemini_score.gene_pair_id`, which silently collapses to one row per `gene_pair_id` even though a small number of `gene_pair_id`s recur across multiple `(study_origin, cell_line_origin)` pairs (see below) — using it would have silently dropped ~4,100 legitimate per-cell-line records.

**`_id` strategy**: `gene_pair_id` alone is not globally unique — verified `SELECT COUNT(DISTINCT gene_pair_id), COUNT(*) FROM cdko_original_sl_results` returns `276,382` vs. `280,483`, i.e. ~4,100 `gene_pair_id`s are shared by more than one `(study, cell line)` row (the same CDKO library design reused across cell lines within one study). The composite `(study_origin, cell_line_origin, gene_pair_id)` was verified fully unique (`280,483` distinct combos = `280,483` rows), so `_id = f"{study_origin}_{cell_line_origin}_{gene_pair_id}"` is used. A `seen_ids` guard is kept in the parser as a defensive no-op (it never fires on the real dataset, confirmed by the 0-duplicate test run below).

**`study_origin`**: this column holds the PMID of the *original* CDKO screen publication (verified: PMID 33956155 → "Minimized combinatorial CRISPR screens identify genetic interactions in autophagy", a real, unrelated-to-SLKB paper), so it is exposed as `study_origin_pmid` for clarity rather than a bare numeric field.

**Fields excluded**: `gene_pair` (a `"GENE1|GENE2"` string concatenation) is dropped — fully redundant with `gene_1`/`gene_2`, which are kept as separate fields for querying.

**Data cleaning**: `dict_sweep(unlist(doc), [None])` removes the many `NULL` scoring-method sub-fields that don't apply to every gene pair (each of the 7 scoring methods has its own coverage, see Field Coverage below) — nested empty sub-objects (e.g. an entirely-null `scores.horlbeck`) are dropped entirely by `dict_sweep`, not emitted as `{}`.

## Sample Output Documents

**Typical record** (`is_sl: false`, all 7 scoring methods populated except `gemini.sl_score_sensitive_lethality`):
```json
{
  "_id": "33956155_RPE1_0",
  "slkb": {
    "gene_pair_id": 0,
    "gene_1": "AKT1",
    "gene_2": "AMBRA1",
    "study_origin_pmid": "33956155",
    "cell_line_origin": "RPE1",
    "is_sl": false,
    "original_result": {
      "sl_score": -0.010982069570913,
      "statistical_score": 0.0,
      "sl_score_cutoff": -1.0,
      "statistical_score_cutoff": 0.0
    },
    "scores": {
      "horlbeck": {"sl_score": -0.1780039576767812, "standard_error": 0.15541682428945283},
      "median_b": {"sl_score": 0.7804234823179965, "standard_error": 0.2984898749661755, "z_sl_score": 2.6145727134176093},
      "median_nb": {"sl_score": 1.035966045556255, "standard_error": 0.2984898749661755, "z_sl_score": 3.4706907417668664},
      "gemini": {"sl_score_strong": -1.45745362193367, "sl_score_sensitive_recovery": 1.90139811755965},
      "mageck": {"sl_score": 1.01035, "standard_error": 0.6000217313465036, "z_sl_score": 1.6838556792479538},
      "sgrna_derived_b": {"sl_score": 2.98126342993733},
      "sgrna_derived_nb": {"sl_score": 2.8137024736584277}
    }
  }
}
```
Source cross-reference: browse this study/cell-line pair on the live site's "Browse SL Score" tab at `https://slkb.osubmi.org` (per-record deep links are not exposed by the Shiny UI; PMID 33956155 identifies the original CDKO screen).

**Edge case** (`is_sl: true` — a true SL gene pair, same study/cell line):
```json
{
  "_id": "33956155_RPE1_7",
  "slkb": {
    "gene_pair_id": 7,
    "gene_1": "AKT1",
    "gene_2": "ATG16L2",
    "study_origin_pmid": "33956155",
    "cell_line_origin": "RPE1",
    "is_sl": true,
    "original_result": {
      "sl_score": -2.29140501476106,
      "statistical_score": 0.0,
      "sl_score_cutoff": -1.0,
      "statistical_score_cutoff": 0.0
    },
    "scores": {
      "horlbeck": {"sl_score": -0.319792572758912, "standard_error": 0.08411199778882615},
      "median_b": {"sl_score": 0.4819875546392696, "standard_error": 0.21821627431577723, "z_sl_score": 2.2087608092043274},
      "median_nb": {"sl_score": 0.737530117877528, "standard_error": 0.21821627431577723, "z_sl_score": 3.37981262025517},
      "gemini": {"sl_score_strong": -0.362052404035177, "sl_score_sensitive_recovery": 0.362052404035177},
      "mageck": {"sl_score": 0.7304499999999998, "standard_error": 0.7931665089702579, "z_sl_score": 0.9209289496455406},
      "sgrna_derived_b": {"sl_score": 6.368396032398615},
      "sgrna_derived_nb": {"sl_score": 5.843189554711148}
    }
  }
}
```

## Field Coverage

Computed against the full 280,483-document collection (not a sample, since a full run completes in ~33 seconds):

- `slkb.gene_pair_id`, `gene_1`, `gene_2`, `study_origin_pmid`, `cell_line_origin`, `is_sl`, `original_result.*`: 100.0%
- `slkb.scores.mageck.*`: 94.0%
- `slkb.scores.median_nb.*`: 94.0%
- `slkb.scores.sgrna_derived_nb.sl_score`: 94.0%
- `slkb.scores.gemini.sl_score_strong`: 94.0%
- `slkb.scores.horlbeck.*`: 93.9%
- `slkb.scores.gemini.sl_score_sensitive_lethality`: 84.6%
- `slkb.scores.median_b.*`: 74.1%
- `slkb.scores.sgrna_derived_b.sl_score`: 74.1%
- `slkb.scores.gemini.sl_score_sensitive_recovery`: 9.5%

Coverage gaps reflect each scoring method's own filtering/QC steps (e.g. Horlbeck score requires `median counts ≥ 35` at the initial timepoint; Median-B/sgRNA-derived-B require background-control normalization data not present for every gene pair) — not parser defects. The two GEMINI sub-scores (`sl_score_sensitive_lethality` vs. `sl_score_sensitive_recovery`) are largely mutually exclusive per gene pair (a classification outcome of the GEMINI model), which is why neither individually approaches 94%.

## Test Results Summary

`biothings-cli` is fully broken in this sandbox — every subcommand (including `validate`) raises `AttributeError: module 'typer' has no attribute 'rich_utils'` at import time in `biothings/cli/settings.py`, before command dispatch (same typer 0.26.7 / biothings 1.0.2 incompatibility already logged for ~15 other plugins in `references/built-plugins-index.md`, e.g. `chemprob`, `open_genes`, `sorc`). Not patched, per instructions (shared environment).

Validated instead via direct `parser.load_data()` execution against the live-downloaded Figshare archive (`SQL_Dumps.zip`, downloaded with `curl -A "Mozilla/5.0"`, unzipped locally to reproduce the Hub's `uncompress: true` behavior):
- **280,483 / 280,483** source rows (`cdko_original_sl_results`) yielded as documents — 0 skipped, 0 exceptions.
- **0 duplicate `_id`s** (`len(set(ids)) == len(ids)`), confirming the composite `(study_origin, cell_line_origin, gene_pair_id)` key holds.
- Full parse (in-memory sqlite3 load of the 943 MB dump + 7-way `LEFT JOIN` + document construction) completes in ~33 seconds.
- `version.get_release()` executed live against the Figshare API and returned `"v1_20230822"` (Figshare article version 1, `modified_date` 2023-08-22 — the only release published to date).
- Manual review of both a typical (`is_sl: false`) and edge-case (`is_sl: true`) document confirmed correct field mapping, `dict_sweep`/`unlist` cleanup (null GEMINI sub-scores correctly dropped rather than emitted as `null`), and float precision preserved from the source sqlite3 REAL columns.

## Mapping Overview

`mapping.py`'s `get_customized_mapping()` returns a single top-level `slkb` object with:
- `gene_pair_id`: `integer`
- `gene_1`, `gene_2`, `study_origin_pmid`, `cell_line_origin`: `keyword` (exact-match identifiers, no free-text search need)
- `is_sl`: `boolean`
- `original_result`: nested `object` with 4 `float` sub-fields (`sl_score`, `statistical_score`, `sl_score_cutoff`, `statistical_score_cutoff`)
- `scores`: nested `object` with 7 sub-objects (`horlbeck`, `median_b`, `median_nb`, `gemini`, `mageck`, `sgrna_derived_b`, `sgrna_derived_nb`), each containing 1–3 `float` fields (`sl_score`, `standard_error`, `z_sl_score`, or the 3 GEMINI-specific score names)

**Mapping validation**: `inspect --mode mapping` itself could not run (same typer/biothings blocker above). Validated instead via a standalone script (`slkb_validate_mapping.py`) that ran the parser against the full 280,483-document collection, recursively recorded the observed Python type at every field path, flattened `mapping.py`'s `properties` to the same path format, and diffed the two: **0 missing fields, 0 type mismatches, 0 unused mapping entries** — every leaf field has exactly one consistent Python type across the entire collection (confirmed separately: every field showed only a single `type(v).__name__` value across all 280,483 documents), so no field required widening or conflict resolution.

**Mapping Conflicts**: None. Every field (including the sparsely-populated scoring-method sub-fields, e.g. `scores.gemini.sl_score_sensitive_recovery` at 9.5% coverage) was consistently `float` wherever present and `None`/absent otherwise — no field alternated between scalar and object, or between numeric and string, across the sample.
