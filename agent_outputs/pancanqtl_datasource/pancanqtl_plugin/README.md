# Design Rationale — PancanQTLv2.0 Plugin

## Quick Stats

| Metric | Value |
|---|---|
| Source rows (this session's representative sample) | 25,463 (across 4 files: 1 per module) |
| Documents yielded | 25,462 |
| Rows skipped | 0 (0 missing SNP/cancer_type/credible_set) |
| Deduplication | 0 collisions across 25,462 composite `_id`s (module-prefixed keys) |
| Target API | pending.api |
| Data format | Gzipped TSV, 4 modules × per-cancer-type files (124 files total in production manifest: 25 fine-mapping + 33×3 for GWAS/drug/immune) |
| Total file size (production, all 124 files) | Not fully downloaded this session — largest single file observed is BRCA eQTL-GWAS at 121 MB; full eQTL-GWAS module alone backs 84,592,135 associations per the paper's Table 1 |

**Sandbox scope note**: `biothings-cli` is broken in this environment (see Test Results Summary below), and the full eQTL-GWAS module totals ~84.6M rows across 33 cancer types (multi-GB uncompressed). Downloading and parsing the entire production dataset was not feasible in this session. Validation was instead performed against one smallest-available file per module (ESCA fine-mapping, DLBC eQTL-GWAS, LAML drug-eQTL, GBM immune-eQTL), each cross-checked against the paper's Table 1 exactly (see Paper vs Reality in `pancanqtl_inspection.json`). `manifest.json` declares the full production file list (124 URLs, all verified to resolve with HTTP 200 / correct gzip content-type); the parser logic is identical regardless of scale (per-row streaming, no full-file buffering), so it is expected to scale correctly to the full dataset on a production Hub run.

## Why These Dump Files Were Chosen

PancanQTLv2.0 publishes four independent modules, each per-cancer-type:

1. **Fine-mapping** (`<CANCER>.cis.susie.txt.gz`) — fine-mapped causal eQTL credible sets (SuSiE), 25 of 33 cancer types (8 excluded by the paper's own methods for sample size ≤100: ACC, CHOL, DLBC, KICH, MESO, READ, UCS, UVM).
2. **eQTL-GWAS** (`<CANCER>.eQTL-GWAS.xls.gz`) — eQTL/GWAS-risk-locus linkage disequilibrium associations, all 33 cancer types.
3. **Drug-eQTL** (`<CANCER>.drug-eQTL.xls.gz`) — eQTL/drug-response associations (from DrVAEN and cancerRxTissue), all 33 cancer types.
4. **Immune-eQTL** (`<CANCER>.immune-eQTL.xls.gz`) — eQTL/immune-cell-infiltration associations (from ImmuneCellsGSVA, ImmuCellAI, TIMER, CIBERSORT), all 33 cancer types.

All four modules were selected for ingestion — none are supersets/subsets of each other; each captures a genuinely distinct relation type (variant→expression-causality, variant→GWAS-trait linkage, variant→drug-response, variant→immune-infiltration) that the paper explicitly frames as a separate contribution of the v2.0 update. This matches the file-selection strategy's preference for per-entity-type bundles over a filtered/full superset — there is no single superset file that contains all four relation types.

No third-party mirror was used: all 124 files resolve directly from `hanlaboratory.com/static/PancanQTLv2/Download/` (the datasource's own domain) with no login gate, confirmed via `curl -A "Mozilla/5.0"` HEAD requests returning `content-type: application/x-gzip` (not `text/html`).

One caveat: three of the four modules are served with a misleading `.xls` file extension (`eQTL-GWAS.xls.gz`, `drug-eQTL.xls.gz`, `immune-eQTL.xls.gz`). Byte inspection confirms these are plain tab-delimited text (not binary Excel), so the parser treats all four modules identically as gzipped TSV via `gzip.open(..., "rt")` + `csv.DictReader(f, delimiter="\t")` — no Excel-reading library is used or required.

## Why the Parser Works the Way It Does

**No shared primary key across modules.** Each module has its own column schema and its own row-level granularity (e.g., fine-mapping rows are one-SNP-within-one-credible-set; GWAS rows are one-eQTL-SNP-to-one-GWAS-SNP-to-one-trait; drug/immune rows are one-SNP-to-one-gene-to-one-drug-or-cell-type). Rather than force these into a single per-SNP or per-gene merged record (which would require inventing a join key the source data does not provide), the parser treats **each row as its own document**, tagged with an `association_type` field (`fine_mapping` | `gwas` | `drug` | `immune`) plus normalized `cancer_type` / `gene` / `snp` fields so all four association types remain queryable together under one `pancanqtl` sub-object.

**`_id` strategy**: composite, module-prefixed strings built from the fields that make each row unique within its module:
- `finemap:<Credible_Set>:<RS_id>` — a credible set can contain multiple SNPs, so both are needed.
- `gwas:<CancerType>:<eQTL_SNP>:<eGene>:<GWAS_SNP>:<PUBMEDID>` — an eQTL SNP can link to multiple GWAS SNPs/traits from different publications.
- `drug:<cancer_type>:<SNP>:<gene>:<drug>:<Drug_source>` — one SNP-gene pair can associate with multiple drugs from two different source databases.
- `immune:<cancer_type>:<SNP>:<gene>:<Cell>:<Immune_cell_source>` — analogous to drug, but keyed on immune cell type and source.

A `_make_unique_id()` helper appends a numeric suffix (`-2`, `-3`, ...) in the rare case two rows produce the same composite key within a module — this did not trigger in this session's test data (0 collisions across 25,462 documents) but guards against edge cases in the full production dataset.

**Document structure**: single top-level `pancanqtl` object per document (no nested lists — the granularity is already one relation per row, so there is nothing to group). Numeric fields (`Beta`, `SE`, `P_value`, `FDR`, `R2`, `PIP`, etc.) are coerced from string to `float`/`int` via `_to_float()`/`_to_int()` helpers that return `None` on empty/`NA` values, which `dict_sweep()` then strips.

**Data cleaning**: `dict_sweep(unlist(doc), [None])` applied to every document, per the standard SDK convention, to remove `None`/empty values and flatten any single-item lists.

## Sample Output Documents

**Example 1 — fine_mapping (typical)**:
```json
{
  "_id": "finemap:ESCA_ERAP2_cis_L1:rs2927608",
  "pancanqtl": {
    "association_type": "fine_mapping",
    "cancer_type": "ESCA",
    "gene": "ERAP2",
    "snp": "rs2927608",
    "variant": "5_96252432_G_A",
    "chr": "5",
    "position": 96252432,
    "credible_set": "ESCA_ERAP2_cis_L1",
    "credible_set_size": 2,
    "pip": 0.45516787575771
  }
}
```
Source cross-reference: [PancanQTLv2.0 Fine-mapping module, ESCA](https://hanlaboratory.com/PancanQTLv2/Finemapping.html) (search cancer type ESCA, gene ERAP2, or SNP rs2927608).

**Example 2 — gwas (edge case: OR_or_BETA sometimes missing)**:
```json
{
  "_id": "gwas:DLBC:rs2608828:RPL9:rs4975018:35870639",
  "pancanqtl": {
    "association_type": "gwas",
    "cancer_type": "DLBC",
    "gene": "RPL9",
    "snp": "rs2608828",
    "position": "4:39453730",
    "gwas_snp": "rs4975018",
    "gwas_snp_position": "4:39476926",
    "r2": 0.53998,
    "risk_allele": "A",
    "or_or_beta": 0.6,
    "p_value": 2e-19,
    "trait_or_disease": "Beta-klotho level in Chronic kidney disease with hypertension and no diabetes (19557_3)",
    "pubmed_id": "35870639"
  }
}
```
Source cross-reference: [PancanQTLv2.0 GWAS-eQTL module](https://hanlaboratory.com/PancanQTLv2/GWAS_eQTL.html) (search cancer type DLBC, SNP rs2608828, or trait "Beta-klotho level").

Note: `pancanqtl.position` in `gwas`-type documents is a combined `"chr:pos"` string (source column `eQTL_SNP_pos`, e.g. `"4:39453730"`), unlike the plain integer `position` in `fine_mapping`/`drug`/`immune` documents — see Mapping Conflicts below.

## Field Coverage

(from the full representative sample: 8,053 gwas / 17,262 fine_mapping / 110 drug / 37 immune documents)

**gwas** (8,053 docs):
- All fields 100% populated except:
  - `or_or_beta`: 79.9% (6,433/8,053) — some GWAS Catalog records report neither an odds ratio nor a beta value for the associated trait, consistent with known GWAS Catalog data-completeness gaps.

**fine_mapping** (17,262 docs): all fields 100% populated (SuSiE fine-mapping output is inherently complete per credible-set row).

**drug** (110 docs): all fields 100% populated.

**immune** (37 docs): all fields 100% populated.

## Test Results Summary

- **Environment blocker**: `biothings-cli` is broken in this sandbox — every subcommand (including `validate`) raises `AttributeError: module 'typer' has no attribute 'rich_utils'` at import time in `biothings/cli/settings.py`, before command dispatch (typer 0.26.7 / biothings 1.0.2 incompatibility). This is the same blocker already logged for ~15 other plugins in `built-plugins-index.md` (ecbd, coconut, chemprob, molbic, persade, geneasso, cancerproteome, medic, tpddb, prime, sorc, ncrnadrug, clinicalomicsdb, etc.). Per instructions, the shared environment was **not** patched.
- **Validation method used instead**: directly imported and executed `parser.load_data()` against 4 live-downloaded representative files (one per module — the smallest available file for each: ESCA fine-mapping, DLBC eQTL-GWAS, LAML drug-eQTL, GBM immune-eQTL), each fetched via `curl -A "Mozilla/5.0"` from the canonical `hanlaboratory.com` domain.
- **Result**: 25,462 unique documents yielded from 25,463 source data rows (0 skipped — every row had a non-empty SNP, cancer_type, and module-appropriate key field). 0 duplicate `_id`s. Counts matched the paper's Table 1 exactly for all 4 sampled cancer types (ESCA fine-mapping credible sets: 745 unique sets / 17,262 SNP rows; DLBC GWAS-related eQTLs: 8,053; LAML drug-related eQTLs: 110; GBM immune-related eQTLs: 37 — see `pancanqtl_inspection.json`'s `paper_vs_reality`).
- **`version.py`**: `get_release(None)` executed directly, returned `"20230927"` (from the `Last-Modified` HTTP header on a live bulk-download file).
- **`dict_sweep`/`unlist` cleanliness**: confirmed no `None`/empty values or single-item lists remained in any of the 25,462 sampled documents.

## Mapping Overview

`mapping.py`'s `get_customized_mapping()` returns a single `pancanqtl.properties` block (25 fields) inferred by recursively walking all 25,462 sampled documents and recording the observed Python type at every field path:

- `association_type`, `cancer_type`, `gene`, `snp`, `variant`, `chr`, `credible_set`, `gwas_snp`, `gwas_snp_position`, `risk_allele`, `pubmed_id`, `alleles`, `drug`, `source`, `cell_type` → `keyword` (categorical/ID-like strings, exact-match and aggregation targets)
- `trait_or_disease` → `text` with a `.raw` keyword subfield (free-text GWAS trait/disease descriptions, but also needed for exact filtering)
- `credible_set_size` → `integer`
- `pip`, `r2`, `or_or_beta`, `p_value`, `beta`, `se`, `fdr` → `float`
- `position` → `keyword` (see Mapping Conflicts below)

**Mapping validation**: a standalone script (not `inspect --mode mapping`, since `biothings-cli` is blocked) recursively walked all 25,462 sampled documents, recorded the observed type at every field path, and diffed that against `mapping.py`'s flattened `properties`. Result: **0 missing fields, 0 unused mapping entries, 1 documented type conflict (resolved, not a failure — see below)**.

### Mapping Conflicts

- **`pancanqtl.position`**: `fine_mapping`, `drug`, and `immune` documents yield an `int` (e.g. `39453730`, from source columns `Position`/`position`), while `gwas` documents yield a combined `"chr:pos"` `str` (e.g. `"4:39453730"`, from source column `eQTL_SNP_pos`, which the eQTL-GWAS module only publishes in that combined form — there is no separate integer position column in that file). This is a genuine cross-module structural conflict, not a parser bug: the source files themselves define `position` differently per module. Resolved by mapping `position` as `keyword` (the safe superset — Elasticsearch keyword fields accept both numeric and string values as exact-match strings) rather than `integer`, which would silently reject or mis-cast the `gwas` module's combined-string values. No information is lost for either shape.

## Notes

- CC BY-NC 4.0 license (non-commercial), per the paper's `ali:license_ref`; no independent site-level license page found on `hanlaboratory.com/PancanQTLv2/`.
- `biothings-cli` broken in this sandbox (typer/biothings v1.0.2 incompatibility, `AttributeError: module 'typer' has no attribute 'rich_utils'`), consistent with the ~15 other plugins already logging this in `built-plugins-index.md`. Not patched (shared environment). Validated via direct `parser.load_data()` execution instead.
- Full-scale production ingestion (124 files, up to ~84.6M eQTL-GWAS rows) was not executed in this session due to both the CLI blocker and file-size/session constraints; validation used the smallest available file per module, cross-checked exactly against the paper's per-cancer-type totals (Table 1). The parser streams rows one at a time (no full-file buffering) so is expected to scale to the full dataset without modification.
- Site (`hanlaboratory.com`) is a lab-hosted domain (Han Laboratory), not an institutional database domain — lower long-term URL-stability guarantee than centrally-hosted resources; worth periodic re-verification.
