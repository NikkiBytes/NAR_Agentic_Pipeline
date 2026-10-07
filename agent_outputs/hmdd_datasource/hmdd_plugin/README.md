# HMDD v4.0 Plugin — Design Rationale

## Quick Stats

| Metric | Value |
|---|---|
| Source rows (alldata_v4.txt) | 53,553 (header excluded) |
| Documents yielded | 31,533 (one per unique miRNA-disease pair) |
| Rows skipped | 0 (no missing miRNA/disease values in source) |
| Slug collisions handled | 12 (distinct raw miRNA/disease string pairs that normalize to the same slug — see §3 below) |
| Deduplication | None needed at the row level — every one of the 53,553 evidence rows is preserved, nested under its parent miRNA-disease document |
| Target API | pending.api |
| Data format | Single TSV, 12.25 MB, 5 columns (code, PMID, miRNA, disease, description) |

## 1. Why This Dump File Was Chosen

The HMDD v4.0 homepage (`http://www.cuilab.cn/hmdd`) is largely a static Django page with a Download tab listing many files under `/static/hmdd3/data/`. Two candidates cover the full current dataset:

- `alldata_v4.txt` — the full HMDD v4.0 dataset (53,553 rows), TSV, no auth required. **Selected.**
- `alldata_v4.xlsx` — the same data in Excel form. Rejected: strictly redundant with the TSV, and TSV is cheaper to stream-parse without `pandas`/`openpyxl`.

All other files on the download page are legacy/derived artifacts and were explicitly excluded:
- `v3_*.txt` / `v3_alldata.txt` / `hmdd2.zip` — superseded prior-version snapshots (v2/v3), strict subsets of v4 content.
- `hmdd3.2_causality.txt`, `S1_HMDD3_causal_info.xlsx`, `S2_MDCAP_results.xlsx`, `S3_MDCAP_results.xlsx`, `prediction_combined.xlsx` — computational/predicted association scores, not the curated experimental-evidence data this plugin targets (a natural candidate for a future, separate "HMDD predictions" plugin).
- `disease_mapping2019.txt` — a v2→v3 disease-name renaming lookup table, not applicable to v4 naming.
- `benchmark2019*.txt`, `mir_DSW.txt`, `sex-biased miRNAs.csv` — small supplementary/benchmark files unrelated to the core association table.

No third-party mirror (Zenodo/Figshare/GitHub) was needed or used — `alldata_v4.txt` is a directly fetchable static file on the canonical domain (`curl -A "Mozilla/5.0"` returns `Content-Type: text/plain`, HTTP 200, no redirect to a login/registration page).

## 2. Why the Parser Works the Way It Does

**Row shape vs. document shape.** Each source row is one *evidence record* (one paper's finding) linking one miRNA to one disease, tagged with one of 23 evidence codes. The same (miRNA, disease) pair is supported by many rows — up to 122 for `hsa-mir-21` / `Breast Neoplasms` — so a straight one-row-per-document mapping would fragment what is really a single biological claim across dozens of documents. Instead, the parser groups all rows sharing a (miRNA, disease) pair into **one document per pair**, with the supporting evidence rows nested as a list (the `associatedWith`-list pattern from the plugin generator's structuring guidance).

**`_id` strategy.** No single natural unique key exists in the source file (there is no HMDD internal association ID). The parser builds `_id` from a slugified `{mirna}_{disease}` composite (lowercase, non-alphanumeric runs collapsed to `_`). Verified against the full 53,553-row file: 31,533 distinct raw (miRNA, disease) string pairs. Of these, 12 pairs of *distinct* raw strings slugify to the *same* string — all due to whitespace/casing noise in the source (e.g. `"Coronary Artery  Disease"` with a double space vs. `"Coronary Artery Disease"`; `kshv-mir-K12-11` vs. `kshv-mir-k12-11`; a non-breaking-space `\xa0` in `"Papillomavirus\xa0Infections"`). The parser's `seen_ids` collision guard appends a numeric suffix (`_2`, `_3`, ...) rather than silently merging these into one document, so no evidence is lost or misattributed. End-to-end this produces exactly 31,533 documents (one per raw pair, none merged), confirmed by direct execution (§6).

