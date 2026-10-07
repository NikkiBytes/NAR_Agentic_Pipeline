# DiSignAtlas Plugin — Design Rationale

## Quick Stats

| Metric | Value |
|---|---|
| Source rows (dataset-info CSV) | 10,306 |
| Source rows (DEG GMT) | 8,466 |
| Documents yielded | 10,306 |
| Rows skipped | 0 (no blank/duplicate `dsaid` observed in the CSV) |
| Deduplication | `seen_ids` guard present in parser but never triggered — every `dsaid` in the CSV is unique |
| Target API | pending.api |
| Data format | CSV (2.95 MB) + GMT/tab-delimited (35.6 MB) |
| Total file size | ~38.5 MB (of the two files ingested; a 10.1 GB per-dataset ZIP was intentionally excluded — see below) |

## Why These Dump Files Were Chosen

The DiSignAtlas download page (`http://www.inbirg.com/disignatlas/download`) lists five downloadable artifacts:

| File | Format | Size | Chosen? | Reason |
|---|---|---|---|---|
| Disease information of All DiSignAtlas Datasets | CSV | 2.95 MB | **Yes** | Dataset-level index: one row per DiSignAtlas dataset (`dsaid`), with disease name/ontology definition, tissue, accession, platform, organism, library strategy, sample counts. This is the base entity table and the only file with 100% dataset coverage (10,306/10,306). |
| Differentially Expressed Genes of All DiSignAtlas Datasets | GMT | 35.6 MB | **Yes** | Per-dataset ranked list of top differentially expressed genes (NCBI/Entrez Gene IDs). This is the novel disease-signature payload that makes DiSignAtlas worth ingesting — it is joined onto the CSV rows by `dsaid`. |
| Differential Gene Expression Analysis Result of Each DiSignAtlas Dataset | ZIP | 10.1 GB | No | Per-gene fold-change/p-value detail for every dataset. Excluded from this first ingestion pass — two orders of magnitude larger than the two files above, and the dataset-info CSV + top-DEG GMT already capture the disease/gene-signature relationship at a scope appropriate for a first plugin. Left as a candidate for a future, separate large-scale ingestion (see `risks` in the inspection JSON). |
| Source Codes for Differential Gene Expression Analysis | TXT (3 KB) | 3 KB | No | Analysis pipeline source code (limma/DESeq2/edgeR/Seurat), not entity data. |
| Source Codes for Functional Enrichment Analysis | TXT (2 KB) | 2 KB | No | GO/KEGG enrichment pipeline source code, not entity data. |

Both selected files were verified as direct, unauthenticated downloads (`curl -A "Mozilla/5.0"` → HTTP 200, correct `Content-Disposition` filenames, no HTML/login wall). **Note**: `www.inbirg.com` only serves over plain HTTP — port 443 (HTTPS) refuses the connection outright. This is a site configuration quirk, not an access restriction, so `manifest.json`'s `dumper.data_url` uses `http://` URLs deliberately, not `https://`.

## Why the Parser Works the Way It Does

