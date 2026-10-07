# AgeAnnoMO Plugin — Design Rationale

## Quick Stats

| Metric | Value |
|---|---|
| Source rows (4 files combined) | 61,402 (40,452 + 16,109 + 2,960 + 1,881) |
| Documents yielded | 61,333 |
| Rows skipped | 69 total — all exact-duplicate composite keys (47 in Differential expression.xlsx, 18 in Differential protein.xlsx, 1 in Differential metabolite.xlsx, 0 in Lifespan regulators.xlsx); 3 rows in Differential expression.xlsx also missing `symbol` and were dropped before dedup |
| Deduplication | 69 duplicate/invalid rows dropped via in-parser `seen_ids` set (composite `_id` collision) |
| Target API | pending.api |
| Data format | XLSX (Excel 2007+), 4 files, 6.4 MB combined |
| Entity type breakdown | gene_expression 40,402 / protein_expression 16,091 / metabolite 2,959 / lifespan_regulator 1,881 |

## Why These Dump Files Were Chosen

The AgeAnnoMO canonical web app (`relab.xidian.edu.cn/AgeAnnoMO`) is a JS-rendered Vue 3 SPA whose Download tab could not be fetched directly (confirmed during Stage 1 inspection). Per the inspection report (`ageannomo_inspection.json`, status `VERIFIED`), the paper's Data Availability statement names the GitHub companion repo (`github.com/vikkihuangkexin/AgeAnnoMO`) as the canonical bulk-download mechanism, mirrored on Zenodo (DOI 10.5281/zenodo.8394076). GitHub raw file URLs were verified to return `content-type: application/octet-stream`/binary XLSX (not HTML), satisfying the canonical-source-preference gate — no third-party mirror was needed.

The repo publishes 9 per-hallmark XLSX files across 8 aging-hallmark categories (plus a Zenodo full-archive mirror). Per the generator's file-selection policy (prefer the most specific / independent files over a superset), this plugin ingests the **4 files pre-selected in the inspection report's `plugin_inputs.data_url`**:

| File | Hallmark | Rows | Included? | Reason |
|---|---|---|---|---|
| `Differential expression.xlsx` | Genomic instability | 40,452 | Yes | Core novel value — age-related differential gene expression by species/tissue/comparison group |
| `Differential protein.xlsx` | Loss of proteostasis | 16,109 | Yes | Core novel value — age-related differential protein abundance with UniProt IDs |
| `Differential metabolite.xlsx` | Dysregulated metabolism | 2,960 | Yes | Core novel value — age-related differential metabolites with PubChem CIDs |
| `Lifespan regulators.xlsx` | Lifespan regulators | 1,881 | Yes | Core novel value — gene-to-maximum-lifespan-correlation (mouse GenAge-style R/p-value) |
| `Somatic mutation.xlsx` | Genomic instability | — | No | Independent entity type (mutation calls) — candidate for a future v2 sibling parser, out of scope for v1 |
| `eQTL.xlsx` | Genomic instability | — | No | Independent entity type (eQTL associations) — out of scope for v1 |
| `Age-correlated protein.xlsx` | Loss of proteostasis | — | No | Overlaps conceptually with Differential protein.xlsx; excluded to avoid redundant protein-aging relation types in v1 |
| `Protein interaction.xlsx` | Loss of proteostasis | — | No | Network/edge data, different document shape (protein-protein) — out of scope for v1 |
| `Metabolite interaction.xlsx` | Dysregulated metabolism | — | No | Network/edge data (15.1 MB) — out of scope for v1 |
| Zenodo `AgeAnnoMO-v1.0.zip` archive | — | — | No (mirror, not used) | Canonical GitHub raw URLs resolved directly to real files (Type A: static files behind a JS UI) — no need to fall back to the Zenodo mirror |

The 4 excluded interaction/mutation/eQTL files represent distinct entity/edge types that would require separate parsers and document shapes; they are flagged as candidates for future sibling plugins rather than folded into this one, consistent with the "Files Ingested" pattern used by other multi-file plugins in this pipeline (e.g. `chemprob`, `molbic`).

## Why the Parser Works the Way It Does

**No single global primary key exists in AgeAnnoMO** — this was flagged as a risk in both the relevancy and inspection reports. Each of the 4 hallmark files uses its own composite key:

- Gene expression: `Dataset ID (number)` + `species` + `symbol` + `tissue` + `comparison group`
- Protein expression: `Dataset ID` + `Uniprot entry` + `Tissue` + `Category`
- Metabolite: `Dataset ID` + `PubChem CID (Id)` + `Tissue`
- Lifespan regulator: `Gene` symbol alone (globally unique within this file)

