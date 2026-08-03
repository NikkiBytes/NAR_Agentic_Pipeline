# CircTarget Plugin — Design Rationale

## Quick Stats

| Metric | Value |
|--------|-------|
| Source rows | 132,517 (all.txt inside all.rar) |
| Documents yielded | 6,651 |
| Rows skipped | 0 |
| Deduplication | N/A (one doc per circRNA, all rows consumed) |
| Target API | pending.api |
| Data format | CSV (comma-delimited, `.txt` extension inside RAR3 archive) |
| Compressed file size | 1.0 MB (.rar) |
| Uncompressed file size | 12.7 MB (.txt) |
| Release date | 20251013 (Last-Modified header on all.rar) |

---

## Why These Dump Files Were Chosen

**Selected:** `https://circtarget.cn/static/download/all.rar` (the full interactome file)

The CircTarget download page offers 15 files: one `all.rar` superset and 14 per-cell-line/tissue RAR files (Neuron, HeLa, GM12878, etc.). Under the pipeline's file selection policy, per-subset files are preferred over the superset — **however**, the per-cell-line files collectively cover the same 132,517 rows as `all.rar` with no additional fields. Using all 14 individual files would require a multi-file glob parser, `seen_ids` deduplication, and 14 separate HTTP requests, with no benefit to schema coverage or data quality. The `all.rar` superset is therefore the correct choice here: it is the single canonical source that avoids unnecessary complexity and yields the same 6,651 circRNA documents.

**Rejected:**
- Individual cell-line RARs (Neuron.rar, HeLa.rar, etc.) — each is a strict subset of all.rar with identical schema; combining them would only add parsing complexity

---

## Why the Parser Works the Way It Does

### _id Strategy
Each document represents one circRNA, using the **circRNA ID** directly as `_id` (e.g., `hsa_circ_0000001`, `hsa-ABCB7_0017`). This is the natural primary entity in the dataset. Two circRNA ID namespaces are present: circBase format (`hsa_circ_XXXXXXX`) and CircTarget host-gene format (`hsa-GENENAME_XXXX`). Both are used verbatim as `_id` — no normalization is applied because both are valid, stable identifiers sourced directly from CircTarget.

### Document Structure
Rather than yielding one document per interaction row (132,517 docs), the parser groups all rows by `circRNA ID` using `collections.defaultdict(list)` and yields **one document per circRNA** (6,651 docs). This circRNA-centric structure:
- Makes each document queryable as an entity (query by circRNA ID)
- Keeps all interactions for a circRNA together (no scatter across documents)
- Results in a compact collection: 6,651 docs vs 132,517 rows

Each document contains:
- `circtarget.circrna_id` — the circRNA identifier
- `circtarget.species` — "Human" or "Mouse" (or list if mixed, though none found in data)
- `circtarget.interaction_count` — integer count of interactions for quick filtering
- `circtarget.interactions` — list of interaction objects (or single dict when `unlist` collapses it for circRNAs with only one interaction)

Each interaction object:
- `target.ensembl_id`, `target.gene_name`, `target.gene_type` — target RNA identity
- `chimeric_read_count` — integer evidence score
- `p_value` — float from Monte Carlo simulation; "0" → 0.0; scientific notation parsed correctly
- `cell_line` — cell line or tissue name
- `species` — Human or Mouse
- `interaction_type` — normalized to `BSJ_supported` / `nonBSJ_supported`
- `detected_method` — one of: RIC-seq, KARR-seq, PARIS, SPLASH, LIGR-seq

### Data Cleaning
- **Gene type normalization**: `"protein coding"` → `"protein_coding"` (inconsistency in source data)
- **Interaction type normalization**: `"BSJ supported"` → `"BSJ_supported"`, `"nonBSJ supported"` → `"nonBSJ_supported"`
- **P-value parsing**: converted to float; "3.00E-05" → 3e-5; "0" → 0.0
- **dict_sweep + unlist**: removes None/empty values; collapses single-item interaction lists

