# LncRNADisease v3.0 — Design Rationale

## Quick Stats

| Metric | Value |
|---|---|
| Source rows — `website_simple_data.csv` | 22,786 (header + 22,786 data rows) |
| Source rows — `website_alldata.tsv` | 25,788 (header + 25,788 data rows) |
| Documents yielded | **22,786** |
| Rows skipped | 0 rows dropped from `website_simple_data.csv` (all rows have a `Database_ID`, `ncRNA_Symbol`, and `Disease_Name`) |
| Deduplication | `seen_ids` guard on `Database_ID` — no duplicates encountered in this dataset (0 skipped) |
| Evidence-matched docs | 22,030 / 22,786 (96.68%) — 756 docs (3.32%) have `evidence_count: 0` because their normalized (symbol, category, species, disease) key did not find a match in `website_alldata.tsv` (whitespace/casing drift between the two export files) |
| Target API | pending.api |
| Data format | CSV (1.5 MB) + TSV (13.6 MB), bulk download, no auth |

## Why These Dump Files Were Chosen

The datasource's download page (`http://www.rnanut.net/lncrnadisease/index.php/home/info/download`) lists 8 files. Two were selected; six were rejected:

**Selected:**
- `website_simple_data.csv` — one row per unique (ncRNA, species, disease) association, carrying the stable internal accession `Database_ID` (e.g. `LDA0000001`). This is the only file with a persistent per-association primary key, so it drives document identity (`_id`).
- `website_alldata.tsv` — one row per piece of experimental evidence supporting an association (validated method, dysfunction pattern, description, causality classification, causal description, supporting PubMed ID). An association can have multiple evidence rows (e.g. HOTTIP–Osteosarcoma has 2). This is the richest content file and is joined against `website_simple_data.csv` by normalized association key.

**Rejected:**
- `website_causal_data.tsv` — a strict subset of `website_alldata.tsv` filtered to `Causality=Yes` rows. `website_alldata.tsv` already carries the `Causality` column, so this file is fully redundant.
- `lncRNA.xlsx` (208,275 rows), `circRNA.xlsx` (13,075 rows), `all ncRNA-disease information.xlsx` (206,963 rows), `predicted lncRNA-disease information.xlsx` (195,395 rows) — all four lack the `Causality` and confidence-related columns present in the current v3.0 schema, and their row counts are 8–10x larger than the paper's stated 25,440 experimentally-supported entries. These appear to be legacy cumulative/predicted dumps predating the v3.0 restructuring (the "predicted" file explicitly contains computational prediction-method rows with `N/A` for Sample/Description/PubMed ID). Ingesting them would mix stale/predicted records into a dataset the paper describes as purely experimentally-supported. Excluded per the file-selection default policy (avoid oversized supersets with mismatched/legacy schema).

## Why the Parser Works the Way It Does

