---
name: biothings-plugin-generator
description: >-
  Generate a BioThings data plugin (manifest.json + parser.py) for a given
  datasource. Use when a user wants to create the scaffolding to ingest a
  biomedical datasource into a BioThings API (MyChem, MyGene, MyDisease,
  MyVariant, pending.api, etc.). Works standalone — does not require prior
  evaluation/inspection skills, but will use their outputs if available in
  agent_outputs/. Do not use for non-BioThings data pipelines or general ETL.
  Reference production plugins at
  https://github.com/biothings/pending.api/tree/master/plugins and
  https://github.com/biothings/mydisease.info/tree/master/src/plugins
---

# BioThings Plugin Generator

## When to Use
- User asks to create a BioThings data plugin for a datasource
- User provides a datasource name, download URL, and data format
- After a datasource evaluation/inspection when the user wants to proceed to implementation

## Plugin File Structure
```
<plugin_name>/
├── manifest.json         # Required — defines data URLs, parser reference, metadata
├── parser.py             # Required — parses data, yields documents
├── version.py            # Required — returns the datasource's current release string
└── design_rationale.md   # Required — explains file selection and parser design decisions
```

## Instructions

### 0. Load Reference Files
Before doing anything else, load these files if not already loaded:
- [references/built-plugins-index.md](references/built-plugins-index.md) — check whether this datasource already has a generated plugin; if so, confirm with the user before proceeding
- [references/manifest-schema.md](references/manifest-schema.md) — authoritative manifest field reference
- [references/production-plugin-examples.md](references/production-plugin-examples.md) — real annotated plugins covering all major parser patterns; match the datasource to the closest pattern

### 1. Gather Required Information
Collect the following (prompt the user if missing):
- **Datasource name**: lowercase, underscore-separated (e.g., `ecbd`)
- **Download URL(s)**: direct URLs to the **specific files** needed
- **Data format**: CSV, TSV, JSON, NDJSON, SDF, or other
- **Primary key field**: the field to use as `_id` (e.g., InChIKey for MyChem, gene symbol for MyGene)
- **Target BioThings API**: MyChem.info, MyGene.info, MyDisease.info, MyVariant.info, pending.api, or custom
- **Key data fields**: which fields from the source should be included in the output documents

If a prior site inspection report exists in `agent_outputs/`, load it to extract download URLs, column headers, recommended ingestion path, and file relationship classifications.

### 1b. File Selection Strategy
**Default policy: prefer the most specific download that contains the data the plugin needs.**

Apply the rule in this order:
1. **Per-subset API or download** (e.g. specific endpoint rather than the full interactome)
2. **Per-entity-type bundle** (e.g. independent sub-library files instead of a superset)
3. **Filtered superset** only if (1) and (2) are unavailable
4. **Full superset** only as a last resort

**File relationship types:**
- **Superset**: Contains all records from other files
- **Independent**: Contains unique data NOT found in the superset
- **Subset**: A filtered view of the superset
- **Composite**: Combination of other files

### 1b-gate. Mandatory URL Verification (do NOT skip)
Before writing `manifest.json`, every candidate `data_url` MUST pass this verification.

**Canonical source preference (MUST follow):** If any candidate `data_url` points to a third-party mirror (Zenodo, Figshare, Dryad, GitHub releases, S3 archive), STOP and check the datasource's own download page first (e.g., `datasource.org/download`). Mirrors often host stale snapshots or subset files (e.g., a "lite" CSV when the full version is on the canonical site). Only use a mirror URL if the datasource's own site has no direct bulk download or is access-gated. Flag any mirror usage in `design_rationale.md` with the reason the canonical source was not used.

**Step 1 — Resolve the actual file URL.** Fetch the download page HTML, extract `href` attributes pointing to data files (`.csv`, `.tsv`, `.json`, `.xlsx`, `.zip`, `.gz`, `.sdf`), construct absolute URLs.

**Step 2 — Verify each URL returns data, not HTML.**
```bash
curl -sIL --fail -A "Mozilla/5.0" "<URL>" | grep -i "content-type"
```
- PASS: `content-type` is `text/plain`, `text/csv`, `application/json`, `application/zip`, etc.
- FAIL: `content-type` is `text/html` — this is a web page, not a data file.

**Step 3 — Sample the first few lines** to confirm expected schema:
```bash
curl -skL -A "Mozilla/5.0" "<URL>" | head -3
```