- **`_id` strategy**: the DiSignAtlas ID (`dsaid`, e.g. `DSA00001`) — an 8-character string, unique across all 10,306 rows in the CSV (verified: `len(set(ids)) == len(ids)`). This is the resource's own stable per-dataset identifier and the natural join key between the two source files.
- **File identification by content-sniffing, not filename**: both `dumper.data_url` entries point at extension-less paths (`.../download/dis_info_datasets`, `.../download/dis_info_degs`). Since the exact filename the Hub's dumper persists them under isn't guaranteed to preserve an extension, `parser.py`'s `_find_input_files()` scans `data_folder` and classifies each file by sniffing its first line: the CSV's header starts with `dsaid,accession,...`; the GMT has no header and each line starts with `DSA#####\t...`. This is more robust than hardcoding filenames.
- **Document structure**: one document per dataset, top-level `_id` + a single `disignatlas` sub-object containing dataset metadata (`accession`, `platform`, `disease`, `disease_id`, `tissue`, `data_source`, `library_strategy`, `organism`, `sample_count.{control,case}`, `definition`, `deg_count`) plus an optional `degs` list (Entrez Gene IDs) joined in from the GMT file by `dsaid`.
- **Fields extracted**: all CSV columns are mapped except `dsaid` itself (promoted to `_id`) and `control_case_sample_count`, which is split into a `{control, case}` sub-object for both fields to be independently queryable/aggregatable rather than a single pipe-delimited string.
- **Fields skipped**: none of the CSV's columns were dropped. From the GMT file, only column 1 (`dsaid`, used as the join key) and columns 3+ (the actual DEG gene IDs) are used — column 2 is a pipe-delimited restatement of the same run metadata already present in the CSV row (accession/platform/disease/etc.) and is not re-extracted, to avoid a redundant duplicate representation of the same facts.
- **Deduplication**: a `seen_ids` set guards against duplicate `dsaid` values, though none were observed in the live data (10,306 CSV rows → 10,306 unique documents).
- **Data cleaning**:
  - `control_case_sample_count` (`"1|1"`) is split on `|` and validated as two digit strings before being emitted as `{"control": 1, "case": 1}`; malformed values are dropped (`_parse_sample_count` returns `None`, and `dict_sweep` removes the key) rather than emitting a partial/garbage value.
  - GMT gene-ID columns occasionally carry a stray trailing double-quote artifact from the source's upstream export (e.g. `381530"` instead of `381530`) — `_clean_gene_id()` strips stray quote/whitespace characters before coercing to `int`. 36 such occurrences were observed and corrected across the full GMT file; genes that still aren't a bare integer after cleaning are dropped rather than silently kept as strings (which would create a field-type conflict against the `integer` mapping).
  - Files are read with `encoding="utf-8", errors="replace"` because a small number of `definition` values (28 of 10,306) contain non-UTF-8 mojibake byte sequences (e.g. a corrupted micro-sign/em-dash) from the source export; `errors="replace"` avoids a hard `UnicodeDecodeError` while preserving the rest of each string intact.
  - `dict_sweep(unlist(doc), [None])` removes all `None`/empty fields (e.g. missing `tissue`, missing `degs` for the ~18% of datasets not covered by the DEG GMT export) so sparse fields are simply absent rather than null.

## Sample Output Documents

**Typical document** (has DEGs; source: `Disease_information_Datasets.csv` row 1 joined with `Disease_information_DEGs.gmt` line 1):

```json
{
  "_id": "DSA00001",
  "disignatlas": {
    "accession": "GSE224398",
    "platform": "GPL21103",
    "disease": "Alzheimer's Disease",
    "disease_id": "C0002395",
    "tissue": "Hippocampus",
    "data_source": "GEO",
    "library_strategy": "scRNA-Seq",
    "organism": "Mus musculus",
    "sample_count": {"control": 1, "case": 1},
    "definition": "DO:An Alzheimer's disease that has_material_basis_in mutation heterozygous mutation in the APP gene, which encodes the amyloid precursor protein, on chromosome 21q21.",
    "deg_count": 1000,
    "degs": [72265, 67923, 19243, 20846, 22218, "... 1000 Entrez Gene IDs total"]
  }
}
```
Source cross-reference: `http://www.inbirg.com/disignatlas/download` (bulk file; DiSignAtlas has no confirmed per-record detail-page URL pattern at inspection time) — original GEO series: `https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE224398`.

**Edge-case document** (no DEG signature published in the bulk GMT export — `degs`/`deg_count` still populated from the CSV but `deg_count` is `0` here and no `tissue`):

```json
{
  "_id": "DSA00007",
  "disignatlas": {
    "accession": "GSE224253",
    "platform": "GPL17692",
    "disease": "Allergic Disorder of Respiratory System",
    "disease_id": "C1504369",
    "data_source": "GEO",
    "library_strategy": "Microarray",
    "organism": "Homo sapiens",
    "sample_count": {"control": 7, "case": 9},
    "deg_count": 0
  }
}
```
Source cross-reference: original GEO series `https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE224253`.

## Field Coverage

(Full-collection coverage over all 10,306 documents — no sampling used, since the source files are small enough to parse in full.)

- `accession`: 100.0%
- `platform`: 98.0%
- `disease`: 100.0%
- `disease_id`: 95.4%
- `tissue`: 73.4%
- `data_source`: 100.0%
- `library_strategy`: 100.0%
- `organism`: 100.0%
- `sample_count`: 100.0%
- `definition`: 94.0%
- `deg_count`: 100.0%
- `degs`: 81.8% (8,466 of 10,306 datasets have a published DEG list in the bulk GMT export; the remaining 18.2% have no `degs` field)

## Test Results Summary

**Environment blocker**: `biothings-cli` is broken in this sandbox for every subcommand:
```
$ biothings-cli dataplugin validate
Traceback (most recent call last):
  File ".../biothings/cli/settings.py", line 44, in setup_commandline_configuration
    typer.rich_utils.STYLE_HELPTEXT = ""
AttributeError: module 'typer' has no attribute 'rich_utils'
```
This is the same typer 0.26.7 / biothings 1.0.2 incompatibility already logged against ~15 other plugins in `built-plugins-index.md` (e.g. `chemprob`, `molbic`). Per that precedent, validation was performed via direct script execution rather than the CLI:

