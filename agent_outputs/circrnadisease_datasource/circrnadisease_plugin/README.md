# circRNADisease — Design Rationale

## Quick Stats

| Metric | Value |
|---|---|
| Source rows (raw TSV) | 15,423 |
| Documents yielded | 13,076 (one per unique circRNA-label + MONDO-disease pair) |
| Rows skipped | 79 total — 34 missing any usable circRNA label (`circrna_id`/`circ_rna_name`/`circrna_synonyms` all empty); 45 missing a `Disease_MONDO_id` |
| Evidence rows retained | 15,344 (nested inside the 13,076 documents; 1,461 documents carry 2–11 evidence rows, 11,615 carry exactly 1) |
| Deduplication | None needed at `_id` level — 0 `_id` collisions across 13,076 documents (rows are aggregated by pair key, not deduplicated away) |
| Target API | pending.api |
| Data format | Plain-text TSV, single file, 9.2 MB |

## Why These Dump Files Were Chosen

The live site (`cgga.org.cn/circRNADisease`) currently serves four bulk downloads under `/circRNADisease/download/`:

- **`circRNADisease_V3_circrna_details.txt`** (9.2 MB, TSV) — **selected**. This is the core circRNA-disease association table this evaluation targets — the direct successor to the dataset described in the NAR 2024 paper (circRNADisease v2.0), now expanded under an in-place "v3.0" label.
- `circRNADisease_V3_circrna_details.xlsx` (3.2 MB) — same content as the TXT file in spreadsheet form. Not ingested; the TSV avoids an `openpyxl`/pandas dependency for no additional information.
- `circRNADisease_V3_circ2mut.txt.zip` (43.3 MB) — 7,159,865 mutation-circRNA co-occurrence records across 30 TCGA cancer types. **Excluded**: this is a different entity/relation type (genomic variant × circRNA), not a circRNA-disease association, and is out of scope for the resource this evaluation is about. Flagged as a candidate for a future, separate plugin.
- `circRNADisease_V3_circ2cnv.zip` (39.3 MB) — 2,962,504 CNV-circRNA records across 33 TCGA cancer types. **Excluded** for the same reason as circ2mut.

All four files are hosted directly on the datasource's own domain (`cgga.org.cn`) with no login/registration gate; `curl -sIL` on each returns a real content-type (`text/plain`, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, `application/zip`), confirming they are real data files rather than JS-rendered landing pages.

## Why the Parser Works the Way It Does

**`_id` strategy**: `{circrna_label}_{mondo_id}`, e.g. `hsa_circ_0007158_MONDO:0004986`. The raw file has no single natural key spanning all rows — 37% of rows (5,733/15,423) leave `circrna_id` empty and only populate `circ_rna_name` or `circrna_synonyms` instead. `_circ_label()` falls back across `circrna_id` → `circ_rna_name` → `circrna_synonyms` in that order and records which column supplied the label in `circrna.label_source`, so downstream consumers can tell a formal circBase ID from a paper-reported name.

