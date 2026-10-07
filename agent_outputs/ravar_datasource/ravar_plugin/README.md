# RAVAR Plugin — Design Rationale

## Quick Stats

| Metric | Value |
|---|---|
| Target API | pending.api |
| Data format | TSV (2 direct-download `.txt` files, ~159 MB total) |
| Source rows (gene table) | 76,186 |
| Source rows (variant table) | 18,861 |
| Documents yielded — gene_associations | 12,850 (one per unique Ensembl Gene ID) |
| Documents yielded — variant_associations | 6,470 (one per unique dbSNP rsID) |
| Rows skipped | 0 (0 missing `Ensembl ID`/`Gene Symbol`, 0 missing `RSID`) |
| Nested association rows preserved | 76,186 (gene) + 18,861 (variant) — matches source exactly |
| Deduplication | None needed — grouped-by-entity design; no duplicate Ensembl IDs or rsIDs in source |
| `_id` format | Ensembl Gene ID (`ENSG…`) for gene docs; dbSNP rsID (`rs…`) for variant docs |

## Why These Dump Files Were Chosen

RAVAR's own download API (`GET /api/download/list`) lists four static files:

| File | Rows | Ingested? | Reason |
|---|---|---|---|
| `gene_fulltable.txt` | 76,186 | Yes | Gene-level rare-variant/gene-trait association evidence (the paper's core "gene-level associations") |
| `snp_fulltable.txt` | 18,861 | Yes | Variant-level rare-variant/trait association evidence (the paper's core "variant-level associations") |
| `trait_allinfo.txt` | 2,005 | No | Lookup table only — every column (`Trait Ontology id`, `Trait Label`, `EFO description`, `EFO synonym`, `EFO Tree`) is already denormalized into every row of the two main tables above. Joining it would duplicate, not add, information. |
| `publication_allinfo.txt` | 245 | No | Same reasoning — every column (`PMID`, `Title`, `Authors`, `Citation`, `First Author`, `Journal/Book`, `Publication Year`, `Create Date`, `PMCID`, `NIHMS ID`, `DOI`) is already present on every association row of the two main tables. |

The site (`www.ravar.bio`) is a JS-rendered Vue single-page app — the download page itself returns no static HTML/links. The four canonical file URLs were recovered by fetching the compiled JS bundle (`app.js`) and grepping for the underlying REST API base path (`/api/`), which surfaced `download/list`. Calling that endpoint returned the four `downloadLink` values used here, all served directly from the datasource's own domain (`www.ravar.bio/api/download/static/*.txt`) — no third-party mirror was needed (Type A case: static files behind a JS UI).

Both files were downloaded directly with `curl -A "Mozilla/5.0"` and verified: `gene_fulltable.txt` = 76,186 data rows (matches the paper's stated "76,186 gene-level associations" exactly); `snp_fulltable.txt` = 18,861 data rows (matches the paper's stated "18,861 variant-level associations" exactly). The API's own file-size metadata (`"size": "33.1M"` for gene_fulltable.txt) is stale — actual downloaded size is ~132.5 MB — but the row counts confirm the download is complete and correct, not truncated or duplicated.

## Why the Parser Works the Way It Does

**Two entity types, `uploaders` (plural).** RAVAR reports associations at two different granularities — genes and individual variants — each with its own natural BioThings identifier (Ensembl Gene ID vs. dbSNP rsID) and its own set of entity-level fields (gene type/location/synonyms vs. chromosome position/genotype/MAF). Per the plugin generator's own manifest guidance ("use `uploaders` only when the output document types are fundamentally different, e.g., genes AND variants from the same dump"), this plugin declares two named uploaders (`gene_associations`, `variant_associations`), each with its own parser function and its own `mapping.py` function.

**`_id` strategy.** Both source tables are denormalized: RAVAR repeats the full gene (or variant) metadata on every association row (one row per gene-trait or variant-trait pair contributed by one source publication). The parser groups rows in memory by the entity's natural identifier — `Ensembl ID` for `gene_fulltable.txt` (confirmed 1:1 with `Gene Symbol`, 12,850 unique values, 0 empty), `RSID` for `snp_fulltable.txt` (6,470 unique values, 0 empty) — and nests each row's association-specific evidence (trait, p-value/beta, method, source publication) into an `associations` list on that one entity document.

`RID` (RAVAR's own per-association record ID, e.g. `R00001`) was considered as a candidate key but rejected: RID values are **not** unique per row (only 3,404 distinct RIDs across 76,186 gene rows) — RID identifies the association concept, not the row — so it cannot serve as a document `_id` on its own.

**Fields extracted.** All 26 gene-table columns and all 28 snp-table columns are captured except the six unused fields (`Gene synonym`/`EFO synonym`/`EFO Tree`/`Nearby Genes` are captured, not skipped — see field list below). No fields were dropped; `trait_allinfo.txt`/`publication_allinfo.txt` were skipped entirely at the file-selection level (see above), not at the field level.

**Data cleaning.**
- Semicolon-delimited fields (`Gene synonym`, `EFO synonym`, `Nearby Genes(+-100K)`) are split into clean string lists, dropping empty/`NA` tokens.
- The `EFO Tree` field packs multiple ontology hierarchy paths separated by `"; "`; each path is kept as one list element (pipe-delimited hierarchy string), not further parsed into nested ontology objects, to avoid inventing structure the source doesn't explicitly provide.
- `P-value`, `Beta`, `MAF` are converted from strings (including scientific notation like `5.91E-05`) to Python `float`; `POS`/`Publication Year` to `int`. Malformed/`NA` values become `None` and are dropped by `dict_sweep`.
- `dict_sweep(doc, [None])` + `unlist(doc)` are applied to every yielded document, per SDK convention. Because roughly a third of gene documents (3,687/12,850) and about two-thirds of variant documents (4,159/6,470) have exactly one association row, `unlist()` collapses their single-element `associations` list down to a bare object — this is expected SDK behavior (see "Sample Output Documents" below), not a parser bug, and is accounted for in the mapping (see "Mapping Overview").
- No deduplication logic was needed: the grouping key (Ensembl ID / rsID) has zero duplicates in either source file, and multiple genuine associations for the same gene/variant are the deliberate reason for the nested `associations` list.

## Sample Output Documents

**Gene document, single association** (`ENSG00000121410` / A1BG) — Source cross-reference: [RAVAR download page](http://www.ravar.bio) (per-gene detail pages are not stably linkable from the JS SPA; row is verifiable in `gene_fulltable.txt`, `RID=R00001`).
```json
{
  "_id": "ENSG00000121410",
  "ravar": {
    "gene_symbol": "A1BG",
    "ensembl_id": "ENSG00000121410",
    "gene_type": "protein_coding",
    "chr": "19",
    "location": "chr19:58345178-58353492",
    "gene_full_name": "alpha-1-B glycoprotein",
    "gene_summary": "The protein encoded by this gene is a plasma glycoprotein of unknown function...",
    "associations": {
      "rid": "R00001",
      "reported_trait": "Abnormal findings on diagnostic imaging of other parts of digestive tract",
      "trait_label": "abnormal result of diagnostic imaging",
      "trait_ontology_id": "EFO:0009827",
      "efo_tree": "abnormal result of diagnostic imaging|test result|information entity|experimental factor",
      "pvalue": 5.91e-05,
      "method_software": "collapsing analyse",
      "publication": {
        "pmid": "34375979",
        "pmcid": "PMC8458098",
        "doi": "10.1038/s41586-021-03855-y",
        "title": "Rare variant contribution to human disease in 281,104 UK Biobank exomes",
        "first_author": "Wang Q",
        "journal": "Nature",
        "publication_year": 2021
      }
    }
  }
}
```

**Variant document, multiple associations** (`rs143997339` / FBN1) — Source cross-reference: row verifiable in `snp_fulltable.txt`, `RID=R03019`/`R03653`. Shows the multi-association list shape, ontology cross-mapping across HPO and MONDO vocabularies within the same field (`trait_ontology_id`), and a long free-text `efo_description`:
```json
{
  "_id": "rs143997339",
  "ravar": {
    "rsid": "rs143997339",
    "chr": "15",
    "pos": 48424410,
    "genotype": "C/A",
    "maf": 0.0077255,
    "mapped_gene": "FBN1",
    "nearby_genes": ["DUT", "FBN1"],
    "associations": [
      {
        "rid": "R03019",
        "trait_label": "Abnormality of connective tissue",
        "trait_ontology_id": "HP:0003549",
        "beta": 1.93221,
        "pvalue": 7.69e-08,
        "publication": {"pmid": "33226994", "journal": "PLoS Genet", "publication_year": 2020}
      },
      {
        "rid": "R03653",
        "trait_label": "Marfan syndrome",
        "trait_ontology_id": "MONDO:0007947",
        "efo_synonym": ["Marfan syndrome", "MFS", "Marfan's syndrome", "MFS1", "Marfan syndrome type 1", "Marfan syndrome, type 1"],
        "beta": 1.8479,
        "pvalue": 2.63e-07,
        "publication": {"pmid": "33226994", "journal": "PLoS Genet", "publication_year": 2020}
      }
    ]
  }
}
```
(Publication sub-object truncated above for readability; full field set includes `citation`, `authors`, `doi`, `pmcid`.)

## Field Coverage

From a full parse of both source files (not a 1000-doc sample — the collections are small enough to scan completely):

**Gene documents (n=12,850):**
- `gene_synonym`: 88.4%
- `gene_summary`: 96.4%
- `associations.efo_description`: 31.6% (of 76,186 nested association rows)
- `associations.efo_synonym`: 71.0%
- `associations.method_software`: 100.0%

**Variant documents (n=6,470):**
- `nearby_genes`: 93.9%
- `associations.efo_description`: 43.3% (of 18,861 nested association rows)
- `associations.efo_synonym`: 79.5%
- `associations.ci_95`: 22.6%
- `associations.beta`: 99.9%

## Test Results Summary

`biothings-cli` could not be run in this sandbox — every subcommand (`validate`, `dump`, `upload`, `list`, `inspect`, `inspect --mode mapping`) fails at import time with `AttributeError: module 'typer' has no attribute 'rich_utils'` (typer/biothings 1.0.2 incompatibility, confirmed by directly invoking `biothings-cli dataplugin validate` in this plugin's directory). This is the same known blocker logged for ~15 other plugins in `built-plugins-index.md` (e.g. `chemprob`, `persade`) — not patched, per instructions not to alter the shared environment.

Validated instead via direct execution:
1. Downloaded both source files with `curl -A "Mozilla/5.0"` from the live site (`gene_fulltable.txt` 76,186 rows / ~132.5 MB, `snp_fulltable.txt` 18,861 rows / ~26.6 MB) — both row counts match the paper's stated entity counts exactly.
2. Ran `parser.load_gene_data()` and `parser.load_variant_data()` directly against the downloaded files (not via the Hub):
   - `load_gene_data`: 12,850 documents yielded, 0 exceptions, `_id` = Ensembl Gene ID (100% present, 0 duplicates), all 76,186 source rows preserved across the nested `associations` lists (verified by summing per-doc association counts).
   - `load_variant_data`: 6,470 documents yielded, 0 exceptions, `_id` = dbSNP rsID (100% present, 0 duplicates), all 18,861 source rows preserved.
3. Confirmed no silent-zero-doc failure mode (both generators yield documents on every run) and no `_id` format violations (all `_id` values are non-empty strings well under the 512-character limit).
4. Confirmed `dict_sweep`/`unlist` cleanliness: no `None`, empty-string, or empty-list values survive into the yielded documents; NaN/float coercion issues do not apply here since the parser is stdlib `csv`-based (no pandas).

## Mapping Overview

`mapping.py` defines `get_gene_mapping(cls)` and `get_variant_mapping(cls)` (one per uploader), wired into `manifest.json` via `"mapping": "mapping:get_gene_mapping"` / `"mapping": "mapping:get_variant_mapping"` on each entry of the `uploaders` list.

**Top-level structure (both):**
- All identifier/categorical string fields (`gene_symbol`, `ensembl_id`, `chr`, `rsid`, `trait_ontology_id`, `associations.publication.*`, etc.) → `keyword`
- `gene_summary` and `associations.efo_description` (paragraph-length free text) → `text` with a `.raw` keyword subfield, since these are the only fields intended for full-text search rather than exact match/aggregation
- `associations.pvalue`, `associations.beta`, `maf` → `float`
- `pos`, `associations.publication.publication_year` → `integer`
- List fields (`gene_synonym`, `efo_synonym`, `efo_tree`, `nearby_genes`) → mapped from their scalar string elements, not as a separate array type (no BioThings/ES array type exists)
- `associations` and `associations.publication` → nested `object` via `properties` (not `nested` type — same object shape is shared whether `associations` collapses to a scalar dict or remains a list, per `unlist()` behavior)

**Validation:** wrote a standalone script (`validate_mapping.py`) that ran both `load_gene_data()` and `load_variant_data()` against the full downloaded collections (12,850 + 6,470 docs, no sampling), recursively recorded the observed Python type at every field path, and diffed that against `mapping.py`'s flattened `properties`. Result: 26/26 leaf fields matched for `gene_associations`, 26/26 for `variant_associations` — 0 missing fields, 0 unused mapped fields, 0 type mismatches in either collection.

**Mapping Conflicts:** None. A full-collection scan (not a sample) found exactly one Python type at every field path in both uploaders — no field is ever numeric in some documents and string in others, and no field is ever a scalar in some documents and an incompatible object shape in others.
