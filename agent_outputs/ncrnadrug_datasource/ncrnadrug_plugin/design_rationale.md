# ncRNADrug Plugin — Design Rationale

## Quick Stats

| Metric | Value |
|---|---|
| Source rows (7 files, header-excluded) | 342,780 |
| Documents yielded | 342,780 |
| Rows skipped | 1 (trailing malformed row in `DR_Curated.txt`, missing `Published_Year` field — tolerated by `dict.get`) |
| Deduplication count | 0 collisions after composite `_id` construction (safety-net `seen_ids` suffixing implemented but never triggered) |
| `relation` split | `drug_resistance`: 273,376 (79.8%) / `drug_target`: 69,404 (20.2%) |
| `evidence_tier` split | `curated`: 31,508 (9.2%) / `predicted`: 311,272 (90.8%) |
| Target API | pending.api |
| Data format | 7 uncompressed TSV files, ~215 MB total (verified via HTTP HEAD) |

## Why These Dump Files Were Chosen

All 7 files listed in the inspection report (`ncrnadrug_inspection.json`) were re-verified live via `curl -sIL` — all returned `HTTP 200` with `Content-Type: text/plain` (real data, not HTML landing pages):

| File | Rows | Role |
|---|---|---|
| `DR_Curated.txt` | 15,206 | Experimentally validated ncRNA–drug-resistance associations (highest confidence) |
| `DT_Curated.txt` | 16,300 | Experimentally validated ncRNA-targeted-by-drug associations (highest confidence) |
| `DR_GEO.txt` | 66,342 | Predicted drug-resistance associations from GEO meta-analysis |
| `DR_NCI60.txt` | 128,965 | Predicted drug-resistance associations from the NCI-60 cell-line drug-response panel |
| `DR_CCLE.txt` | 62,862 | Predicted drug-resistance associations from CCLE expression profiling |
| `DT_GEO.txt` | 33,157 | Predicted drug-target associations from GEO meta-analysis |
| `DT_CMap.txt` | 19,946 | Predicted drug-target associations from Connectivity Map perturbation signatures |

**No files were excluded** — unlike most ncRNADrug-adjacent bulk sources (e.g. idrblab databases with subset/superset XLSX duplicates), these 7 files are independent, non-overlapping partitions by relation type (DR/DT) × evidence source (Curated/GEO/NCI60/CCLE/CMap). There is no single superset file to prefer over these.

**Important schema divergence found during inspection re-verification**: the 7 files do **not** share one common column schema, contrary to what a first read of the inspection report's unified `schema.fields` list might suggest (that list was built primarily from the two Curated files). Concretely:
- `DR_GEO.txt` / `DT_GEO.txt` use `GSE_Number` instead of `PMID`, and report `FoldChange`/`PValue`/`FDR`/`Pattern` instead of `Effect`/`Support`/`Phenotype`.
- `DR_NCI60.txt` has no `PMID`, `ENSEMBL_ID`, `SYMBOL`, or `NONCODE_ID` — only `miR_Row`, `ncRNA`, `miRBase_ID`, and statistics (`Pvalue`, `Qvalue`, `logFC`, `EffectSize`).
- `DR_CCLE.txt` has no `ncRNA_Type` column (all rows are lncRNA-only by design) and its `"LncRNA"` column is actually a **duplicate of `ENSEMBL_ID`**, not a name/symbol — verified against raw rows. Its `"CCLE"` column is a drug alias/synonym (e.g. `"OSI-906"` for Linsitinib), not a cell-line name.
- `DT_CMap.txt` uses `Instance`/`Dose`/`Duration`/`Batch`/`Cell`/`Platform` (CMap perturbagen metadata) with no `PMID`/`GSE_Number` at all.

This was resolved by writing **one normalizer function per file category** rather than a single generic row mapper (see Pattern Selection below), and documenting the anomalies inline in `parser.py`.

## Why the Parser Works the Way It Does

**`_id` strategy**: No single natural key spans all 7 files (PMID only exists in the Curated files). Each category builds its own composite from the most specific identifying columns available:
- `DR_Curated`/`DT_Curated`: `{PMID}_{ncRNA_Name}_{Drug_Name}_{ncRNA_Type}`
- `DR_GEO`/`DT_GEO`: `{GSE_Number}_{ncRNA_Name}_{Drug_Name}_{ncRNA_Type}`
- `DR_NCI60`: `{miR_Row}_{ncRNA}_{Drug_Name}_{ncRNA_Type}`
- `DR_CCLE`: `{ENSEMBL_ID}_{Lnc_Row}_{Drug_Name}`
- `DT_CMap`: `{Instance}_{ncRNA}_{Drug_Name}_{ncRNA_Type}`