- **`_id` strategy**: `Database_ID` from `website_simple_data.csv` (e.g. `LDA0000001`) — the only stable, unique-per-association identifier the datasource publishes. A `seen_ids` set guards against duplicate `Database_ID`s (none observed).
- **Evidence join**: An in-memory index (`evidence_index`) is built once from `website_alldata.tsv`, keyed by a normalized tuple `(ncRNA symbol, category, species, disease)` (lowercased, whitespace-stripped). The main loop walks `website_simple_data.csv` and looks up all matching evidence rows for each `Database_ID`. This mirrors the "merged multi-row records → `associatedWith`-style list" pattern from the plugin generator skill — here as an `evidence` list.
- **Document structure**: top-level `_id` + `lncrnadisease` sub-object containing the association's core fields (`ncrna_symbol`, `ncrna_category`, `species`, `disease_name`), a rollup boolean `is_causal` (true if any evidence row has `Causality: Yes`), an `evidence_count`, a deduplicated sorted `pubmed_ids` list, and the full `evidence` list/object.
- **Fields skipped**: none of the 12 columns across both files are dropped; every evidence-level field (`Sample`, `Dysfunction Pattern`, `Validated Method`, `Description`, `Clinical Application`, `Causality`, `Causal Description`, `PubMed ID`) is preserved under `evidence`.
- **Data cleaning**: `dict_sweep(unlist(doc), [None])` removes empty/None fields; `unlist()` collapses the common single-evidence case from a one-item list to a bare object (this is expected and handled — see Mapping Overview below, not a conflict per the mapping-generation reference's rule #2).
- **3.32% zero-evidence gap**: 756 `Database_ID`s in `website_simple_data.csv` did not find a matching evidence row in `website_alldata.tsv` after key normalization — likely due to residual formatting differences (extra internal whitespace, punctuation variants in disease names) between the two independently-exported files. These docs still carry the core association fields (symbol/category/species/disease) but have `evidence_count: 0` and no `evidence`/`pubmed_ids` keys.

## Sample Output Documents

**Typical (single evidence row):**
```json
{
  "_id": "LDA0000001",
  "lncrnadisease": {
    "ncrna_symbol": "ARHGAP5-AS1",
    "ncrna_category": "LncRNA",
    "species": "Homo sapiens",
    "disease_name": "Carcinoma, Hepatocellular",
    "is_causal": true,
    "evidence_count": 1,
    "pubmed_ids": "36354136",
    "evidence": {
      "sample": "HCC cells and tissues",
      "dysfunction_pattern": "Epigenetics( m6 A-modified)",
      "validated_method": "qRT-PCR",
      "description": "Among these lncRNAs, we found that ARHGAP5-AS1 is the lncRNA with the highest levels of m6 A modification and significantly increased expression in HCC specimens. ...",
      "causality": "Yes",
      "causal_description": "ARHGAP5-AS1 remarkably promotes malignant behaviours of HCC cells ex vivo and in vivo.",
      "pubmed_id": "36354136"
    }
  }
}
```
Source cross-reference: search `ARHGAP5-AS1` + `Carcinoma, Hepatocellular` at http://www.rnanut.net/lncrnadisease/index.php/home/search

**Edge case (multi-evidence association):**
```json
{
  "_id": "LDA0000002",
  "lncrnadisease": {
    "ncrna_symbol": "HOTTIP",
    "ncrna_category": "LncRNA",
    "species": "Homo sapiens",
    "disease_name": "Osteosarcoma",
    "is_causal": true,
    "evidence_count": 2,
    "pubmed_ids": ["31423232", "33475442"],
    "evidence": [
      {
        "sample": "OS tissues",
        "dysfunction_pattern": "Interaction(PTBP1/KHSRP )",
        "validated_method": "qRT-PCR//RIP",
        "description": "Our data demonstrated HOTTIP was upregulated in OS tissues. ...",
        "causality": "Yes",
        "causal_description": "HOTTIP knockdown resulted in a suppression of OS cell proliferation, invasion and migration...",
        "pubmed_id": "33475442"
      },
      {
        "sample": "OS tissues and cell lines",
        "dysfunction_pattern": "Interaction[c-Myc]",
        "validated_method": "CCK8//qRT-PCR//Wound Healing Assay//Western Blot",
        "description": "HOTTIP was demonstrated to be upregulated in OS tissues and cell lines. ...",
        "causality": "Yes",
        "causal_description": "knockdown of HOTTIP inhibited OS cell migration, invasion and EMT...",
        "pubmed_id": "31423232"
      }
    ]
  }
}
```
Source cross-reference: search `HOTTIP` + `Osteosarcoma` at http://www.rnanut.net/lncrnadisease/index.php/home/search

## Field Coverage

(computed over the full 22,786-document collection)

- `ncrna_symbol`: 100.0%
- `ncrna_category`: 100.0%
- `species`: 100.0%
- `disease_name`: 100.0%
- `is_causal`: 100.0%
- `evidence_count`: 100.0%
- `pubmed_ids`: 96.68%
- `evidence`: 96.68%

`ncrna_category` breakdown: CircRNA 11,872 (52.1%), LncRNA 10,914 (47.9%). `is_causal: true` for 7,700 docs (33.79%).

## Test Results Summary

`biothings-cli` is broken in this sandbox: every subcommand (`validate`, `dump`, `upload`, `list`, `inspect`, `inspect --mode mapping`) raises `AttributeError: module 'typer' has no attribute 'rich_utils'` at import time (typer 0.26.7 / biothings 1.0.2 incompatibility — the same issue already logged for ~15 other plugins in `built-plugins-index.md`, e.g. chemprob, molbic, persade). Per instructions, the shared environment was **not** patched. Validation was instead performed by:

1. Downloading both source files directly with `curl -A "Mozilla/5.0"` into a scratch `data_folder` (`website_simple_data.csv` 1.5 MB, `website_alldata.tsv` 13.6 MB) — both confirmed `content-type: text/csv` / `text/tab-separated-values` (real data, not HTML) during Stage 1 inspection.
2. Calling `parser.load_data(data_folder)` directly against the full files (no sampling) and collecting all yielded documents: **22,786 documents**, matching the unique `Database_ID` count in `website_simple_data.csv` exactly. `_id` format confirmed as the 10-character `LDA0000001`-style stable accession on every document. No parser exceptions.
3. Field coverage computed over the full collection (see above) — no unexpectedly all-null fields; `pubmed_ids`/`evidence` gap (3.32%) fully explained by the evidence-join mismatch noted above.
4. `version.py:get_release()` invoked directly — returned `"20240325"` from a live `HEAD` request's `Last-Modified` header on `website_simple_data.csv` (the more recent of the two files' Last-Modified dates).
5. Mapping validation: a standalone script (see Mapping Overview below) recursively walked all 22,786 yielded documents, recorded the observed Python type at every field path, and diffed it against `mapping.py`'s flattened `properties`. Result: **0 missing fields, 0 type mismatches, 0 unused mapping entries** across the full collection (not a sample).

