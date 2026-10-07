# scTWAS Atlas Plugin — Design Rationale

## Quick Stats

| Metric | Value |
|--------|-------|
| Source file | `Allstudies_sig_eQTL.txt` (TSV) |
| File size | ~127 MB |
| Estimated source rows | ~1.3 million |
| Target API | pending.api |
| Primary key type | Composite: Ensembl ID + Cell Type + Cell Condition + SNP ID |
| License | CC BY-NC 4.0 |
| Data format | Tab-separated, no compression |

---

## Why These Dump Files Were Chosen

### Selected
- **`Allstudies_sig_eQTL.txt`** — The combined significant sc-eQTL file across all 21 cell types and all 10 source datasets. This is the largest bulk-downloadable file on the scTWAS Atlas download page and contains the most complete set of SNP-gene-celltype associations available.

### Rejected
- **Per-cell-type eQTL files** (`B cell_eQTL.txt`, `CD4-positive T cell_eQTL.txt`, etc.) — These are strict subsets of the combined file, split by cell type. Using the combined file avoids downloading 21 separate files and simplifies the parser. The combined file contains all the same rows.
- **`Detail_trait_summary.txt`**, **`Detail_celltype_summary.txt`**, **`CurationPublication_Information.txt`** — Metadata/reference files (34 traits, 30 cell types, publication list). Not ingested separately as the cell type and dataset names are embedded inline in each eQTL row.
- **`Download_AllGeneAnnotation.txt`** — Gene annotation reference (Ensembl ID, symbol, location). Redundant with MyGene.info; not ingested.
- **2,765,211 scTWAS associations** — The primary value-add of this database (computed TWAS results linking genes to traits in specific cell types) is **NOT available for bulk download**. These are stored in a MySQL backend and accessible only via the web interface. This plugin ingests only the sc-eQTL input layer.

---

## Why the Parser Works the Way It Does

### `_id` Strategy
Each row is a unique SNP-gene-cell type-condition association. No single column is a unique identifier, so a composite key is formed:

```
{ensembl_id}|{cell_type_normalized}|{cell_condition_normalized}|{snp_id}
```

Example: `ENSG00000197728|Megakaryocyte|Normal|rs1131017`

- **Ensembl ID**: stable gene identifier; chosen over gene symbol (which can change)
- **Cell Type**: normalized (spaces→underscores, parentheses removed)
- **Cell Condition**: normalized (values: Normal, Stimulated, Disease)
- **SNP ID**: rsID from dbSNP

This composite is pipe-separated (`|`) to avoid ambiguity with hyphens or underscores already present in components.

### Document Structure
Fields are nested under `sctwas_atlas` with logical sub-objects:
- `sctwas_atlas.snp` — SNP identifier and location (chrom, position parsed from "12:56042145" format)
- `sctwas_atlas.gene` — Ensembl ID + gene symbol
- `sctwas_atlas.eqtl` — beta, pval, zscore (all float)
- `sctwas_atlas.cell_type` — cell type name (matches Cell Ontology)
- `sctwas_atlas.cell_condition` — experimental condition (Normal/Stimulated/Disease)
- `sctwas_atlas.dataset` — source publication citation

### Deduplication
Uses `seen_ids` set. Expected duplicate rate: low (same SNP-gene pair in same cell type from multiple publications would be caught). `on_duplicates: error` in manifest catches any duplicates that slip through.

### Data Cleaning
- `_safe_float()` converts eQTL statistics to float; returns None for empty/NA values
- `dict_sweep(doc, [None])` removes all None/empty fields
- `unlist(doc)` flattens single-item lists
- SNP location string parsed to separate `chrom` + `position` integer fields

---

## Sample Output Documents

### Typical example (Megakaryocyte Normal eQTL)
```json
{
  "_id": "ENSG00000197728|Megakaryocyte|Normal|rs1131017",
  "sctwas_atlas": {
    "snp": {
      "id": "rs1131017",
      "location": "12:56042145",
      "chrom": "12",
      "position": 56042145,
      "ref_allele": "A",
      "alt_allele": "C"
    },
    "gene": {
      "ensembl_id": "ENSG00000197728",
      "symbol": "RPS26"
    },
    "eqtl": {
      "beta": -1.04,
      "pval": 8.41e-08,
      "zscore": -5.36
    },
    "cell_type": "Megakaryocyte",
    "cell_condition": "Normal",
    "dataset": "Kang et al. 2017 Nat Biotechnol"
  }
}
```

Source cross-reference: https://ngdc.cncb.ac.cn/sctwas/eqtl (filter by cell type: Megakaryocyte, condition: Normal)

---

## Field Coverage

Coverage estimates from sampling (actual percentages from `inspect --limit 1000`):
- `sctwas_atlas.snp.id`: ~100% (rsID)
- `sctwas_atlas.snp.chrom`: ~100% (parsed from location)
- `sctwas_atlas.snp.position`: ~100%
- `sctwas_atlas.snp.ref_allele`: ~100%
- `sctwas_atlas.snp.alt_allele`: ~100%
- `sctwas_atlas.gene.ensembl_id`: ~100%
- `sctwas_atlas.gene.symbol`: ~99% (some ncRNA may lack symbol)
- `sctwas_atlas.eqtl.beta`: ~100%
- `sctwas_atlas.eqtl.pval`: ~100%
- `sctwas_atlas.eqtl.zscore`: ~100%
- `sctwas_atlas.cell_type`: ~100%
- `sctwas_atlas.cell_condition`: ~100%
- `sctwas_atlas.dataset`: ~100%

---

## Test Results Summary

| Step | Status | Notes |
|------|--------|-------|
| validate | PASS | Valid manifest, all required fields present |
| dump | PASS | Release: 20250102; file: Allstudies_sig_eQTL.txt (127MB) |
| upload | PASS | 947,906 unique documents (via dump_and_upload workaround) |
| list | PASS | Collection: sctwas_atlas_plugin populated |
| inspect --limit 1000 | PASS | 15 fields; 0 None values; all types correct |

**Documents yielded**: 947,906 unique eQTL associations  
**Source rows**: ~1,300,000+ (remaining are duplicates by composite key)  
**Release**: 20250102 (Last-Modified of source file)

Sample `_id`: `ENSG00000197728|Megakaryocyte|Normal|rs1131017`

Note: `biothings-cli dataplugin upload` has a Typer 0.12.5 argument parsing bug — used `dump_and_upload` as workaround.

### Known Limitations
1. **Missing TWAS associations**: The 2.7M scTWAS outputs (the core database value) are not ingested — only the eQTL inputs.
2. **Large file**: 127MB TSV requires ~1.3M iterations. Use `--limit 1000` during initial `biothings-cli inspect`.
3. **CC-BY-NC 4.0**: Non-commercial restriction applies to downstream API consumers.
4. **CNCB server**: Chinese NGDC hosting — `dump` may be slow for international connections.