**If no direct-file URL can be found:** Stop and flag as `BLOCKED`. Do NOT generate a plugin with a placeholder URL.

### 1c. Ingestion Strategy — Manifest-First (Bulk Download)
The default — and currently the **only** — supported ingestion strategy is **bulk download via the manifest**. Every generated plugin must declare its data via `dumper.data_url`.

**Decision tree:**
- Bulk CSV/TSV/JSON/SDF download available → use `dumper.data_url` (default path)
- Bulk download requires auth/paywall → stop; flag as openness blocker
- Only a REST API is available → stop and escalate to the user. API-based ingestion is tracked in `BACKLOG.md`

### 2. Generate manifest.json
Always use version `"1.0"`, always include `__metadata__`, and always wire `version.py` via `"release": "version:get_release"` in the `dumper` block.

**Standard manifest template:**
```json
{
    "version": "1.0",
    "requires": ["pandas"],
    "__metadata__": {
        "name": "<datasource display name>",
        "description": "<one sentence describing what this datasource contains>",
        "license": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "url": "https://datasource-homepage.org",
        "publication": {
            "doi": "<doi of the NAR paper describing this datasource>",
            "pmid": "<PubMed ID>",
            "pmc": "<PMC ID if available>"
        }
    },
    "dumper": {
        "data_url": ["<only_the_specific_files_needed>"],
        "uncompress": false,
        "release": "version:get_release"
    },
    "uploader": {
        "parser": "parser:load_data",
        "on_duplicates": "error"
    }
}
```

Pull `doi`, `pmid`, and `pmc` from the datasource's relevancy report (`urls.paper_doi`, `urls.pmid`, `urls.pmc`) if available; otherwise search PubMed. Omit `pmc` if not found. Omit the entire `publication` block only if no paper can be identified.

See [references/manifest-schema.md](references/manifest-schema.md) for the complete field reference and validated examples.

### 2b. Generate version.py
Always generate `version.py` alongside `parser.py`. Its sole job is to return a string identifying the datasource's current release.

**Function signature — always use this exact form:**
```python
def get_release(self):
    import requests
    # query the datasource and return a version string
    ...
```

**How to discover the version source:**
1. Check the site inspection report for a version/release endpoint
2. Check if the datasource API has an info or version endpoint
3. Check if the homepage lists a "last updated" date
4. Check if the bulk download URL contains a date or version string
5. Fall back to fetching the homepage and extracting any visible date/version text

Rules for version.py:
- Function MUST be named `get_release` and accept `self` as the first argument
- MUST return a non-empty string; return `None` only if version truly cannot be determined
- Always import `requests` inside the function body (not at module level)
- Always set a `timeout` on requests (30s recommended)
- Do NOT hardcode the current version — always fetch it dynamically

### 3. Generate parser.py
Create a parser module following BioThings conventions:

```python
import os
import csv
from biothings.utils.dataload import dict_sweep, unlist

def load_data(data_folder):
    """Parse <datasource> data and yield BioThings-compatible documents."""
    infile = os.path.join(data_folder, "<filename>")
    assert os.path.exists(infile), f"Expected file not found: {infile}"

    with open(infile, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            _id = row.get("<primary_key_field>")
            if not _id:
                continue
            doc = {
                "_id": str(_id),
                "<datasource_name>": {
                    # Map source fields to output fields here
                }
            }
            doc = dict_sweep(unlist(doc), [None])
            yield doc
```

**For additional parser patterns** (groupby, pandas, multi-file, JSON, HGVS, cross-API ID resolution), see [references/parser-patterns.json](references/parser-patterns.json).

Rules for parser.py:
- The main parse function MUST accept `data_folder` as its only argument
- The function MUST be a generator (use `yield`, not `return`)
- Every yielded document MUST have an `_id` key (string, unique, max 512 chars)
- All field keys MUST be lowercase with underscores
- Nest all datasource-specific fields under a top-level key matching the datasource name
- Use SDK helpers: `dict_sweep(doc, [None])` removes None/empty values; `unlist(doc)` flattens single-item lists
- For `.gz` files with pandas: `pd.read_csv(filepath, compression='gzip')`
- Convert `numpy.int64` to Python `int` before yielding
- Replace NaN with None: `df = df.where(pd.notnull(df), None)`