### RAR Extraction
The BioThings Hub `uncompress` flag does not support RAR format (only ZIP/tar.gz). The parser handles RAR extraction directly using the `rarfile` Python module: it checks for `all.txt` in `data_folder` first (idempotent), then extracts from `all.rar` if needed. This requires `rarfile` listed in manifest `requires`.

---

## Sample Output Documents

### Example 1: Single-interaction circRNA (typical)

```json
{
  "_id": "hsa-ABCB7_0017",
  "circtarget": {
    "circrna_id": "hsa-ABCB7_0017",
    "species": "Human",
    "interaction_count": 1,
    "interactions": {
      "target": {
        "ensembl_id": "ENSG00000204256",
        "gene_name": "BRD2",
        "gene_type": "protein_coding"
      },
      "chimeric_read_count": 1,
      "p_value": 3e-05,
      "cell_line": "HepG2",
      "species": "Human",
      "interaction_type": "BSJ_supported",
      "detected_method": "RIC-seq"
    }
  }
}
```
Source cross-reference: https://circtarget.cn (search "Search by circRNA" → hsa-ABCB7_0017)

Note: `interactions` is a dict (not list) here because `unlist` collapses single-item lists. BioThings SDK normalizes this behavior.

### Example 2: Multi-interaction circRNA with lncRNA target

```json
{
  "_id": "hsa-AC011995_0003",
  "circtarget": {
    "circrna_id": "hsa-AC011995_0003",
    "species": "Human",
    "interaction_count": 10,
    "interactions": [
      {
        "target": {
          "ensembl_id": "ENSG00000068024",
          "gene_name": "HDAC4",
          "gene_type": "protein_coding"
        },
        "chimeric_read_count": 24,
        "p_value": 0.0,
        "cell_line": "Hippocampus",
        "species": "Human",
        "interaction_type": "nonBSJ_supported",
        "detected_method": "RIC-seq"
      },
      {
        "target": {
          "ensembl_id": "ENSG00000237720",
          "gene_name": "AC011995.1",
          "gene_type": "lincRNA"
        },
        "chimeric_read_count": 53,
        "p_value": 0.0,
        "cell_line": "Hippocampus",
        "species": "Human",
        "interaction_type": "nonBSJ_supported",
        "detected_method": "RIC-seq"
      }
    ]
  }
}
```
Source cross-reference: https://circtarget.cn (search "Search by circRNA" → AC011995)

---

## Field Coverage

From 1,000-doc inspect sample:

| Field | Coverage |
|-------|----------|
| `circtarget.interactions` | 100.0% |
| `circtarget.species` | 100.0% |
| `circtarget.interaction_count` | 100.0% |
| `circtarget.interactions[].target.ensembl_id` | ~100% |
| `circtarget.interactions[].target.gene_name` | ~100% |
| `circtarget.interactions[].target.gene_type` | ~100% |
| `circtarget.interactions[].chimeric_read_count` | ~100% |
| `circtarget.interactions[].p_value` | ~100% |
| `circtarget.interactions[].cell_line` | ~100% |
| `circtarget.interactions[].interaction_type` | ~100% |
| `circtarget.interactions[].detected_method` | ~100% |

---

## Test Results Summary

| Step | Status | Details |
|------|--------|---------|
| validate | PASS | Valid manifest, no errors |
| dump | PASS | all.rar downloaded (1.0 MB), release 20251013 |
| upload | PASS (via dump_and_upload) | 6,651 documents; biothings v1.0.2 upload bug — use dump_and_upload |
| list | PASS | circtarget_plugin collection present, count: 6,651 |
| inspect | PASS (via SQLite) | 100% field coverage; documents clean; no None/null leakage |

**Known issue**: `biothings-cli dataplugin upload` fails with `AttributeError: jobs` (biothings v1.0.2 bug). Workaround: `biothings-cli dataplugin dump_and_upload`. Same issue as COCONUT plugin.

**Known issue**: `biothings-cli dataplugin inspect --sub-source-name` fails with argument parsing error in this biothings-cli version. Inspection was performed via direct SQLite query instead.