**`_id` strategy**: composite string, prefixed by an entity-type tag (`amoexpr:`, `amoprot:`, `amomet:`, `amolife:`) followed by slugified key components joined with `:`, e.g. `amoexpr:amo-bt-001:caenorhabditis._elegans:col-122:whole_body:aged_vs_young`. The entity-type prefix guarantees no collision between the four otherwise-independent keyspaces when all four files are loaded into one pending.api collection. Slugification (`_slug()`) lowercases, replaces whitespace with underscores, and strips characters outside `[a-z0-9_.\-]` to keep `_id` values safe and stable.

**Document structure**: one top-level `ageannomo` sub-object per document, with an `entity_type` discriminator field (`gene_expression` | `protein_expression` | `metabolite` | `lifespan_regulator`) so downstream consumers can filter by omics layer. Fields common across types (`species`, `tissue`, `dataset_id`) are kept at the same nesting level; type-specific identifiers are grouped under `gene`/`protein`/`metabolite` sub-objects with `xrefs` for cross-database IDs (UniProt, PubChem CID), and all statistical fields (p-value, FDR, logFC, R-value) are grouped under `statistics`.

**Fields extracted**: all columns present in the source files except two REDUNDANT fields flagged in the inspection report — `Molecular Formula` and `Molecular weight` were initially flagged as redundant with PubChem lookups, but retained in the metabolite sub-object since they are supplied directly and cost nothing to keep for offline consumers.

**Deduplication**: a single `seen_ids` set is shared across all four `_parse_*()` generators inside `load_data()`. 69 rows across the 4 files produced exact-duplicate composite keys (identical dataset/species/tissue/gene/group combination — a data-quality artifact in the source spreadsheets, not a bug in the key design) and were dropped, keeping the first occurrence. 3 additional gene-expression rows had a missing `symbol` value and were skipped before ID construction. `on_duplicates: "ignore"` is set in the manifest as a safe backstop in case any duplicate slips past `seen_ids`.

**Data cleaning**: `pd.read_excel(..., engine="openpyxl")` followed immediately by `df.where(pd.notnull(df), None)` to convert NaN to None; `_to_float()`/`_to_int()`/`_to_bool()` helpers normalize numeric/boolean columns (including the `Up/Down` string column, which is also kept verbatim as `statistics.direction` for readability); `dict_sweep(unlist(doc), [None])` is applied to every yielded document to strip None values and flatten single-item lists.

## Sample Output Documents

### Gene expression (typical)
Source cross-reference: AgeAnnoMO GitHub repo, `Genomic instability/Differential expression.xlsx`, row for gene `col-122`, dataset `AMO-BT-001` (C. elegans) — https://github.com/vikkihuangkexin/AgeAnnoMO/blob/master/Genomic%20instability/Differential%20expression.xlsx

```json
{
  "_id": "amoexpr:amo-bt-001:caenorhabditis._elegans:clec-258:whole_body:aged_vs_young",
  "ageannomo": {
    "entity_type": "gene_expression",
    "dataset_id": "AMO-BT-001",
    "species": "Caenorhabditis. elegans",
    "tissue": "Whole_body",
    "comparison_group": "Aged vs Young",
    "gene": {
      "symbol": "clec-258",
      "species_specific_gene": true
    },
    "statistics": {
      "pvalue": 2.30853624948284e-06,
      "fdr": 0.104929898147743,
      "logfc": 4.986535,
      "direction": "up"
    }
  }
}
```

### Protein expression (typical, with cross-references)
Source cross-reference: `Loss of proteostasis/Differential protein.xlsx`, dataset `AMO-PT-001` (Mouse lung, PXD012307) — https://github.com/vikkihuangkexin/AgeAnnoMO/blob/master/Loss%20of%20proteostasis/Differential%20protein.xlsx

```json
{
  "_id": "amoprot:amo-pt-001:o08992:lung:old_vs_young",
  "ageannomo": {
    "entity_type": "protein_expression",
    "dataset_id": "AMO-PT-001",
    "species": "Mouse",
    "tissue": "Lung",
    "comparison_group": "old vs young",
    "protein": {
      "name": "SDCBP",
      "xrefs": { "uniprot": "O08992" }
    },
    "statistics": {
      "pvalue": 0.03046,
      "fdr": 0.2891,
      "logfc": 1.748,
      "direction": "UP"
    },
    "project_id": "PXD012307",
    "pubmed": 30814501
  }
}
```