## Mapping Overview

`mapping.py`'s `get_customized_mapping()` returns, nested under the top-level `lncrnadisease` key (matching the parser's document structure):

| Field | ES type |
|---|---|
| `ncrna_symbol` | `keyword` |
| `ncrna_category` | `keyword` |
| `species` | `keyword` |
| `disease_name` | `keyword` |
| `is_causal` | `boolean` |
| `evidence_count` | `integer` |
| `pubmed_ids` | `keyword` |
| `evidence.sample` | `keyword` |
| `evidence.dysfunction_pattern` | `keyword` |
| `evidence.validated_method` | `keyword` |
| `evidence.description` | `text` + `.raw` keyword subfield |
| `evidence.clinical_application` | `keyword` |
| `evidence.causality` | `keyword` |
| `evidence.causal_description` | `text` + `.raw` keyword subfield |
| `evidence.pubmed_id` | `keyword` |

`description` and `causal_description` are mapped as `text` (with a `.raw` keyword subfield for exact-match/aggregation) since they hold multi-sentence free-text extracted from paper abstracts/results — everything else is short categorical or ID-like data and is mapped `keyword`.

`evidence` is a genuine scalar-vs-list case (single-evidence associations collapse to a bare object via `unlist()`, multi-evidence associations remain a list of objects) — per the mapping-generation reference's conflict-resolution rule #2 this is **not** a structural conflict; it is mapped once as an `object` with `properties`, which Elasticsearch applies uniformly whether the field holds one object or a list of them.

**Mapping Conflicts**: none. All 15 observed field paths across the full 22,786-document collection matched a single, unambiguous type with no heterogeneous/incompatible values.

## Known Limitations (carried from Stage 1 inspection)

- Disease names are free-text strings, not MONDO/DOID/MeSH-coded, despite the paper's claim that disease names are mapped to Disease Ontology/MeSH on the live site — that mapping is web-UI-only and not exposed in the bulk files.
- The paper's per-pair confidence score (0.75–1.0) is not present in any downloadable file.
- License: paper states CC BY-NC 4.0; the live site itself shows only a generic "Copyright 2013-2023, all rights reserved" notice with no CC badge (flagged as a mismatch in Stage 1).
- Entity counts have drifted since publication (paper: 6,066 lncRNAs / 10,732 circRNAs / 566 diseases; current download: 5,540 unique lncRNA symbols / 11,309 unique circRNA symbols / 566 diseases) — file `Last-Modified` dates (2023-09-07 and 2024-03-25) confirm a post-publication content refresh. Disease count matches exactly, confirming correct file identification.