### 4. Choose _id Strategy Based on Target API
- **MyChem.info**: InChIKey (e.g., `KTUFNOKKBVMGRW-UHFFFAOYSA-N`)
- **MyGene.info**: NCBI Gene ID (Entrez) or Ensembl Gene ID
- **MyDisease.info**: MONDO ID (e.g., `MONDO:0005015`)
- **MyVariant.info**: HGVS notation
- **pending.api**: Most specific unique ID available. Composite IDs like `f"{id1}-{id2}"` are acceptable.

### 5. Structure Output Documents
- Top-level: `_id` + one key per datasource
- Group related fields into sub-objects
- Use lists for one-to-many relationships
- Cross-references under `xrefs` sub-key
- For association data, use `subject` / `object` / `relation` structure
- For merged multi-row records, use `associatedWith` list pattern

### 6. Save Output Files
```
agent_outputs/<datasource_name>_datasource/<datasource_name>_plugin/
├── manifest.json
├── parser.py
├── version.py
└── design_rationale.md
```

After saving, **update [references/built-plugins-index.md](references/built-plugins-index.md)** by appending a new entry.

### 6a. Generate design_rationale.md (Required)
Always generate `design_rationale.md`. Required sections:
1. **Quick Stats** — top-of-file summary box with key numbers at a glance:
   - Source rows / Documents yielded / Rows skipped (with reason breakdown)
   - Deduplication count
   - Target API
   - Data format and total file size
2. **Why These Dump Files Were Chosen** — selected vs rejected files with reasons
3. **Why the Parser Works the Way It Does** — `_id` strategy, document structure, fields extracted/skipped, deduplication, data cleaning
4. **Sample Output Documents** — 1–2 real documents yielded by the parser, shown as formatted JSON. Pick representative examples (one typical, one edge-case if applicable). For each example, include a **Source cross-reference link** pointing to the record on the datasource's own site so reviewers can compare the parsed output against the original (e.g., `https://ecbd.eu/compound/AQTQHPDCURKLKT-PNYVAJAMSA-N` for an ECBD compound, or the download page URL if per-record links aren't available).
5. **Field Coverage** — for each optional/sparse field, show the % of documents that have it populated (from the `inspect --limit 1000` sample). Use a simple list, e.g.:
   - `xrefs.pubchem`: 96.0%
   - `xrefs.chembl`: 88.6%
   - `xrefs.zinc`: 69.5%
6. **Test Results Summary** — key metrics from biothings-cli test run

### 6b. Optional: parser_report.json (Opt-In)
Generate only when the user opts in via trigger phrases like "initialize run", "with parser report", "include parser report". See the full schema in the original pipeline documentation.

### 7. Validate with biothings-cli
**Required step.** After writing the plugin files, exercise the plugin end-to-end with biothings-cli.

Run these five commands **in order**: `validate` → `dump` → `upload` → `list` → `inspect`.

For the complete step-by-step validation workflow including prerequisites, git setup, hub state cleanup, pass criteria, and failure handling, see [references/cli-validation-workflow.json](references/cli-validation-workflow.json).

**Key rules:**
- Exit-0 with zero documents on `upload` = FAILURE (silent failure mode)
- Always use `-s <plugin_name>` flag with `inspect`
- Use `--limit 1000` for large datasets (>100K docs) during initial verification
- On any failure, stop and surface the error before continuing

## Decision Rules
- Default to singular `uploader` in manifest — use `uploaders` (plural) only for multiple entity types
- If file > 1 GB → streaming or chunked reads
- If `_id` collisions expected → `on_duplicates: "ignore"` or pre-aggregate
- Always `dict_sweep()` + `unlist()` before yielding
- Always use manifest-based bulk download (`dumper.data_url`)
- `.gz` → `uncompress: false`; `.zip` → `uncompress: true`
- Include `__metadata__` with license info
- Multi-file `data_url` list → parser must glob `data_folder` and deduplicate by `_id`
- Always run the §7 biothings-cli workflow end-to-end before declaring a plugin "complete"

## Reference Repositories
- **pending.api**: https://github.com/biothings/pending.api/tree/master/plugins
- **mydisease.info**: https://github.com/biothings/mydisease.info/tree/master/src/plugins
- **BioThings CLI tutorial**: https://docs.biothings.io/en/latest/tutorial/cli.html