1. **`validate` (manual equivalent)**: `manifest.json` was hand-checked against `manifest-schema.md` — `version: "1.0"`, `__metadata__` complete with `publication` block (DOI/PMID/PMC re-verified live via Europe PMC, matching title "DiSignAtlas: an atlas of human and mouse disease signatures based on bulk and single-cell transcriptomics"), `dumper.data_url` is a 2-element list of directly-curl-able URLs, `dumper.release: "version:get_release"` wired to `version.py`, `uploader.parser: "parser:load_data"`, `uploader.mapping: "mapping:get_customized_mapping"`. PASS.
2. **`dump` (manual equivalent)**: both `data_url` files fetched with `curl -A "Mozilla/5.0"` — both returned HTTP 200 with correct `Content-Disposition` filenames (`Disease_information_Datasets.csv`, `Disease_information_DEGs.gmt`), non-empty (2.95 MB / 35.6 MB, matching the download page's stated sizes). `version.get_release()` executed directly, returned `"20230901"` (regex match against the download page's first RELEASED-ON date). PASS.
3. **`upload` (manual equivalent)**: `parser.load_data(data_folder)` called directly against the two downloaded files placed in a local folder. Yielded **10,306 documents** in 4.5 seconds, zero exceptions. PASS (not a silent-zero-doc failure).
4. **`list` (manual equivalent)**: confirmed via the same script — 10,306 unique `_id`s (`len(set(ids)) == 10306 == len(docs)`), all `_id`s are 8-character strings matching `DSA\d{5}`. PASS.
5. **`inspect` (manual equivalent)**: iterated all 10,306 yielded documents — every document has a string `_id` and a populated top-level `disignatlas` key; field coverage computed above; no stray `None` values remain after `dict_sweep`/`unlist` (spot-checked via `json.dumps` on sample docs, and via the mapping-diff script below which would surface any leftover `NoneType` value as a type mismatch). PASS.
6. **`inspect --mode mapping` (manual equivalent)**: a standalone script recursively walked every field path across **all 10,306** yielded documents (full collection, not a 1,000-doc sample — the source is small enough to process in full), recorded the observed Python type at each path, and diffed it against `mapping.py`'s flattened `properties`. Result: **0 missing fields, 0 type mismatches, 0 unused mapping entries.** PASS.

**Rollup: 6/6 steps PASS** (via direct-script equivalents in place of the broken CLI).

## Mapping Overview

Top-level `disignatlas.properties` (see `mapping.py`):

| Field | ES type | Notes |
|---|---|---|
| `accession` | `keyword` | GEO/ArrayExpress/TCGA accession |
| `platform` | `keyword` | Array/sequencer platform ID |
| `disease` | `text` + `.raw` keyword | Disease name — full-text searchable, with exact-match/aggregation subfield |
| `disease_id` | `keyword` | DisGeNET/UMLS CUI |
| `tissue` | `keyword` | Categorical, short strings |
| `data_source` | `keyword` | Enum: `GEO` \| `TCGA` \| `ArrayExpress` |
| `library_strategy` | `keyword` | Enum: `Microarray` \| `RNA-Seq` \| `scRNA-Seq` \| `snRNA-Seq` |
| `organism` | `keyword` | Enum: `Homo sapiens` \| `Mus musculus` |
| `sample_count.control` / `sample_count.case` | `integer` | Nested object |
| `definition` | `text` + `.raw` keyword | Disease-ontology free-text definition (DO/EFO/MONDO/MeSH/etc., prefixed with source tag) |
| `deg_count` | `integer` | Value observed as a constant `1000` for datasets with a full DEG export cutoff, and `0` for datasets without one — treated as an integer count, not a boolean flag |
| `degs` | `integer` | List of NCBI/Entrez Gene IDs; mapped by element type (Elasticsearch has no array type) |

**Mapping Conflicts**: none. Recursively inferring types across the full 10,306-document collection found exactly one Python type per field path (`str`, `int`, or nested `dict`/`int`) with no scalar-vs-object or numeric-vs-string conflicts. The only per-field nuance worth flagging (not a conflict, just a modeling note): `deg_count` in the CSV is a fixed `1000` for every dataset that has a DEG list, rather than the literal number of significant DEGs for that dataset — the true per-dataset signature size is `len(degs)` once the field is populated (ranges from 1 to 1000 genes across the GMT file), not `deg_count`. Both fields are kept as-is (matching the source), with this distinction documented here rather than silently "fixed" by the parser.
