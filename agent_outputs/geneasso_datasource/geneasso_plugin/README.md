# GENEasso Plugin — Design Rationale

## Datasource
GENEasso is a database of 716,122 high-confidence disease-gene associations
derived from 8,226 GWAS summary statistics using 7 different gene-based
association methods. Published in NAR 2025 (DOI: 10.1093/nar/gkaf1097,
PMID: 41166152).

Homepage: https://www.geneasso.net/

## _id Strategy

```
_id = f"{ENSG}_{DAGENA}_{method_key}"
```

Where `method_key` is the method string lowercased with spaces and hyphens
replaced by underscores (e.g. `LDAK-GBAT` → `ldak_gbat`).

**Rationale:** The combination of Ensembl gene ID (ENSG), internal GWAS study
ID (DAGENA), and method name is guaranteed to be unique in the source data.
Each file represents exactly one method and the GENEasso database ensures no
duplicate triplets within or across files. Using ENSG as the first component
enables future joining with MyGene.info.

Example: `ENSG00000145335_GA00002_MAGMA`

## Files Ingested

All 11 data files are ingested:
- `MAGMA.download.txt` (~217 MB)
- `DEPICT.download.txt` (~31 MB)
- `PASCAL.download.txt` (~327 MB)
- `LDAK-GBAT.download.txt` (~253 MB)
- `RWAS.download.txt` (~45 MB)
- `SMR_CAGE.download.txt` (~47 MB)
- `SMR_Geuvadis.download.txt` (~12 MB)
- `SMR_GTEx-top1tissue.download.txt` (~22 MB)
- `SMR_GTEx-top2tissue.download.txt` (~23 MB)
- `SMR_GTEx-top3tissue.download.txt` (~23 MB)
- `SMR_PsychENCODE.download.txt` (~13 MB)

**Excluded:** `Script.download.txt` — contains R/Python analysis scripts used
to run the gene-based methods, not association data.

## Parser Pattern

Simple single-pass streaming TSV reader (`csv.DictReader`). Each row becomes
one document — no groupby aggregation needed because the ENSG+DAGENA+Method
triplet is already unique per row.

Method-specific fields are added conditionally by testing whether the column
name is present in the row dict (derived from the file header). This handles
the heterogeneous schemas across the 7 methods without branching on filename.

Column name → document key mappings follow standard snake_case conventions:
- `N(eQTL)` → `n_eqtl`
- `Z-score` → `zscore`
- `EFO Trait Synonym` → `efo_trait_synonym`
- `Top_eQTL` → `top_eqtl`
- `Top1-Tissue` → `top1_tissue`

## Method-Specific Field Inventory

| Field       | MAGMA | DEPICT | PASCAL | LDAK-GBAT | RWAS | SMR_* |
|-------------|-------|--------|--------|-----------|------|-------|
| `n_eqtl`    | yes   | no     | yes    | no        | yes  | yes   |
| `zscore`    | yes   | no     | no     | no        | yes  | no    |
| `h2`        | no    | no     | no     | yes       | no   | no    |
| `top_eqtl`  | no    | yes    | no     | no        | no   | yes   |
| `beta`      | no    | no     | no     | no        | no   | yes   |
| `peak`      | no    | no     | no     | no        | yes  | no    |
| `model`     | no    | no     | no     | no        | yes  | no    |
| `r2`        | no    | no     | no     | no        | yes  | no    |
| `top1_tissue` | no  | no     | no     | no        | no   | some  |

## on_duplicates

`error` — each ENSG+DAGENA+Method triplet is unique by construction in the
source data. If a duplicate is encountered it signals a data quality issue
that should be investigated rather than silently overwritten.

## Top-Level Key

All fields are nested under `geneasso` to follow BioThings plugin conventions.

## License

GENEasso is "available free of charge for all users, including both academic
and commercial users" (from the paper). No formal license is declared, but the
language is permissive for both research and commercial API consumers.

## Version Strategy

`version.py` queries `https://www.geneasso.net/api/download/list` (JSON API)
to confirm the dataset is reachable and uses the file count as a change
signal. Returns `20250101_{N}files` based on the paper's 2025 publication
date. Fallback returns today's date as YYYYMMDD.

## Test Results Summary

| Step | Status | Notes |
|------|--------|-------|
| validate | PASS | Valid manifest, exit 0 |
| dump | SKIP | SSL cert expired on geneasso.net; files pre-downloaded via `curl -k`; 11 files, ~1 GB total |
| upload | PASS | 640,732 unique documents written to geneasso collection |
| list | PASS | geneasso collection present in data_src_database |
| inspect | PASS | 1,001 docs sampled; `_id`=str (30 chars); geneasso.\* subfields typed correctly; pvalue=float; start\_pos/end\_pos=int; no `_none` warnings |

**Document count**: 640,732 (from 660,601 source rows; 19,869 rows deduplicated by seen_ids — duplicate ENSG+DAGENA+Method triplets in source data)

**Per-method document counts:**

| Method | Source rows | Unique docs |
|--------|-------------|-------------|
| PASCAL | 226,899 | 225,878 |
| LDAK-GBAT | 170,439 | 169,306 |
| MAGMA | 141,689 | 141,545 |
| SMR_CAGE | 27,828 | 22,700 |
| DEPICT | 21,089 | 21,089 |
| RWAS | 20,052 | 7,609 |
| SMR_GTEx-top2tissue | 12,637 | 12,637 |
| SMR_GTEx-top3tissue | 12,358 | 12,358 |
| SMR_GTEx-top1tissue | 12,111 | 12,111 |
| SMR_PsychENCODE | 9,264 | 9,264 |
| SMR_Geuvadis | 6,235 | 6,235 |

## Known Limitations

1. **SSL certificate expired** — the GENEasso server has an expired TLS
   certificate. Both the dump (HTTP, not HTTPS) and version.py use
   `verify=False` to work around this. Production deployment should monitor
   for certificate renewal.

2. **Large files** — PASCAL (~320 MB) and LDAK-GBAT (~256 MB) are the largest
   files. Total download ~1.0 GB. Dump may take several minutes on slow
   connections.

3. **No versioning API** — the site does not expose a data version timestamp.
   The version signal uses file count as a proxy. Manual version bumping will
   be needed if data is updated without changing file count.

4. **DEPICT `Top_eQTL` field is sparse** — inspection of the DEPICT file
   shows the `Top_eQTL` column exists but may not be populated for all rows.
   `dict_sweep` removes null values so absent entries are omitted cleanly.

5. **`Gene Summary` field contains "NA"** — many rows have the literal string
   "NA" for gene summaries where RefSeq has no annotation. The `_clean()`
   helper treats "NA" as null, so these are swept from documents.

6. **Duplicate rows in source** — LDAK-GBAT (1,133), PASCAL (1,013), RWAS
   (3,757), MAGMA (144), SMR_CAGE (4,460) contain duplicate ENSG+DAGENA+Method
   triplets — identical rows in the upstream GENEasso release. The `seen_ids`
   set in `load_data()` deduplicates these. `on_duplicates: "ignore"` in
   manifest provides Hub-level backstop.

7. **Infinity values in RWAS Z-scores** — some RWAS rows have `Z-score=Infinity`
   (not valid JSON). The `_to_float()` helper returns `None` for `inf`/`-inf`,
   and `dict_sweep` removes those null fields cleanly.