**Aggregation, not one-row-per-document**: The raw file has 15,423 rows but only 13,122 unique (circRNA label, MONDO ID) pairs — 1,463 pairs are supported by more than one literature row (up to 11 rows for the same pair, e.g. `circHIPK3`/hepatocellular carcinoma). Rather than emitting duplicate/near-duplicate documents (which would either collide on `_id` under `on_duplicates: error` or silently drop 1,463 pairs' worth of extra evidence under `ignore`), the parser groups rows by pair key and nests every supporting literature row under `evidence`, preserving all 15,344 usable evidence rows (79 of the raw 15,423 rows are dropped for lacking a usable label or MONDO ID — see Quick Stats).

**Document structure**: `_id` + `circrnadisease` → `circrna` (label/synonyms/host gene/species) + `disease` (MONDO id/name/reported name) + `evidence` (list of per-PMID records: journal, year, title, expression pattern, detection method, free-text description, confidence score).

**Fields extracted**: all 16 source columns (see inspection report); `journal` and `pub_time` are kept for provenance despite being classified REDUNDANT (not disease/circRNA content per se) since they're needed to disambiguate multiple evidence rows for the same pair.

**Fields skipped**: none dropped outright — every source column is represented in the output.

**Deduplication**: none required at the pair level (0 `_id` collisions observed); `on_duplicates: "error"` is set in `manifest.json` as the correct default since the parser itself guarantees uniqueness by construction (dict keyed by pair_key).

**Data cleaning**: `dict_sweep(unlist(doc), [None, "", [], {}])` removes empty/None values; `unlist()` collapses single-item evidence lists to a scalar dict, which is why `evidence` appears as either a single object or a list of objects across documents (documented in the Mapping Overview below — this is expected, not a bug).

## Sample Output Documents

**Typical (single evidence row):**
```json
{
  "_id": "hsa_circ_0007158_MONDO:0004986",
  "circrnadisease": {
    "circrna": {
      "label": "hsa_circ_0007158",
      "label_source": "circrna_id",
      "circbase_id": "hsa_circ_0007158",
      "name": "hsa_circ_FAM169A",
      "synonyms": "circFAM169A",
      "host_gene": "FAM169A",
      "species": "Homo sapiens"
    },
    "disease": {
      "mondo_id": "MONDO:0004986",
      "mondo_name": "urinary bladder carcinoma",
      "reported_name": "bladder carcinoma"
    },
    "evidence": {
      "pmid": "27484176",
      "journal": "Scientific reports",
      "pub_time": "2016",
      "title": "Screening differential circular RNA expression profiles reveals the regulatory role of circTCF25-miR-103a-3p/miR-107-CDK6 pathway in bladder carcinoma.",
      "expression_pattern": "down-regulated",
      "detection_method": "RT-qPCR; Microarray",
      "description": "circFAM169A (hsa_circ_0007158) is significantly down-regulated in bladder carcinoma tissues compared with matched para-carcinoma tissues and was among the six circRNAs validated by qRT-PCR, suggesting potential diagnostic value.",
      "confidence_score": 0.5541
    }
  }
}
```
Source cross-reference: [PMID 27484176 on PubMed](https://pubmed.ncbi.nlm.nih.gov/27484176/) (per-record deep links on the circRNADisease site itself could not be confirmed to follow a stable URL pattern; the search interface is at `https://cgga.org.cn/circRNADisease/search_by_circRNA.jsp`).

**Edge case (multi-evidence pair, 3 of 3 evidence rows shown truncated):**
```json
{
  "_id": "hsa_circ_HIPK3_MONDO:0007256",
  "circrnadisease": {
    "circrna": {
      "label": "hsa_circ_HIPK3",
      "label_source": "circ_rna_name",
      "name": "hsa_circ_HIPK3",
      "synonyms": "circHIPK3",
      "host_gene": "HIPK3",
      "species": "Homo sapiens"
    },
    "disease": {
      "mondo_id": "MONDO:0007256",
      "mondo_name": "hepatocellular carcinoma",
      "reported_name": "hepatocellular carcinoma"
    },
    "evidence": [
      {"pmid": "27050392", "journal": "Nature communications", "pub_time": "2016", "expression_pattern": "up-regulated", "detection_method": "RT-qPCR; RNA-seq", "confidence_score": 0.8123, "title": "Circular RNA profiling reveals an abundant circHIPK3 that regulates cell growth by sponging multiple miRNAs."},
      {"pmid": "32977948", "journal": "Biochemical and biophysical research communications", "pub_time": "2020", "expression_pattern": "up-regulated", "detection_method": "RT-qPCR", "confidence_score": 0.7595, "title": "Knockdown of circ_HIPK3 inhibits tumorigenesis of hepatocellular carcinoma via the miR-582-3p/DLX2 axis."},
      {"pmid": "33247421", "journal": "Digestive diseases and sciences", "pub_time": "2021", "expression_pattern": "up-regulated", "detection_method": "RT-qPCR; ISH", "confidence_score": null, "title": "HIPK3 Circular RNA Promotes Metastases of HCC Through Sponging miR-338-3p to Induce ZEB2 Expression."}
    ]
  }
}
```
Source cross-reference: [PMID 27050392](https://pubmed.ncbi.nlm.nih.gov/27050392/) (first supporting paper for this pair).

## Field Coverage

(computed across the full 13,076-document collection produced by `parser.load_data()`)

- `circrna.label`: 100.0%
- `circrna.species`: 100.0%
- `disease.mondo_id`: 100.0%
- `disease.reported_name`: 100.0%
- `disease.mondo_name`: 99.6%
- `circrna.synonyms`: 72.6%
- `circrna.name`: 67.7%
- `circrna.host_gene`: 66.8%
- `circrna.circbase_id`: 60.4% (the remaining 39.6% use `circ_rna_name` or `circrna_synonyms` as the `label`, tracked via `label_source`)
- `evidence.pmid` / `evidence.journal` / `evidence.pub_time` / `evidence.title` / `evidence.expression_pattern` / `evidence.detection_method` / `evidence.description` / `evidence.confidence_score`: 100.0% within all 15,344 retained evidence rows

## Test Results Summary

`biothings-cli` is fully broken in this sandbox — every subcommand (including `validate`) raises `AttributeError: module 'typer' has no attribute 'rich_utils'` at import time in `biothings/cli/settings.py`, before command dispatch (typer 0.26.7 / biothings 1.0.2 incompatibility, the same issue already logged for ~15 other plugins in `references/built-plugins-index.md`, e.g. `ncrnadrug`, `clinicalomicsdb`). The shared environment was not patched. Validated instead via:

1. **Direct `parser.load_data()` execution** against the live-downloaded `circRNADisease_V3_circrna_details.txt` (9.2 MB, 15,423 rows, downloaded via `curl -A "Mozilla/5.0"`): 0 exceptions, 13,076 documents yielded (0 silent-zero-doc failure), 0 `_id` collisions, all `_id` values are non-empty strings well under the 512-char limit.
2. **Standalone mapping-diff script**: recursively walked all 13,076 yielded documents, recorded the observed Python type at every field path, and diffed against `mapping.py`'s flattened `properties`. Result: **0 missing fields, 0 unused mapping entries, 0 type mismatches** across all 18 field paths.

| Check | Result |
|---|---|
| Parser runs without exception | PASS |
| Non-zero document count | PASS (13,076) |
| `_id` uniqueness | PASS (0 collisions) |
| `_id` is string, <512 chars | PASS |
| `dict_sweep`/`unlist` cleanliness (no stray `None`/empty) | PASS |
| Mapping field coverage (mapping.py vs. real docs) | PASS (0 missing, 0 mismatches) |

## Mapping Overview

`mapping.py`'s `get_customized_mapping()` returns, nested under `circrnadisease.properties`:

- `circrna.{label, label_source, circbase_id, name, synonyms, host_gene, species}` → all `keyword` (short identifiers/categorical strings, no free-text search need)
- `disease.{mondo_id, mondo_name, reported_name}` → all `keyword`
- `evidence.{pmid, journal, pub_time, expression_pattern, detection_method}` → `keyword`
- `evidence.title`, `evidence.description` → `text` with a `.raw` `keyword` subfield (free-text fields meant for full-text search, per §3b's rule for descriptions/abstracts)
- `evidence.confidence_score` → `float`

**Mapping Conflicts**: None. The only structural variation observed is `evidence` appearing as a single object in 11,615 documents versus a list of objects in 1,461 documents (pairs supported by more than one literature row) — per the mapping-generation reference's conflict-resolution rule #4 ("object in some docs, list-of-objects in others is the same object shape, not a type conflict"), this is mapped once via `evidence.properties` and both shapes validated cleanly against it in the diff script (0 mismatches).

## Notes

- `biothings-cli` is broken in this sandbox for every subcommand (`AttributeError: module 'typer' has no attribute 'rich_utils'`) — not patched (shared environment); validated instead via direct `parser.load_data()` execution as described above.
- The live site now serves "circRNADisease v3.0" data (per the download page's own text) rather than the exact v2.0 snapshot described in the cited NAR 2024 paper. Entity counts differ materially from the paper (paper: 6,998 associations / 4,246 circRNAs / 330 diseases via Disease Ontology; live download: 15,423 rows / ~13,076 unique pairs / 656–657 unique MONDO IDs, using MONDO rather than DO). This is expected growth of the same underlying resource, not a wrong source — the live bulk file is the most current, complete, and directly downloadable release of circRNADisease, and was used as-is.
- License: CC BY-NC per the NAR publication's stated license; no separate license/terms page exists on the live site (`about.jsp`/`license.jsp` both 404), so this is a paper-sourced license claim, not a site-published one. Non-commercial use only.
- No public API — bulk TSV download is the only ingestion path.