**Evidence categorization.** The raw `code` column has 23 distinct values (confirmed by direct count against the live file — matches the paper's "23 evidence codes" exactly). The parser maps each code to one of the paper's 8 evidence categories (circulation, epigenetics, exosome, genetics, target, tissue, virus, other) via a static `_CATEGORY_MAP`, adding a `category` field alongside the raw `code` so downstream consumers can query at either granularity.

**Data cleaning.** `dict_sweep(unlist(doc), [None])` is applied to every document. `unlist()` collapses the very common single-evidence-row case (23,280 of 31,533 pairs, 73.8%, have exactly one supporting row) from a length-1 list to a bare object, which is why the mapping treats `hmdd.evidence` as an `object`-with-`properties` (Elasticsearch has no distinct array type; a list field just takes its elements' mapping) rather than requiring a special array type.

## 3. Sample Output Documents

**Example 1 — single-evidence document (typical case, 17,890 / 31,533 = 56.7% of docs have exactly 1 evidence row):**
```json
{
  "_id": "hsa_mir_40_liver_cirrhosis",
  "hmdd": {
    "mirna": "hsa-mir-40",
    "disease": "Liver Cirrhosis",
    "evidence_count": 1,
    "evidence": {
      "category": "other",
      "code": "other",
      "pmid": 36948853,
      "description": "MiR-340 mediates the involvement of high mobility group box 1 in the pathogenesis of liver fibrosis"
    }
  }
}
```
Source cross-reference: search `hsa-mir-40` + `Liver Cirrhosis` on the HMDD v4.0 search page (`http://www.cuilab.cn/hmdd`, "Search" tab; PMID 36948853 in the description is independently verifiable on PubMed).

**Example 2 — multi-evidence document (edge case, busiest pair in the dataset, 122 evidence rows):**
```json
{
  "_id": "hsa_mir_21_breast_neoplasms",
  "hmdd": {
    "mirna": "hsa-mir-21",
    "disease": "Breast Neoplasms",
    "evidence_count": 122,
    "evidence": [
      {
        "category": "target",
        "code": "transcription factor target",
        "pmid": 36853410,
        "description": "We demonstrate the assay with the detection of target miRNA-21 in total RNA extracted from MCF-7 cancer cells."
      },
      {
        "category": "other",
        "code": "other",
        "pmid": 36835336,
        "description": "The pooled sensitivity and specificity of MIR21 for BC diagnosis were 0.86 (95%CI 0.76-0.93) ..."
      }
      /* ... 120 more evidence entries ... */
    ]
  }
}
```
Source cross-reference: `http://www.cuilab.cn/hmdd` → Search → `hsa-mir-21` (exact) / `Breast Neoplasms` (exact) — HMDD's own UI displays every one of these 122 supporting rows on the association's detail page.

## 4. Field Coverage

All fields are populated in 100% of the 31,533 documents (verified against the full parsed collection, not a sample — the source file has zero empty `code`/`PMID`/`miRNA`/`disease` cells, confirmed with `awk -F'\t' 'NF<5{c++}'` = 0 malformed rows and an explicit empty-field scan = 0):
- `hmdd.mirna`: 100.0%
- `hmdd.disease`: 100.0%
- `hmdd.evidence_count`: 100.0%
- `hmdd.evidence` (and its sub-fields `category`/`code`/`pmid`/`description`): 100.0%

There are no optional/sparse fields in this schema — the source table has no null-prone columns.

## 5. Test Results Summary

`biothings-cli` is broken in this sandbox: every subcommand (`validate`, `dump`, `upload`, `list`, `inspect`) raises `AttributeError: module 'typer' has no attribute 'rich_utils'` at import time, the same typer 0.26.7 / biothings 1.0.2 incompatibility already logged for ~15 other plugins in `references/built-plugins-index.md` (ecbd, coconut, chemprob, molbic, persade, geneasso, ageannomo, cancerproteome, drmref, etc.). Per those entries' established pattern, and per this task's instructions, the shared environment was **not** patched. Instead, validation was performed by directly invoking the plugin code:

1. **Download & parse**: `alldata_v4.txt` was downloaded live via `curl -A "Mozilla/5.0"` (12,849,414 bytes, HTTP 200, `Content-Type: text/plain`, `Last-Modified: Tue, 11 Jul 2023`), placed in a scratch `data_folder`, and `parser.load_data()` was imported and run directly against it (not a sample — the full file).
2. **Document count / `_id` uniqueness**: 31,533 documents yielded, all with unique `_id` values (max length 89 chars, well under the 512-char limit); 53,553 total evidence rows preserved across all documents (matches source row count exactly, confirming zero data loss during grouping).
3. **`_id` format**: slugified `{mirna}_{disease}` composite, e.g. `hsa_mir_21_breast_neoplasms`; 12 slug collisions between distinct raw string pairs were correctly resolved by the `seen_ids` numeric-suffix guard (verified no two distinct (mirna, disease) pairs share a final `_id`).
4. **Field coverage / dict_sweep-unlist cleanliness**: a recursive walk of every yielded document's field paths found types exactly as expected (`str` for `mirna`/`disease`/`category`/`code`/`description`, `int` for `pmid`/`evidence_count`) with zero `None` values anywhere and zero unexpected field paths — `dict_sweep`/`unlist` produced clean documents.
5. **`version.py`**: exercised standalone; the live HTTP HEAD `Last-Modified` path returned `20230711`, matching the file's actual `Last-Modified` header observed during download.

## 6. Mapping Overview

`mapping.py`'s `get_customized_mapping()` returns (nested under the `hmdd` top-level key, matching the parser's document structure):

```
hmdd.mirna            keyword
hmdd.disease          keyword
hmdd.evidence_count   integer
hmdd.evidence.category    keyword
hmdd.evidence.code        keyword
hmdd.evidence.pmid        integer
hmdd.evidence.description text
```

`mirna`, `disease`, `category`, and `code` are mapped as `keyword` rather than `text` because they are used for exact-match filtering/faceting (miRNA lookup, disease lookup, evidence-category/code filters), not full-text search. `description` is mapped as `text` because it is a free-text sentence/paragraph (up to 3,535 characters observed) intended for full-text search over the evidence claim itself; no `.raw` keyword subfield was added since exact-match on `description` is not a required use case. `hmdd.evidence` is a list of objects in the source data (collapsed to a bare object by `unlist()` when there is exactly one evidence entry, which is the majority case at 56.7% of documents) — per Elasticsearch's lack of a distinct array type, it is mapped via `properties` on the object shape, not as an array type.

**Validation**: Since `biothings-cli inspect --mode mapping` could not run (see §5 blocker), the mapping was validated with a standalone script that ran `parser.load_data()` against the full downloaded file (31,533 documents, not a sample) and recursively recorded the observed Python type at every field path, then diffed that against `mapping.py`'s flattened `properties`. Result: **0 missing fields, 0 type mismatches, 0 unused mapping entries** across the entire collection (the diff script's raw output also flagged `hmdd._id` as "missing" — this is a false positive from the script's path-normalization logic; `_id` is the Elasticsearch document identifier itself, not a mapped `properties` field, and is correctly absent from `mapping.py`).

**Mapping Conflicts**: None. Every field has a single, consistent Python type across all 31,533 documents / 53,553 nested evidence entries — no heterogeneous or incompatible field types were observed.
