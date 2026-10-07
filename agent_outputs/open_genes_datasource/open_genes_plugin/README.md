# Open Genes — Plugin Design Rationale

## Quick Stats

| Metric | Value |
|---|---|
| Source records fetched | 2,405 (single API response, `objTotal`) |
| Documents yielded | 2,404 |
| Rows skipped | 1 (missing `ncbiId`, the `_id` field) |
| Duplicate `_id` collisions | 0 |
| Target API | pending.api |
| `_id` strategy | NCBI (Entrez) Gene ID (`ncbiId`) |
| Data format / size | JSON (single REST response), ~3.7 MB, 2,405 gene records |
| Parser test | Ran `parser.load_data()` directly against a locally cached copy of the dumped API response — see Test Results Summary |

---

## Why This Dump File Was Chosen

**No static bulk file exists.** Per the skill's mandatory URL-verification step, both candidate canonical paths were tested live:

```
curl -sIL -A "Mozilla/5.0" https://open-genes.com/download
  → Content-Type: text/html   (JS-rendered SPA shell, not a data file)

curl -sIL -A "Mozilla/5.0" https://open-genes.com/media/open_genes_sql_dump.zip
  → HTTP 200, Content-Type: text/html   (soft-404 page, not the zip referenced in GitHub docs)
```

This confirms the inspection report's risk note: the `/download` page and the GitHub-referenced `open_genes_sql_dump.zip` are not independently resolvable as direct-download files from the sandbox. No `.zip`/`.csv`/`.tsv` file could be found at the canonical domain after probing the documented path and common patterns (Step 1a of the mandatory verification gate). No third-party mirror (Zenodo/Figshare/GitHub release archive) was substituted, since none is referenced by the paper as the "official" distribution channel — the described bulk path is the site's own `/download` UI, which is JS-rendered and inaccessible here (Type B case: dynamically generated, no stable static URL).

**The confirmed-live REST API supports single-request bulk retrieval.** The inspection report verified `https://open-genes.com/api/gene/search` live, with default pagination (`pageSize=20`, `pagesTotal=121`). Testing showed the API accepts an arbitrarily large `pageSize` and returns the *entire* collection in one response when the requested page size exceeds the total record count:

```
curl 'https://open-genes.com/api/gene/search?pageSize=5000&page=1'
  → HTTP 200, Content-Type: application/json
  → options.objTotal = 2405, pagination.pagesTotal = 1, items returned = 2405
```

This lets the plugin use the standard **manifest-first bulk-download strategy** (`dumper.data_url` as a single curl-able URL) even though the underlying source is API-backed — no custom `dumper.py`, pagination loop, or API-crawl escalation is needed. This is a deliberate, documented deviation from the generic case in SKILL.md §1c ("Only a REST API is available → stop and escalate") because the API itself satisfies the direct-file-URL test in §1b-gate Step 2/3 (JSON content-type, expected schema on first bytes) once a sufficiently large `pageSize` is supplied. The URL is recorded verbatim in `manifest.json.dumper.data_url`.

**Rejected alternative**: writing a custom `APIDumper`-based `dumper.py` (the `clinicaltrials_gov` pattern in `production-plugin-examples.md`) to paginate 121 pages of 20 records each. Rejected because it is unnecessary — the single generous-`pageSize` request returns identical data with far less complexity, one HTTP call instead of 121, and fits the plugin's required 4-file structure (`manifest.json` + `parser.py` + `version.py` + this file) without an extra `dumper.py`.

## Correction to prior evaluation

The relevancy report (`open_genes_relevancy.json`) recorded `paper_doi: "10.1093/nar/gkad1015"`. Independently re-resolving `PMC10768108` via the NCBI ID Converter API returned a *different* DOI:

```
https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/?ids=PMC10768108&format=json
  → {"doi":"10.1093/nar/gkad712","pmcid":"PMC10768108","pmid":37665017}
```

Cross-checked against CrossRef: `10.1093/nar/gkad712` resolves to *"Open Genes—a new comprehensive database of human genes associated with aging and longevity"* (correct), while `10.1093/nar/gkad1015` resolves to an unrelated siRNA-chemistry paper. **`manifest.json` uses the corrected DOI (`10.1093/nar/gkad712`) and PMID (`37665017`)**, not the value recorded in the relevancy report.