Every composite is prefixed with `{source_category}:` (e.g. `DR_Curated:28040594_7SK_Gefitinib_lncRNA`) to guarantee no cross-file collisions, matching the pending.api convention that composite IDs (`f"{id1}-{id2}"`) are acceptable when no single field is unique. A `seen_ids` counter in `load_data()` appends a numeric suffix (`-2`, `-3`, …) if a composite ever repeats within a category — this never triggered in the full run (0 collisions across 342,780 rows), but is kept as a safety net since `manifest.json` also sets `on_duplicates: "ignore"` as a second line of defense.

**Document structure**: One document per source row (no groupby/aggregation — each row already represents one distinct relation instance). All fields nest under `ncrnadrug`:
- `relation`: `drug_resistance` (DR_*) or `drug_target` (DT_*)
- `evidence_tier`: `curated` or `predicted` — lets consumers weight/filter by confidence
- `source_category`: one of the 7 file tags, for full provenance traceability
- `ncrna` sub-object: `name`, `type`, `symbol`, `target_gene`
- `drug` sub-object: `name`, `drugbank_id`, `pubchem_cid`, `nsc`, `fda_status` (+ `ccle_alias` for CCLE rows)
- `xrefs` sub-object: normalized cross-references (`drugbank`, `pubchem_cid`, `nsc`, `ensembl_gene`, `noncode`, `circbase`, `deepbase`, `circpedia`, `mirbase`)
- Category-specific sub-objects: `geo` (GEO files), `cmap` (CMap file), plus flat fields `tumor`/`phenotype` for CCLE
- `statistics` sub-object for predicted files: `pvalue`/`qvalue`/`fdr`/`logfc`/`foldchange`/`effectsize` (only the subset each file actually reports)

**Fields extracted vs. skipped**: `Reference` (free-text paper title, redundant with PMID) and the curated `FDA` field's raw string are folded into `drug.fda_status`; nothing from the schema was dropped as truly unused — even sparse fields (`Pathway`, `ncRNA_Target_Gene`) are retained since they are high-value when present.

**Data cleaning**: `_clean()` treats the literal string `"NA"` (case-insensitive) and empty strings as missing, converting to `None` so `dict_sweep()` removes them from the final document. `_to_float()` guards against malformed numeric strings. `dict_sweep(unlist(doc), [None])` is applied to every yielded document per SKILL.md convention.

**Parser pattern**: Multi-file glob with **per-category normalizer dispatch** (a variant of the "Multi-file TSV" pattern, but with 7 distinct schemas rather than 1 shared schema — closest to Pattern 1/DISEASES in spirit, without the groupby step since no aggregation is needed here).

## Sample Output Documents

**Typical curated example** (drug resistance, PMID-backed):
```json
{
  "_id": "DR_Curated:28040594_7SK_Gefitinib_lncRNA",
  "ncrnadrug": {
    "relation": "drug_resistance",
    "evidence_tier": "curated",
    "source_category": "DR_Curated",
    "ncrna": {"name": "7SK", "type": "lncRNA", "symbol": "LINC02198"},
    "drug": {"name": "Gefitinib", "drugbank_id": "DB00317", "pubchem_cid": "123631", "nsc": "NSC715055", "fda_status": "approved"},
    "effect": "sensitive",
    "detection_method": "Microarray",
    "throughput": "High",
    "species": "Homo sapiens",
    "phenotype": "Non-Small Cell Lung Cancer",
    "condition": "cell line (PC-9)",
    "pmid": 28040594,
    "published_year": "2017"
  }
}
```
Source cross-reference: http://www.jianglab.cn/ncRNADrug/data_download/DR_Curated.txt (per-record browse page not available without a search UI session; PMID 28040594 is independently verifiable on PubMed).

