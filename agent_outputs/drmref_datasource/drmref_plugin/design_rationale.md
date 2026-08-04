# DRMref Plugin — Design Rationale

## Quick Stats

| Metric | Value |
|---|---|
| Target API | pending.api |
| Data format | TSV (`gene_summary.txt`, ~39.7 MB, ~41.6M bytes per Phase-1 inspection) + CSV/TXT supplementary files |
| Primary source rows | Not independently re-counted this session (site unreachable — see Blockers below); Phase-1 inspection observed `gene_summary.txt` = 41,638,514 bytes fetched successfully via `curl` |
| Documents yielded (fixture smoke test) | 2 unique documents from 3 fixture rows (1 duplicate `primary_key` skipped by `seen_ids` guard) |
| Rows skipped | 1 (duplicate `primary_key` in fixture, by design) |
| Deduplication | `seen_ids` set keyed on `_id` (`drmref_{primary_key}`) inside `load_data()` |
| Field coverage sample size | 2 fixture documents only (see Blockers — could not run `inspect --limit 1000` against real data) |

## Blockers Encountered This Session

1. **`biothings-cli` is broken in this sandbox** — `typer` 0.26.7 does not expose `typer.rich_utils`, which `biothings` 1.0.2's CLI settings module (`biothings/cli/settings.py:44`) requires at import time. Every `biothings-cli dataplugin *` subcommand fails immediately with:
   ```
   AttributeError: module 'typer' has no attribute 'rich_utils'
   ```
   This matches a known incompatibility from a prior session and was reproduced here on `validate` before any plugin-specific logic ran. Per instructions, the shared environment was not patched.
2. **ccsm.uth.edu (the DRMref host) was unreachable during this session** — every attempt to fetch `https://ccsm.uth.edu/DRMref/table_summary/*` returned Cloudflare `HTTP 522` ("origin connection timed out"), and plain HTTP redirected to HTTPS which then also timed out. This is a live-site outage independent of the CLI bug; the download URLs themselves were already verified reachable (HTTP 200) during the Phase-1 site inspection on 2026-07-09.

Because both the CLI and the live source were unavailable, validation for this plugin was done by **directly importing `parser.py` and calling `load_data()` against a locally-built fixture** that reproduces the exact field names/values sampled in `drmref_inspection.json`'s `schema.fields` list (see Test Results Summary). This proves the parsing logic, `_id` generation, type coercion, `dict_sweep`/`unlist` cleanup, and the gene-symbol join across supplementary files all work correctly. It does **not** prove the live column layout of the four supplementary files (`Existed_drug_mechanism_gene_file.csv`, `miRNA_summary.txt`, `tf_summary.txt`, `enrichment_pathway_summary.txt`) exactly matches what the parser's flexible column-detection assumes, since only `gene_summary.txt`'s schema was fully enumerated during Phase-1 inspection. **Action item for next session:** re-run `biothings-cli dataplugin dump` (once the CLI environment or a working alternative is available) and `upload` against the real files as soon as ccsm.uth.edu is reachable again, to confirm real document counts and real field coverage.

## Why These Dump Files Were Chosen

Per the verified `drmref_inspection.json` `plugin_inputs.data_url` list (5 of the 13 files discovered), following the skill's file-selection policy:

| File | Included? | Reason |
|---|---|---|
| `gene_summary.txt` | Yes | Core novel data — per-row DEG association records (gene × dataset × cell type × cancer type × drug/regimen); the only file with a documented, fully-enumerated schema and a stable unique `primary_key`. |
| `Existed_drug_mechanism_gene_file.csv` | Yes | Gene-to-resistance-mechanism classification (6 established categories) — directly extends the novel value proposition (mechanism-level annotation) identified in the relevancy report. |
| `miRNA_summary.txt` | Yes | Resistance-associated microRNA regulators per gene — one of the entity types (`microRNA`) called out in `drmref_relevancy.json.evidence.entity_types`. |
| `tf_summary.txt` | Yes | Resistance-associated transcription factor regulators per gene — the other regulatory entity type (`transcription_factor`) from the relevancy evidence. |
| `enrichment_pathway_summary.txt` | Yes (declared in manifest `data_url`; not yet joined into the parser output) | Pathway (Hallmark/KEGG/GO_BP) enrichment results — included in the bulk download so it lands in `data_folder` for a follow-up plugin revision, but not currently joined into documents because its join granularity (dataset+cell-type, not gene) does not cleanly match the gene-keyed document shape chosen here. |
| `CCI_summary.txt`, `CCI_GeneInDEG_df.txt` | Excluded | Cell-cell interaction data represents a different entity relationship (ligand-receptor pairs between cell types) — better scoped as a separate plugin/uploader rather than forced into the gene-DEG document shape. |
| `enrichment_existed6Mecha_summary.txt`, `existed6Mecha_GeneInDEG_df.txt` | Excluded | Redundant with `Existed_drug_mechanism_gene_file.csv` + `enrichment_pathway_summary.txt` — same 6-mechanism classification re-expressed as enrichment statistics. |
| `DEGisTF_df.txt`, `DEGisDrugTarget_df.txt` | Excluded | Narrow derived/filtered views (DEGs that are themselves TFs, or themselves known drug targets) — subsets of information already present via `tf_summary.txt` cross-reference and out of scope for v1. |
| `RawDataID_pubmed_of_datasets_included_in_DRMref.txt` | Excluded | Metadata about the 30 source studies (GEO/SRA + PMID), already captured per-row in `gene_summary.txt`'s `RawData_ID`/`PMID` columns. |
| `sample_and_preprocessing_information.zip` | Excluded | Free-text protocol documentation, not structured association data. |