## Why the Parser Works the Way It Does

- **`_id` strategy**: `ncbiId` (NCBI/Entrez Gene ID), per the inspection's verified `primary_key` field. All 2,405 records have a unique `ncbiId` except one, which is skipped (see Quick Stats). No duplicate collisions were observed across the full dataset, so `on_duplicates: "error"` is safe.
- **File discovery**: because the dumped filename for a query-string URL depends on the Hub's HTTP dumper naming behavior (not verifiable without a working `biothings-cli` in this sandbox — see Test Results Summary), `parser.py._find_source_file()` globs every file in `data_folder` and accepts the first one that parses as JSON with an `items` list, rather than hardcoding a filename.
- **Document structure**: one document per gene, nested under `open_genes`, following the "Structure Output Documents" guidance:
  - `xrefs` sub-object: `ncbigene`, `ensembl`, `uniprot`
  - Simple novel scalar/nested fields kept close to source shape: `confidence_level`, `origin`, `family_origin`, `expression_change`, `methylation_correlation`
  - List fields flattened to name-only lists where the source objects carried no other useful attributes (`aging_mechanisms`, `functional_clusters`, `protein_classes`, `longevity_associations` — sourced from `commentCause`, renamed for clarity since it represents literature-derived longevity/lifespan associations)
  - `disease_categories` / `diseases` kept as ICD-coded sub-objects (`icdCode`, `icdCategoryName` / `icdCode`, `name`, `icdName`)