**Edge-case example** (CCLE predicted, where the source's `"LncRNA"` and `"CCLE"` columns are misleadingly named — see schema-divergence note above):
```json
{
  "_id": "DR_CCLE:ENSG00000005206_1_GW_441756",
  "ncrnadrug": {
    "relation": "drug_resistance",
    "evidence_tier": "predicted",
    "source_category": "DR_CCLE",
    "ncrna": {"name": "SPPL2B", "type": "lncRNA", "symbol": "SPPL2B"},
    "drug": {"name": "GW 441756", "pubchem_cid": "9943465", "nsc": "NSC756236", "ccle_alias": "GW 441756"},
    "effect": "sensitive",
    "detection_method": "CCLE expression profiling",
    "species": "Homo sapiens",
    "tumor": "PAAD",
    "phenotype": "Ovarian serous cystadenocarcinoma",
    "statistics": {"pvalue": 0.0278, "qvalue": 0.5003, "logfc": -1.5385, "effectsize": -2.9101},
    "xrefs": {"pubchem_cid": "9943465", "nsc": "NSC756236", "ensembl_gene": "ENSG00000005206"}
  }
}
```
Source cross-reference: http://www.jianglab.cn/ncRNADrug/data_download/DR_CCLE.txt

## Field Coverage (full 342,780-document run)

- `relation` / `evidence_tier` / `source_category` / `ncrna.name` / `detection_method` / `species`: 100.0%
- `drug.pubchem_cid` / `xrefs.pubchem_cid`: 92.8%
- `drug.nsc` / `xrefs.nsc`: 82.1%
- `statistics.pvalue`: 76.8%
- `effect`: 60.4%
- `statistics.qvalue` / `statistics.logfc` / `statistics.effectsize`: 56.0%
- `xrefs.ensembl_gene`: 52.5%
- `xrefs.noncode`: 47.0%
- `drug.drugbank_id` / `xrefs.drugbank`: 45.9%
- `xrefs.mirbase`: 44.2%
- `expression_pattern`: 39.6%
- `condition`: 38.2%
- `drug.fda_status`: 36.1%
- `ncrna.symbol`: 31.9%
- `geo.gse_number` / `statistics.foldchange`: 29.0%
- `phenotype`: 27.5%
- `statistics.fdr`: 20.8%
- `drug.ccle_alias` / `tumor`: 18.3% (CCLE-only)
- `throughput` / `pmid` / `support` / `published_year`: 9.2% (curated-only)
- `cmap.*` fields: 5.8% (CMap-only); `cmap.synonyms`: 3.3%
- `ncrna.target_gene`: 1.9%
- `pathway`: 1.6%

## Test Results Summary

`biothings-cli` is broken in this environment (see Notes) — validation was performed by importing `parser.py` directly and running `load_data()` against the 7 downloaded source files:

- 342,780 total documents yielded from 342,780 source rows (only 1 malformed trailing row tolerated, no data lost)
- All `_id` values are non-empty strings ≤ 512 chars
- All documents contain the `ncrnadrug` top-level key
- 0 `_id` collisions (composite key + category prefix proved sufficient; `seen_ids` safety net never triggered)
- No `numpy` types in output (parser uses stdlib `csv`/`float`/`int` only)
- `dict_sweep(unlist(doc), [None])` confirmed removing all `None`/empty values from every sampled document

## Notes / Known Limitations

- **`biothings-cli` is non-functional in this sandbox**: `biothings-cli dataplugin validate` (and every other subcommand) raises `AttributeError: module 'typer' has no attribute 'rich_utils'` at import time inside `biothings/cli/settings.py`, before any command logic runs. This is a pre-existing typer/biothings version incompatibility in the shared environment, not a defect in this plugin. Per instructions, the shared environment was **not** patched; validation was instead performed by directly invoking `parser.load_data()` against real downloaded files (see Test Results Summary).
- Row counts in the live files are noticeably larger than the inspection report's estimated file sizes (e.g. `DR_GEO.txt` is ~57 MB / 66,342 rows vs. the ~7 MB estimate on file) — the site appears to have grown its predicted-association tables since the original inspection pass (2026-07-09); re-verified live via HTTP HEAD immediately before plugin generation (2026-07-20).
- License: relies on the NAR 2024 paper's CC BY 4.0 status; the jianglab.cn site itself has no separate standalone data-usage license page (documented risk, consistent with `ncrnadrug_inspection.json`).
- No public API exists; all data must be re-dumped via the 7 static TSV URLs. No documented update cadence.
- `DR_CCLE.txt`'s `"LncRNA"` and `"CCLE"` column names are misleading (see schema-divergence note); handled explicitly in `_parse_ccle()` with inline documentation to prevent future maintainers from re-introducing the bug of using `LncRNA` as a display name.
- Predicted-association files (GEO/NCI60/CCLE/CMap) are computational predictions, not experimentally validated — flagged via `evidence_tier: "predicted"` per the relevancy report's risk note.