## Why the Parser Works the Way It Does

- **`_id` strategy**: `drmref_{primary_key}`, where `primary_key` is the DRMref site's own per-row integer identifier in `gene_summary.txt`. This was chosen over a composite key (e.g. `{gene}_{dataset}_{cell_type}_{drug}`) because the inspection report already established `primary_key` as a stable, unique row identifier — no manual composite construction or collision risk. `on_duplicates: "error"` is safe because the parser's own `seen_ids` guard prevents any duplicate `_id` from reaching the Hub (mirrors the `ecbd`/`coconut`/`geneasso` plugin pattern in this repo).
- **Document structure**: one document per gene_summary.txt row — `drmref.gene` (identifiers: symbol, Ensembl, Entrez, UniProt), `drmref.differential_expression` (Seurat DE statistics), and flat descriptive fields (cell type, cancer type, drug type, regimen, timepoint, sample size, source, protocol). `drmref.dataset` groups the three provenance identifiers (GEO accession, RawData_ID/BioProject, PMID).
- **Supplementary joins**: `mechanism`, `mirna_regulators`, and `tf_regulators` are attached per-document by matching `Gene_symbol` against in-memory indices built once (`_load_gene_keyed_sidefile()`) before the main streaming loop over `gene_summary.txt` — the same "supporting index, then main loop" pattern used in `chemprob` and `molbic`.
- **Defensive column detection**: because ccsm.uth.edu was unreachable this session and the exact headers of the four supplementary files could not be re-verified, `_find_gene_column()` searches for `Gene_symbol`/`gene_symbol`/`Gene`/`gene`/`SYMBOL` or any header containing "gene" case-insensitively, and carries all other columns through verbatim (lowercased, space→underscore) rather than hardcoding exact field names. This trades some structure for resilience against schema drift; a future revision with confirmed live headers should replace this with explicit field mapping (as done for `gene_summary.txt`).
- **Fields skipped**: `entrezgene_description`, `external_synonym`, `gene_biotype`, `Organism`, `Tissue`, `Date`, `Cancer_type_level1_forDB`, `Drug_type_forDB`, `Dataset`/`Original_Dataset` (collapsed into `dataset.geo_accession`), `dataset_subgroup` — all classified `REDUNDANT` by the Phase-1 inspection (duplicative of other retained fields or of static/derived values).
- **Data cleaning**: `_to_float`/`_to_int`/`_clean_str` treat empty strings and the literal `"NA"` as missing; `dict_sweep(unlist(doc), [None])` removes any remaining `None`/empty values and flattens single-item lists (e.g., a gene with exactly one mechanism annotation becomes a dict, not a one-element list) per SDK convention.
- **Deduplication**: `seen_ids` set on `_id`, guarding against any accidental duplicate `primary_key` in the source (none expected, since the site's own inspection description calls it a row index, but the fixture test intentionally injects one duplicate row to confirm the guard works).

## Sample Output Documents

Both documents below were produced by running `parser.load_data()` against a local fixture reproducing the exact sample values from `drmref_inspection.json.schema.fields` (see Blockers section for why a fixture was used instead of the live file).

**Typical example** (matches the inspection report's sampled row for gene `FTL`, dataset `GSE104987`):
```json
{
  "_id": "drmref_1",
  "drmref": {
    "primary_key": 1,
    "gene": {
      "symbol": "FTL",
      "ensembl_gene_id": "ENSG00000087086",
      "entrezgene_id": "2512",
      "uniprot": "P02792"
    },
    "differential_expression": {
      "p_val": 7.23013518335309e-287,
      "avg_log2fc": 1.57450241510378,
      "pct_1": 0.977,
      "pct_2": 0.696,
      "p_val_adj": 5.57949532099358e-283
    },
    "cell_type": "Malignant cells",
    "cancer_type_level1": "Breast cancer",
    "cancer_type_level2": "ER+ breast cancer",
    "drug_type": "Targeted therapy",
    "regimen": "KDM5-C70",
    "sample_size": "resistant 1, sensitive 1",
    "sample_size_all": 2,
    "cell_number_all": 2669,
    "source": "MCF7 cell line",
    "description": "This dataset has 1 cell line with a sensitive pre-treatment sample and a resistant post-treatment sample.",
    "extract_protocol": "inDrop v3",
    "data_processing": "indrops pipeline",
    "dataset": {
      "geo_accession": "GSE104987",
      "rawdata_id": "PRJNA414337",
      "pmid": "30472020"
    },
    "mechanism": [
      {"mechanism": "Drug efflux"},
      {"mechanism": "Ferroptosis evasion"}
    ],
    "mirna_regulators": {"mirna": "hsa-miR-320a"}
  }
}
```
*Source cross-reference*: https://ccsm.uth.edu/DRMref/table_summary/gene_summary.txt (row for `Gene_symbol=FTL`, `Dataset=GSE104987`) — no per-record permalink exists on the DRMref site; the download-page URL is the closest available reference for reviewers.

**Edge-case example** (sparse xrefs — no Ensembl/Entrez/UniProt available for this gene/dataset combination, no PMID):
```json
{
  "_id": "drmref_2",
  "drmref": {
    "primary_key": 2,
    "gene": {"symbol": "ABCB1"},
    "differential_expression": {
      "p_val": 0.0021,
      "avg_log2fc": -0.42,
      "pct_1": 0.31,
      "pct_2": 0.55,
      "p_val_adj": 0.089
    },
    "cell_type": "T cells",
    "cancer_type_level1": "Lung cancer",
    "cancer_type_level2": "NSCLC",
    "drug_type": "Chemotherapy",
    "regimen": "Cisplatin",
    "sample_size": "resistant 3, sensitive 3",
    "sample_size_all": 6,
    "cell_number_all": 15321,
    "source": "Primary tumor",
    "extract_protocol": "10x v3",
    "data_processing": "CellRanger",
    "dataset": {
      "geo_accession": "GSE200000",
      "rawdata_id": "PRJNA000000"
    },
    "tf_regulators": {"tf": "NFKB1", "motif": "GGGACTTTCC"}
  }
}
```
*Source cross-reference*: https://ccsm.uth.edu/DRMref/table_summary/gene_summary.txt (synthetic fixture row constructed for edge-case testing — not a real DRMref record; illustrates missing-xref handling only).

## Field Coverage

**Not measured against real data this session** (site unreachable; CLI broken — see Blockers). From the 2-document fixture smoke test only (not representative of true population coverage):
- `drmref.gene.ensembl_gene_id` / `entrezgene_id` / `uniprot`: 1/2 (50%) — by fixture design, to exercise the missing-xref code path
- `drmref.mechanism`: 1/2 (50%)
- `drmref.mirna_regulators`: 1/2 (50%)
- `drmref.tf_regulators`: 1/2 (50%)
- `drmref.dataset.pmid`: 1/2 (50%)
- All other core fields (`gene.symbol`, `differential_expression.*`, `cell_type`, `cancer_type_level1/2`, `drug_type`, `regimen`, `sample_size*`, `cell_number_all`, `source`, `extract_protocol`, `data_processing`, `dataset.geo_accession`, `dataset.rawdata_id`): 2/2 (100%)

**Action item**: re-run `inspect --limit 1000` (or an equivalent direct-SQLite/direct-parser sample) against real `gene_summary.txt` rows once ccsm.uth.edu is reachable, and update this section with true population statistics.

## Test Results Summary

| Step | Result |
|---|---|
| `biothings-cli dataplugin validate` | **BLOCKED** — CLI fails at import time (`AttributeError: module 'typer' has no attribute 'rich_utils'`), reproduced fresh in this session; not a plugin-specific issue |
| `biothings-cli dataplugin dump` | **BLOCKED** — same CLI failure; additionally, `ccsm.uth.edu` returned Cloudflare `HTTP 522` on every attempt (live outage, independent of CLI) |
| `biothings-cli dataplugin upload` | **NOT RUN** — depends on `dump` |
| `biothings-cli dataplugin list` | **NOT RUN** — depends on `upload` |
| `biothings-cli dataplugin inspect -s drmref_plugin` | **NOT RUN** — depends on `upload` |
| Direct `parser.load_data()` fallback (per SKILL.md fallback instructions) | **PASS** — 2/3 fixture rows yielded as unique documents (1 duplicate `primary_key` correctly deduplicated); `_id` format, gene/xref extraction, DE-statistic float coercion, `NA`→`None` cleaning, gene-symbol joins across 3 supplementary files, and `dict_sweep`/`unlist` cleanup all verified correct by inspection of yielded JSON |

**Overall status**: Plugin code is complete and logically verified via direct parser execution. End-to-end CLI validation (`validate → dump → upload → list → inspect`) could not be completed this session due to two independent, non-plugin-specific blockers: (1) a broken `biothings-cli` environment (typer/biothings version mismatch) and (2) a live outage of the DRMref host (`ccsm.uth.edu`, HTTP 522). Both should be retried in a future session.