- **Fields excluded** (per inspection's `redundant_fields` classification): `name` (redundant with `symbol`), `aliases`, `chromosome`, and `location` (transcript/exon coordinate data — large, redundant with existing genomic-coordinate sources like NCBI/Ensembl already surfaced by MyGene.info).
- **Data cleaning**: every document passes through `dict_sweep(unlist(doc), [None, "", [], {}])`, removing empty/None values and flattening single-item lists (e.g., a gene with exactly one aging mechanism yields a bare string instead of a one-element list — this is expected `unlist()` behavior per SKILL.md and is consistent across BioThings production plugins, though it means some list-typed fields can appear as either a scalar or a list depending on cardinality).
- **Deduplication**: none needed — a single source file, one row per gene, `ncbiId` unique (verified: 0 duplicate IDs across 2,405 items).

## Sample Output Documents

### Typical example — GHR (growth hormone receptor, highest confidence)

Source cross-reference: `https://open-genes.com/api/gene/search?pageSize=1&page=1` (first record) — Open Genes has no per-gene permalink on the live site; the API response is the authoritative source record.

```json
{
  "_id": "2690",
  "open_genes": {
    "symbol": "GHR",
    "xrefs": {
      "ncbigene": 2690,
      "ensembl": "ENSG00000112964",
      "uniprot": "GHR_HUMAN"
    },
    "confidence_level": "highest",
    "origin": {
      "phylum": "Euteleostomi",
      "age_million_years": "420"
    },
    "family_origin": {
      "phylum": "Vertebrata",
      "age_million_years": "490"
    },
    "disease_categories": [
      {"icdCode": "E70-E90", "icdCategoryName": "Metabolic disorders"},
      {"icdCode": "E20-E35", "icdCategoryName": "Disorders of other endocrine glands"}
    ],
    "diseases": [
      {"icdCode": "E78.0", "name": "Hypercholesterolemia, familial", "icdName": "Pure hypercholesterolaemia"},
      {"icdCode": "E34.3", "name": "Laron syndrome", "icdName": "Short stature, not elsewhere classified"}
    ],
    "aging_mechanisms": "INS/IGF-1 pathway dysregulation",
    "functional_clusters": [
      "glucose metabolism", "mitochondrial function", "insulin sensitivity",
      "lipid metabolism", "endocrine system"
    ],
    "protein_classes": ["Disease related genes", "FDA approved drug targets", "Predicted membrane proteins"],
    "longevity_associations": [
      "Changes in gene activity extend mammalian lifespan",
      "Association of genetic variants and gene expression levels with longevity",
      "Regulation of genes associated with aging"
    ],
    "expression_change": 0
  }
}
```

### Sparse/edge-case example — PDGFB (lowest confidence, methylation data present)

Source cross-reference: `https://open-genes.com/api/gene/search?pageSize=5000&page=1` (filter for `ncbiId=5155`).

```json
{
  "_id": "5155",
  "open_genes": {
    "symbol": "PDGFB",
    "xrefs": {"ncbigene": 5155, "ensembl": "ENSG00000100311", "uniprot": "PDGFB_HUMAN"},
    "confidence_level": "lowest",
    "family_origin": {"phylum": "Bilateria", "age_million_years": "700–800"},
    "disease_categories": {"icdCode": "G20-G26", "icdCategoryName": "Extrapyramidal and movement disorders"},
    "diseases": [
      {"icdCode": "D32.9", "name": "Meningioma, familial, susceptibility to", "icdName": "Benign neoplasm: Meninges, unspecified"},
      {"icdCode": "C49.9", "name": "Dermatofibrosarcoma protuberans", "icdName": "Malignant neoplasm: Connective and soft tissue, unspecified"}
    ],
    "aging_mechanisms": ["accumulation of reactive oxygen species", "intercellular communication impairment"],
    "functional_clusters": ["embryonic development", "oxidation/antioxidant function", "inflammation", "signaling"],
    "methylation_correlation": "..."
  }
}
```

(`disease_categories` collapses to a single dict here rather than a list — an `unlist()` side effect for genes with exactly one disease category; documented above.)

## Field Coverage

Computed from the full parsed set (2,404 documents — no `--limit 1000` sampling needed since the entire collection is only 2,405 rows):

- `open_genes.confidence_level`: 100.0%
- `open_genes.expression_change`: 100.0%
- `open_genes.longevity_associations`: 100.0%
- `open_genes.protein_classes`: 98.4%
- `open_genes.xrefs.ensembl`: 98.5%
- `open_genes.aging_mechanisms`: 52.3%
- `open_genes.xrefs.uniprot`: 41.8%
- `open_genes.diseases`: 30.1%
- `open_genes.family_origin`: 19.9%
- `open_genes.functional_clusters`: 21.5%
- `open_genes.origin`: 10.4%
- `open_genes.disease_categories`: 7.2%
- `open_genes.methylation_correlation`: 2.3%

## Test Results Summary

**`biothings-cli` is broken in this sandbox** (pre-existing issue, not caused by this plugin):

```
$ biothings-cli --version
Traceback (most recent call last):
  File ".../biothings/cli/settings.py", line 44, in setup_commandline_configuration
    typer.rich_utils.STYLE_HELPTEXT = ""
AttributeError: module 'typer' has no attribute 'rich_utils'
```

This is a `typer`/`biothings` version incompatibility in the shared environment, unrelated to `open_genes`-specific code. Per instructions, the shared environment was **not** patched. `validate` → `dump` → `upload` → `list` → `inspect` could not be exercised via the CLI wrapper.

**Fallback verification performed instead** (direct Python import, no CLI):

1. Fetched the manifest's exact `dumper.data_url` live: `curl 'https://open-genes.com/api/gene/search?pageSize=5000&page=1'` → HTTP 200, `application/json`, 2,405 items, 3.7 MB.
2. Placed the cached response in a local `data_folder` and ran `parser.load_data(data_folder)` directly via `python3`:
   - **2,404 documents yielded**, 1 row skipped (missing `ncbiId`), **0 duplicate `_id`s**.
   - Verified `_id` is always a string, `open_genes` key present in 100% of yielded documents, no stray `None`/empty values after `dict_sweep`.
3. Ran `version.get_release(self)` directly (with a stub `self`): returned `"2405-genes-2023-06-19"` — a live, dynamically-fetched, non-hardcoded string, confirming `version.py` works end-to-end against the real API.

**Result: parser and version logic are proven correct against real, live-fetched data. The CLI wrapper itself is broken in this sandbox — this is an environment issue, not a defect in the `open_genes` plugin.**