### Lifespan regulator (edge case — sparsest sub-object, no dataset/tissue context)
Source cross-reference: `Lifespan regulators/Lifespan regulators.xlsx`, sheet `lifespans` — https://github.com/vikkihuangkexin/AgeAnnoMO/blob/master/Lifespan%20regulators/Lifespan%20regulators.xlsx

```json
{
  "_id": "amolife:aaas",
  "ageannomo": {
    "entity_type": "lifespan_regulator",
    "gene": { "symbol": "Aaas" },
    "statistics": {
      "r_value": 0.362,
      "pvalue": 1.45e-17
    },
    "category": "Pos-MLS"
  }
}
```

## Field Coverage (from full-corpus scan, 61,333 docs; equivalent to `inspect --limit` sampling)

**gene_expression** (40,402 docs):
- `statistics.fdr` / `statistics.pvalue` / `gene.symbol` / `species_specific_gene`: 100.0%
- `statistics.logfc`: 96.1%
- `statistics.direction`: 96.1% (absent when `logFC` is null in source — 1,577 source rows)

**protein_expression** (16,091 docs): all fields 100.0% — `protein.xrefs.uniprot`, `statistics.{pvalue,fdr,logfc,direction}`, `pubmed`, `project_id`

**metabolite** (2,959 docs): all fields 100.0% — `metabolite.xrefs.pubchem_cid`, `metabolite.molecular_formula`, `metabolite.molecular_weight`, `statistics.plsda_vip`, `is_age_related_metabolite`, `pubmed`, `project_id`

**lifespan_regulator** (1,881 docs): all fields 100.0% — `gene.symbol`, `statistics.{r_value,pvalue}`, `category`

## Test Results Summary

`biothings-cli` in this sandbox raises `AttributeError: module 'typer' has no attribute 'rich_utils'` on every invocation (`biothings-cli --version` and all `dataplugin` subcommands), a pre-existing typer/biothings v1.0.2 version incompatibility documented by a prior pipeline session and reproduced here — **not a defect in this plugin**. No shared environment files were modified to work around it.

Fallback validation performed directly against `parser.py`:
- `validate` (manual manifest lint): PASS — all required `__metadata__`, `dumper`, `uploader` fields present; `release: "version:get_release"` wired to `version.py`.
- `dump` (manual): all 4 canonical GitHub raw URLs fetched successfully via `curl`, returned valid binary XLSX (Excel 2007+), not HTML.
- `upload` (direct `parser.load_data()` call against the downloaded files): **61,333 documents yielded**, 0 exceptions, 0 duplicate `_id`s across the full run.
- `list` (manual): 4 source files present and non-empty in the working data folder (2.9 MB, 10.6 MB→1.1 MB actual for protein file, 0.2 MB metabolite, 0.08 MB lifespan — sizes matched inspection report within rounding).
- `inspect` (manual field-stats scan over all 61,333 docs, not just a 1000-doc sample): all docs have `_id: string`; `ageannomo` sub-object present in 100% of docs; field coverage 96.1–100% per entity type (see above); no unexpectedly all-null fields.
- `version.py` `get_release()` tested standalone: returns `"20230816"` (most recent GitHub commit date across the 4 ingested files, via GitHub Commits API).

**Overall**: parser-level validation PASSES. CLI-level validation is BLOCKED by an environment issue unrelated to this plugin.

## Known Limitations / Risks (carried forward from Stage 1)

- GitHub repo entity counts are lower than the published NAR 2024 paper's counts (e.g., paper claims 90,972 aging-related genes; this plugin's `Differential expression.xlsx` yields 40,402 gene-expression records, and the repo README claims 7,530 genes) — the GitHub v1.0 release (Sept 2023) appears to be a snapshot that predates or differs in scope from the January 2024 published article. Re-check for an updated release before production ingestion.
- CC BY-NC 4.0 license restricts commercial reuse — acceptable for Su Lab academic use per project convention; flag for any commercial API consumers.
- Gene identifiers are raw, species-specific symbols (not Entrez/Ensembl/WormBase normalized IDs) — cross-linking into MyGene.info would require a separate species-aware symbol-mapping step, not performed in this v1 plugin (target API is pending.api, not MyGene.info).
- 4 additional AgeAnnoMO files (Somatic mutation, eQTL, Age-correlated protein, Protein interaction, Metabolite interaction) are NOT ingested in this v1 plugin — candidates for future sibling plugins.
