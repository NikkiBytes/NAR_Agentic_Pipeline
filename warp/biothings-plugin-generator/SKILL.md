---
name: biothings-plugin-generator
description: >-
  Generate a BioThings data plugin (manifest.json + parser.py) for a given
  datasource. Use when a user wants to create the scaffolding to ingest a
  biomedical datasource into a BioThings API (MyChem, MyGene, MyDisease,
  MyVariant, pending.api, etc.). Works standalone — does not require prior
  evaluation/inspection skills, but will use their outputs if available in
  agent_outputs/. Reference production plugins at
  https://github.com/biothings/pending.api/tree/master/plugins and
  https://github.com/biothings/mydisease.info/tree/master/src/plugins
---

# BioThings Plugin Generator

## When to Use
- User asks to create a BioThings data plugin for a datasource
- User provides a datasource name, download URL, and data format
- After a datasource evaluation/inspection when the user wants to proceed to implementation

## Plugin File Structure
A BioThings data plugin requires these files:
```
<plugin_name>/
├── manifest.json         # Required — defines data URLs, parser reference, metadata
├── parser.py             # Required — parses data, yields documents
├── version.py            # Required — returns the datasource's current release string
└── design_rationale.md   # Required — explains file selection and parser design decisions
```

Optional files (only add when explicitly requested):
- `mapping.py` — Elasticsearch field mappings (for production Hub deployment)

## Instructions

### 0. Load Reference Files
Before doing anything else, load these files if you have not already:
- [references/built-plugins-index.md](references/built-plugins-index.md) — check whether this datasource already has a generated plugin; if so, confirm with the user before proceeding
- [references/manifest-schema.md](references/manifest-schema.md) — authoritative manifest field reference; use this instead of the manifest rules in Section 2
- [references/production-plugin-examples.md](references/production-plugin-examples.md) — real annotated plugins covering all major parser patterns; match your datasource to the closest pattern and use it as the template

### 1. Gather Required Information
Collect the following (prompt the user if missing):
- **Datasource name**: lowercase, underscore-separated (e.g., `ecbd`)
- **Download URL(s)**: direct URLs to the **specific files** needed — NOT every file the datasource offers. Ask the user which files are relevant. If a prior site inspection exists, use its recommended files.
- **Data format**: CSV, TSV, JSON, NDJSON, SDF, or other
- **Primary key field**: the field to use as `_id` (e.g., InChIKey for MyChem, gene symbol for MyGene)
- **Target BioThings API**: MyChem.info, MyGene.info, MyDisease.info, MyVariant.info, pending.api, or custom
- **Key data fields**: which fields from the source should be included in the output documents

If a prior site inspection report exists in `agent_outputs/`, load it to extract download URLs, CSV column headers, API schema, recommended ingestion path, and file relationship classifications.

### 1b. File Selection Strategy
**Default policy: prefer the most specific download that contains the data the plugin needs.** Only fall back to a full / superset / interactome dump when the specific data is not available as a separate file. A focused per-subset endpoint avoids: (a) ingesting redundant rows, (b) parser failures from schema drift in unrelated fields, (c) wasted dumper bandwidth, and (d) post-hoc filtering that's easy to get wrong.

Apply the rule in this order:
1. **Per-subset API or download** (e.g. `PhosphoSIGNOR/apis/v1/index.php?role=all` rather than the full SIGNOR interactome at `releases/Apr2026_release.txt`)
2. **Per-entity-type bundle** (e.g. ECBD's `bioactives.csv`/`fragments.csv`/`nuisance_set.csv` independent files instead of `ecbd_all.csv`)
3. **Filtered superset** only if (1) and (2) are unavailable — and document the post-filter scope explicitly in the parser
4. **Full superset** only as a last resort, when the data needed is genuinely interspersed with unwanted content and the upstream offers no narrower endpoint

If you select option 3 or 4, record the rationale in the README's "Known Limitations" section and (when `parser_report.json` is generated) in `redundant_fields_skipped[]` so the next person knows the choice was deliberate.

Most datasources offer multiple download files. Classify each before choosing which to include:

**File relationship types:**
- **Superset**: Contains all records from other files (e.g., `ecbd_all.csv` = everything)
- **Independent**: Contains unique data NOT found in the superset (e.g., curated bioactives, fragment library)
- **Subset**: A filtered view of the superset (e.g., "representative diverse set")
- **Composite**: Combination of other files (e.g., pilot library = representative + bioactives + nuisance)

**Decision tree:**
- User wants comprehensive coverage → single superset file, `on_duplicates: "error"`
- User wants only novel/specialized data → independent files only, skip subsets/composites, `on_duplicates: "ignore"`
- Unclear → ask user, or default to independent files with novel content

**How to classify files (when no prior inspection exists):**
1. Fetch the download page and list all available files with their descriptions
2. Compare record counts: if file A has 100K rows and file B has 2K, B is likely a subset or independent set
3. Check if file descriptions say "subset of", "representative", "selected from" → subset
4. Check if files are described as separately curated/designed → independent
5. Download CSV headers from each file (just the first line) to confirm schema compatibility

**How to use prior inspection reports:**
If `agent_outputs/` contains a prior inspection report (from a site-inspector or datasource-evaluator skill), it should include:
- A catalog of all available download files with URLs, sizes, and descriptions
- File relationship classifications (superset/independent/subset/composite)
- Recommended files for ingestion
- CSV column headers for each file

Load and use these classifications directly instead of re-discovering them.

### 1b-gate. Mandatory URL Verification (do NOT skip)
Before writing `manifest.json`, every candidate `data_url` MUST pass this verification. This is a hard gate — if a URL fails, do NOT put it in the manifest.

**Canonical source preference (MUST follow):** If any candidate `data_url` points to a third-party mirror (Zenodo, Figshare, Dryad, GitHub releases, S3 archive), STOP and check the datasource's own download page first (e.g., `datasource.org/download`). Mirrors often host stale snapshots or subset files (e.g., a "lite" CSV when the full version is on the canonical site). Only use a mirror URL if the datasource's own site has no direct bulk download or is access-gated. Flag any mirror usage in `design_rationale.md` with the reason the canonical source was not used.

**Step 1 — Resolve the actual file URL.** Many datasource download pages are JS-rendered, PHP-backed, or redirect chains. You must discover the terminal direct-file URL, not the landing page.
- Fetch the download page HTML (try `curl -skL` if SSL is broken on academic servers)
- Extract `href` attributes pointing to data files (`.csv`, `.tsv`, `.txt`, `.json`, `.xlsx`, `.zip`, `.gz`, `.sdf`)
- Construct absolute URLs from relative paths (e.g., `/sites/files/data.txt` → `https://domain.org/sites/files/data.txt`)

**Step 2 — Verify each URL returns data, not HTML.**
```bash
curl -sIL --fail -A "Mozilla/5.0" "<URL>" | grep -i "content-type"
```
- PASS: `content-type` is `text/plain`, `text/csv`, `text/tab-separated-values`, `application/json`, `application/octet-stream`, `application/zip`, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- FAIL: `content-type` is `text/html` — this is a web page, not a data file. Go back to Step 1.
- FAIL: HTTP 000 / connection error — server unreachable. Flag in inspection report, try with `-k` (insecure) for old academic servers. If still fails, the URL cannot be used in the manifest.

**Step 3 — Sample the first few lines** to confirm the file has the expected schema:
```bash
curl -skL -A "Mozilla/5.0" "<URL>" | head -3
```
- Confirm column headers match what the parser expects
- Confirm the delimiter (tab vs comma) matches the parser logic

**Rejection criteria — NEVER put these in `data_url`:**
- Generic download pages: `Download.php`, `/download`, `/downloads`
- API documentation pages: `/api-documentation`, `/api/docs`
- Landing pages or homepages that return HTML
- URLs that require POST requests, session cookies, or JavaScript execution to return data
- URLs returning HTTP 000 (unreachable) from the agent's network — flag as BLOCKED in the inspection report

**If you cannot find a direct-file URL:** Stop and flag the datasource as `BLOCKED` in the site inspection. Do NOT generate a plugin with a placeholder URL. Instead, document in `design_rationale.md` what you tried and recommend the user manually download the file and pre-place it in `data_folder`.

**Multi-file manifest pattern:**
When using multiple files, set `data_url` as a list. All files land in the same `data_folder`, so the parser must iterate all matching files:
```json
{
    "dumper": {
        "data_url": [
            "https://example.org/data/bioactives.csv",
            "https://example.org/data/fragments.csv"
        ]
    },
    "uploader": {
        "parser": "parser:load_data",
        "on_duplicates": "ignore"
    }
}
```

### 1c. Ingestion Strategy — Manifest-First (Bulk Download)
The default — and currently the **only** — supported ingestion strategy for generated plugins is **bulk download via the manifest**. Every generated plugin must declare its data via `dumper.data_url` pointing at the datasource's canonical bulk release artifact(s), matching the pattern used by the production example plugins (DISEASES, DisGeNET, FoodData, etc.). The manifest always loads this way.

**Why manifest-first:**
- All reference production plugins use `dumper.data_url` for canonical release artifacts
- Keeps plugins simple, reproducible, and compatible with the Hub's release detection via `version.py`
- Avoids custom `dumper.py` code paths that are not yet standardized in this generator

**Decision tree:**
- Bulk CSV/TSV/JSON/SDF download available at a direct URL → use `dumper.data_url` (this is the default path for every plugin)
- Bulk download requires auth, paywall, or click-through → stop; flag as an openness blocker in the relevancy evaluation
- Only a REST API is available, no bulk download → stop and escalate to the user. API-based ingestion (custom `dumper.py`) is tracked in `BACKLOG.md` and is NOT produced by this generator today

**API availability is still worth recording — but not for ingestion here.**
When an upstream `datasource-relevancy-analysis` or `datasource-site-inspection` runs, it should check and record whether a public API exists. That signal feeds:
- Relevancy/novelty scoring (an API often indicates actively maintained data)
- The backlog item for future API-first dumpers

Do NOT consume the API as the ingestion source in the generated plugin. If a prior inspection report in `agent_outputs/` documents an API, note it in the generated `README.md` under "Known limitations / future work" and continue with the bulk-download manifest.

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
        "url": "https://datasource-homepage.org"
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

Rules for manifest.json:
- `version`: Always `"1.0"`. This is the manifest spec version, not the datasource version.
- `__metadata__`: **Always include.** Must have `name`, `description`, `license`, `license_url`, and `url` (datasource homepage). Optional `author` object with `name` and `url`.
- `requires`: List Python packages the parser needs (e.g., `["pandas"]`). Omit the key entirely if only stdlib + biothings SDK are needed.
- `dumper.data_url`: Single string URL or list of URLs. **Only include the specific files the parser needs** — not every file the datasource offers. Must be direct-download links.
- `dumper.uncompress`: Set `true` only for `.zip` files. For `.gz` files that pandas reads natively via `compression='gzip'`, set `false`.
- `uploader` (singular): Standard form. Contains `parser`, `on_duplicates`, and optionally `mapping`.
- `uploaders` (plural, list): Only when multiple parsers process different entity types. Each needs a `name` field.
- `on_duplicates`: Use `"error"` for most plugins. Use `"ignore"` only when the same `_id` legitimately appears from multiple source IDs.
- `parser`: Format is `"module:function"`. Standard is `"parser:load_data"`. Can reference shared parsers like `"hub.dataload.data_parsers:load_obo"`.
- `parser_kwargs`: Optional dict passed to parser function. Used with shared parsers (e.g., `{"obofile": "doid.obo", "prefix": "DOID"}`)

**Reference:** https://github.com/biothings/mydisease.info/blob/master/src/plugins/disgenet/manifest.json

### 2b. Generate version.py
Always generate a `version.py` alongside `parser.py`. Its sole job is to return a string identifying the datasource's current release so the Hub can detect when new data is available.

**Function signature — always use this exact form:**
```python
def get_release(self):
    import requests
    # query the datasource and return a version string
    ...
```

**How to discover the version source:**
1. Check the site inspection report in `agent_outputs/` — it may document a version/release endpoint
2. Check if the datasource API has an info or version endpoint (e.g., `/api/version`, `/api/info`, `/ContentService/data/database/version`)
3. Check if the datasource homepage or a summary URL lists a "last updated" date
4. Check if the bulk download URL contains a date or version string that changes on each release
5. If none of the above: fall back to fetching the homepage and extracting any visible date/version text

**Common patterns:**

```python
# Pattern A: dedicated version/release endpoint returns version directly
def get_release(self):
    import requests
    resp = requests.get("https://datasource.org/api/version", timeout=30)
    resp.raise_for_status()
    return str(resp.json())

# Pattern B: info/summary endpoint — parse date or version from text
def get_release(self):
    import requests
    resp = requests.get("https://datasource.org/api/info", timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("release") or data.get("version") or data.get("date")

# Pattern C: parse a date from a plain-text summary page
def get_release(self):
    import requests
    resp = requests.get("https://datasource.org/summary.txt", timeout=30)
    resp.raise_for_status()
    for line in resp.text.split("\n"):
        if line.startswith("Release:") or line.startswith("Date:"):
            return line.split(":", 1)[-1].strip().replace("-", "")

# Pattern D: version embedded in the download URL (e.g., dated filenames)
# If data_url is "https://datasource.org/releases/2026-04/data.tsv",
# fetch the releases index and extract the latest date:
def get_release(self):
    import re, requests
    resp = requests.get("https://datasource.org/releases/", timeout=30)
    resp.raise_for_status()
    dates = re.findall(r"(\d{4}-\d{2})", resp.text)
    return max(dates) if dates else None
```

Rules for version.py:
- Function MUST be named `get_release` and accept `self` as the first argument (Hub calls it as a bound method)
- MUST return a non-empty string; return `None` only if version truly cannot be determined
- Always import `requests` inside the function body (not at module level) — Hub convention
- Always set a `timeout` on requests (30s recommended)
- The returned string should be comparable across releases so the Hub can detect changes (dates as `YYYYMMDD`, integers as strings, semantic versions as strings)
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

Rules for parser.py:
- The main parse function MUST accept `data_folder` as its only argument (unless `parser_kwargs` is used)
- The function MUST be a generator (use `yield`, not `return`)
- Every yielded document MUST have an `_id` key (string, unique, max 512 chars)
- All field keys MUST be lowercase with underscores. Clean keys: `key.lower().replace(" ", "_").replace("/", "_")`
- Nest all datasource-specific fields under a top-level key matching the datasource name
- Use SDK helpers: `dict_sweep(doc, [None])` removes None/empty values; `unlist(doc)` flattens single-item lists
- Also available: `value_convert_to_number()`, `merge_duplicate_rows()`, `to_boolean()`
- Use `biothings.utils.common.open_anyfile` to transparently handle .gz files without pandas
- For `.gz` files with pandas: `pd.read_csv(filepath, compression='gzip')`
- For large files, use streaming (`csv.DictReader`) or chunked reads (`pd.read_csv(chunksize=100000)`)
- Convert `numpy.int64` to Python `int` before yielding
- Replace NaN with None: `df = df.where(pd.notnull(df), None)`
- Follow BioThings code style: PEP8, max line length 160, import groups (stdlib / third-party / biothings)

### 4. Choose _id Strategy Based on Target API
- **MyChem.info**: InChIKey (e.g., `KTUFNOKKBVMGRW-UHFFFAOYSA-N`)
- **MyGene.info**: NCBI Gene ID (Entrez) or Ensembl Gene ID
- **MyDisease.info**: MONDO ID (e.g., `MONDO:0005015`). Map from DOID/UMLS/MESH if needed.
- **MyVariant.info**: HGVS notation (use `myvariant.src.utils.hgvs.get_hgvs_from_vcf()`)
- **pending.api**: Most specific unique ID available. Composite IDs like `f"{id1}-{id2}"` are acceptable.

Common ID mapping patterns:
- UMLS/MESH/OMIM → MONDO: Parse `mondo.json` xrefs
- DOID → MONDO: Use `biothings_client.get_client('disease').querymany()`
- Gene symbol/ENSEMBL → Entrez: Use mygene.info queries

### 5. Structure Output Documents
- Top-level: `_id` + one key per datasource
- Group related fields into sub-objects
- Use lists for one-to-many relationships
- Cross-references under `xrefs` sub-key
- For association data, use `subject` / `object` / `relation` structure (FoodData pattern)
- For merged multi-row records, use `associatedWith` list pattern (DISEASES pattern)

### 6. Save Output Files
```
agent_outputs/<datasource_name>_datasource/<datasource_name>_plugin/
├── manifest.json
├── parser.py
├── version.py
├── README.md
└── design_rationale.md
```

The `_datasource/` folder should already exist from the relevancy evaluation and site inspection steps — create it if not. README.md should include: datasource name/URL, what the plugin does, `biothings-cli` test commands, example document, known limitations.

After saving, **update [references/built-plugins-index.md](references/built-plugins-index.md)** by appending a new entry using the template at the bottom of that file.

### 6a. Generate design_rationale.md (Required)
Always generate a `design_rationale.md` alongside the other plugin files. This report documents the reasoning behind file selection and parser design so that future maintainers (or automated reviewers) can understand why the plugin was built this way.

**Required sections:**

**1. Why These Dump Files Were Chosen**
- List how many files the datasource offers in total vs how many the plugin uses
- For each **selected file**: state its name, size, record count, format, and why it was chosen (e.g., "only file containing drug-disease relationships", "enrichment lookup table")
- For each **rejected file**: state its name and one-line reason for exclusion (e.g., "raw upstream input already merged into the indication list", "subset of the flexible list with no unique data")
- End with a decision summary paragraph explaining the overall file selection logic

**2. Why the Parser Works the Way It Does**
Cover each of these sub-topics with bullet points:
- **`_id` strategy**: what the composite/primary key is, why this key was chosen, and how it maps to the target API
- **Document structure**: which BioThings pattern was used (subject/object/relation, associatedWith, flat entity) and why
- **Fields extracted**: for each source file, list what fields the parser pulls and what each one provides
- **Fields deliberately skipped**: list columns/fields the parser ignores and why (e.g., redundant, inconsistently formatted, not relevant to BioThings)
- **Deduplication logic**: how duplicates are detected and handled, how many were found in testing
- **Data cleaning**: what `dict_sweep`/`unlist`/type conversions are applied

**3. Test Results Summary**
A table with key metrics from the biothings-cli test run:
- Source row count, documents yielded, duplicates removed, parsing errors
- Enrichment rate (if applicable)
- Pass/fail status for each biothings-cli step (validate, dump, upload, inspect)

**Formatting rules:**
- Use markdown with clear headings and bullet points
- Be specific — cite actual file names, column names, record counts, and CURIE prefixes
- Keep it factual — this is a technical reference, not marketing copy
- Aim for 80-120 lines; enough detail to reconstruct the reasoning, not so much that it's redundant with the code

### 6b. Optional: parser_report.json (Opt-In)
Generate a machine-readable `parser_report.json` alongside the four required files **only when the user opts in** via a trigger phrase. Detect the opt-in from the user's invocation; matching phrases include (case-insensitive substring match):
- `initialize run`
- `init run`
- `with parser report`
- `with parser_report`
- `include parser report`
- `with structured report`
- `with json report`

When the trigger fires, write `parser_report.json` to the same plugin directory:
```
agent_outputs/<datasource_name>_datasource/<datasource_name>_plugin/
├── manifest.json
├── parser.py
├── version.py
├── README.md
└── parser_report.json    # opt-in only
```

**Required schema** (use these top-level keys; omit a key only if its value is genuinely unknown):
```json
{
    "plugin_name": "<datasource_name>",
    "datasource_name": "<full display name>",
    "datasource_homepage": "<URL>",
    "generated_date": "YYYY-MM-DD",
    "generator": "biothings-plugin-generator",
    "plugin_version": "1.0",
    "target_api": "MyChem.info | MyGene.info | MyDisease.info | MyVariant.info | pending.api",
    "id_strategy": {
        "type": "InChIKey | NCBI Entrez Gene ID | MONDO ID | HGVS | composite | other",
        "source_field": "<column or JSON path>",
        "primary_key_join": "<BioThings field this _id joins to, e.g. mygene.entrezgene>"
    },
    "data_format": "CSV | TSV | gzipped TSV | JSON | NDJSON | SDF | Excel | other",
    "files_ingested": [
        {"name": "<filename>", "url": "<download URL>", "size_bytes": 0, "purpose": "<one-line role>"}
    ],
    "parser_pattern": "simple CSV | groupby aggregation | pandas groupby | multi-file glob | API dump-then-parse | shared OBO parser | other",
    "on_duplicates": "error | ignore",
    "requires": ["<python package>"],
    "version_strategy": "<one-line description of how version.py determines the release>",
    "smoke_test": {
        "run_date": "YYYY-MM-DD",
        "status": "passed | failed | not_run",
        "documents_yielded": 0,
        "unique_ids": 0,
        "total_associations": 0,
        "exceptions": [],
        "sample_document": {},
        "cli_validation": {
            "runner": "biothings-cli",
            "runner_version": "<output of `biothings-cli --version`>",
            "steps": [
                {"command": "dataplugin validate",  "status": "passed | failed | skipped", "summary": "<one-line outcome>", "errors": []},
                {"command": "dataplugin dump",      "status": "passed | failed | skipped", "summary": "<archive folder + file list>", "errors": []},
                {"command": "dataplugin upload",    "status": "passed | failed | skipped", "summary": "<collection name + doc count>", "errors": []},
                {"command": "dataplugin list",      "status": "passed | failed | skipped", "summary": "<dump+upload state confirmed>", "errors": []},
                {"command": "dataplugin inspect",   "status": "passed | failed | skipped", "summary": "<sample doc shape verified>", "errors": []}
            ]
        }
    },
    "license": {
        "name": "<license short name>",
        "url": "<license URL>",
        "biothings_compatibility": "compatible | needs_review | incompatible",
        "notes": "<NC/SA/commercial-API caveats, etc.>"
    },
    "novel_fields": ["<field that's net-new vs existing BioThings sources>"],
    "redundant_fields_skipped": ["<dataset/field intentionally not ingested because already in BioThings>"],
    "known_limitations": ["<bullet>"],
    "prior_artifacts": [
        {"type": "relevancy | site_inspection", "path": "<relative path under agent_outputs/>"}
    ]
}
```

**Rules**:
- Always include `plugin_name`, `datasource_name`, `generated_date`, `target_api`, `id_strategy`, `data_format`, `files_ingested`, `parser_pattern`, `on_duplicates`, `version_strategy`, and `license`
- `smoke_test` is required when the generator runs a live parse during plugin development; set `status: "not_run"` if skipped (e.g. login-gated downloads)
- `sample_document` should be a **real document yielded by the parser** during the smoke test, not a hand-crafted example. Truncate large nested arrays to ≤5 items if the doc would otherwise exceed ~3 KB
- Keys with null/empty values may be omitted (apply `dict_sweep`-style cleanup before writing)
- File must be valid JSON (UTF-8, 2-space indent recommended for diffability)
- The report is for downstream automation (CI checks, cross-plugin dashboards, registry indexing). Do NOT duplicate large prose — that belongs in `README.md`
- Mention the report exists in the README's "Plugin Files" list when it is produced

### 7. Validate the Generated Plugin with biothings-cli
**Required step.** After writing the four/five plugin files, exercise the plugin end-to-end with the BioThings CLI to confirm the manifest, dumper, parser, and version detector all work together against live data. This catches the silent-failure modes the parser-only smoke test (§6b) cannot — manifest schema errors, network failures during dump, parser exceptions on real data, and uploaded-document shape regressions.

#### 7.0 Prerequisites
```bash
pip install "biothings[cli]"
biothings-cli --version          # confirm install; capture this for parser_report.json
cd agent_outputs/<datasource_name>_datasource/<datasource_name>_plugin/
```
The CLI uses a local SQLite-backed `data_src_database` and an `archive/` folder under `.biothings_hub/` inside the plugin directory — no external services needed.

**Git repository setup (required).** `biothings-cli` internally calls `git rev-list` and `git remote` to detect plugin identity and version. These calls fail silently or fatally if the plugin directory is not a proper git repo. **Always run the following before any CLI command:**
```bash
# Skip if the plugin directory already has commits on the current branch
git init                           # no-op if .git/ already exists
git add manifest.json parser.py version.py README.md
git commit -m "Initial plugin files"  --allow-empty
git remote add origin /dev/null 2>/dev/null || true   # dummy origin; no push needed
```
- `git init` + initial commit: satisfies `git rev-list -1 <branch>` which biothings-cli runs during upload.
- Dummy `origin` remote: satisfies `git remote` lookups. Points to `/dev/null` — nothing is ever pushed.
- These are local-only operations. No GitHub repo or remote push is required.

**Clean hub state (required on re-runs).** If `.biothings_hub/` exists from a previous run (especially a failed one), stale SQLite locks or cached "canceled" status will cause new uploads to fail. **Always clean before re-running the pipeline:**
```bash
# Safe to run even on first run (files won't exist yet)
rm -f .biothings_hub/data_src_database .biothings_hub/data_src_database-journal .biothings_hub/biothings_hubdb
```
- `data_src_database-journal`: SQLite WAL/journal lock left by an interrupted upload.
- `data_src_database`: the collection store; must be recreated after removing the journal.
- `biothings_hubdb`: hub metadata that caches "stale" / "canceled" status from prior failures.
- Archive data files (`.biothings_hub/archive/`) are safe to keep — only metadata/DB files need clearing.

Run the five commands below **in order**. Each step's pass/fail outcome must be recorded in `parser_report.json` under `smoke_test.cli_validation.steps[]` (when the user opted into the report per §6b). On any failure, stop the workflow and surface the error to the user before continuing.

#### 7.1 `dataplugin validate` — manifest schema check
```bash
biothings-cli dataplugin validate
```
- **Purpose**: lints `manifest.json` against the BioThings manifest schema. Catches missing `__metadata__`, malformed `data_url`, missing `release` wiring, parser-reference typos.
- **Pass criterion**: exit code 0; no "ERROR" or "FAIL" lines in stdout/stderr.
- **Common failures**: `parser` reference points at a function that doesn't exist in `parser.py`; `data_url` is not a string or list of strings; `__metadata__.url` missing.
- **On failure**: record the validation errors in `cli_validation.steps[].errors[]` and stop — do not run `dump`.

#### 7.2 `dataplugin dump` — download data + exercise version.py
```bash
biothings-cli dataplugin dump
```
- **Purpose**: invokes `version.py:get_release()` to detect the current release, then downloads every URL in `dumper.data_url` into `.biothings_hub/archive/<plugin>/<release_string>/`.
- **Pass criterion**: exit code 0; archive folder exists; every declared `data_url` file is present and non-empty.
- **Common failures**: version.py returns `None` (Hub falls back to a date string but logs a warning); HTTP 4xx/5xx on a `data_url`; `uncompress: true` fails because the file isn't a zip.
- **On failure**: capture the offending URL + HTTP status in `cli_validation.steps[].errors[]`. If a single URL in a list fails, the whole dump fails — fix the URL or remove it from the manifest before retrying.

#### 7.3 `dataplugin upload` — run the parser, write to local DB
```bash
biothings-cli dataplugin upload
```
- **Purpose**: runs `parser.load_data(data_folder)` against the dumped files and writes yielded documents into the SQLite collection `<plugin_name>` under `data_src_database`.
- **Pass criterion**: exit code 0; final log line shows non-zero document count; collection appears in subsequent `list` output.
- **Common failures**: parser raises (caught and logged — always check stderr even on exit 0); zero documents yielded (silent failure mode — see SIGNOR v1.0 case); duplicate `_id` errors when `on_duplicates: error`; document exceeds Hub size limits.
- **On failure**: record the parser exception (if any) and the final document count. **A successful exit with `documents_yielded == 0` is treated as FAILURE** — add a `discrepancies[]` entry to `smoke_test` flagging the silent-zero-doc condition.

#### 7.4 `dataplugin list` — verify accumulated state
```bash
biothings-cli dataplugin list
```
- **Purpose**: prints two boxed sections — `Dump` (source + data folder + file list) and `Upload` (database path + collection name + archived collections + temporary collections). No mutations; pure inspection.
- **Pass criterion**: both `Dump` and `Upload` boxes are populated; `Collections` line lists `<plugin_name>`; data folder shows the expected files from §7.2.
- **Common findings**: archived collections accumulate across re-runs (named `<plugin>_archive_<YYYYMMDD>_<token>`) — not a failure, but worth pruning periodically.
- **On failure**: if `Collections` is empty after a successful upload, the upload silently dropped all docs — investigate via `inspect`.

#### 7.5 `dataplugin inspect` — sample document shape verification
```bash
# Basic form — use -s when prompted (required when multiple uploaders/collections exist)
biothings-cli dataplugin inspect -s <plugin_name>

# For large datasets (>100K docs): limit the sample to avoid long waits
biothings-cli dataplugin inspect -s <plugin_name> --limit 1000
```
- **Purpose**: pulls a sample of yielded documents from the collection and reports field-level statistics (key presence, type distribution, value ranges) to verify the parser's output schema matches expectations.
- **Pass criterion**: every yielded document has an `_id` of type `string`; the top-level datasource key (e.g. `harmonizome`, `signor`, `ecbd`) is present in 100% of sampled documents; no fields are unexpectedly all-null.
- **`-s` flag**: always provide `-s <plugin_name>`. The CLI requires it when multiple uploaders exist and errors with `--sub-source-name must be provided` without it. Safe to always include.
- **`--limit` flag for large datasets**: for collections with >100K documents, a full inspection is slow and unnecessary for schema validation. Use `--limit 1000` to `--limit 10000` for initial verification. The tradeoff: rare fields (e.g., xref categories appearing in <1% of compounds) may not surface in small samples. Use `--limit 10000` as a good balance; omit `--limit` only for the final comprehensive check if needed.
- **Common findings**: stray `None` values not cleaned by `dict_sweep`; `_id` mistakenly stored as integer instead of string; nested dicts with a single key (should have been flattened by `unlist`).
- **On failure**: record the offending field-level statistics in `cli_validation.steps[].errors[]` and surface to the user as a parser fix-up task.

#### 7.6 Optional: re-run cycle / cleanup
Between iterations during plugin development:
```bash
# Discard archived collections to keep the local DB tidy
rm -rf .biothings_hub/archive/<plugin_name>/<old_release_string>/
# Re-run dump+upload after parser changes
biothings-cli dataplugin dump && biothings-cli dataplugin upload
```

#### 7.7 Recording results in `parser_report.json`
When the user opted into the report per §6b, populate `smoke_test.cli_validation` with one entry per command above. Status values:
- `passed`: command exited 0 AND its specific pass criterion was met
- `failed`: command exited non-zero, OR exited 0 but its pass criterion failed (e.g. zero documents on `upload`)
- `skipped`: command was not run (typically because an earlier step failed and the workflow halted)

The `cli_validation` block lives inside `smoke_test`; the overall `smoke_test.status` should be `passed` only when all five CLI steps pass. Any failed step bubbles up to `smoke_test.status: "failed"` and is duplicated as a `discrepancies[]` entry with severity `critical` if the failure was silent (zero docs, missing collection) or `warning` if loud (HTTP error, validation error).

## Common Patterns (from production plugins)

### Simple CSV/TSV with groupby (DISEASES pattern)
```python
import os, csv
from itertools import groupby
from operator import itemgetter

def load_data(data_folder):
    infile = os.path.join(data_folder, "data.tsv")
    rows = []
    with open(infile) as f:
        for row in csv.DictReader(f, delimiter='\t'):
            rows.append(row)
    rows = sorted(rows, key=itemgetter('disease_id'))
    for key, group in groupby(rows, key=itemgetter('disease_id')):
        merged = [doc for doc in group]
        yield {"_id": key, "source": {"associatedWith": merged}}
```

### Pandas groupby for multi-row aggregation (DisGeNET pattern)
```python
import os
from collections import defaultdict
import pandas as pd
from biothings.utils.dataload import dict_sweep, unlist

def load_data(data_folder):
    df = pd.read_csv(os.path.join(data_folder, "data.tsv.gz"),
                     sep="\t", comment="#", compression="gzip")
    df = df.where(pd.notnull(df), None)
    d = defaultdict(list)
    for grp, subdf in df.groupby(["diseaseId", "source", "geneId"]):
        records = subdf.to_dict(orient="records")
        doc = {"source": grp[1], "gene_id": int(grp[2]), "pubmed": []}
        for rec in records:
            if rec.get("pmid"):
                doc["pubmed"].append(int(rec["pmid"]))
        d[grp[0]].append(doc)
    for _id, records in d.items():
        yield dict_sweep(unlist({"_id": _id, "source": {"genes": records}}), [None])
```

### Variant HGVS ID generation (CCLE/FIRE pattern)
```python
import os, logging
from biothings.utils.common import open_anyfile
import myvariant.src.utils.hgvs as hgvs

def load_data(data_file):
    with open_anyfile(data_file) as f:
        for line in f:
            try:
                parts = line.strip().split("\t")
                _id = hgvs.get_hgvs_from_vcf(parts[0], parts[1], parts[2], parts[3])
                yield {"_id": _id, "source": {"score": float(parts[4])}}
            except Exception as e:
                logging.error("Error with line %s: %s" % (line.strip(), e))
```

### Cross-API ID resolution (DISEASES pattern)
```python
from biothings_client import get_client

def batch_query_mondo_from_doid(doid_list):
    client = get_client('disease')
    mapping = {}
    for i in range(0, len(doid_list), 1000):
        batch = doid_list[i:i+1000]
        res = client.querymany(batch, scopes="mondo.xrefs.doid", fields="_id")
        for doc in res:
            mapping[doc['query']] = doc.get('_id', doc['query'])
    return mapping
```

### Multi-file CSV with deduplication (ECBD pattern)
Use when `data_url` is a list of CSVs with potential ID overlap between files:
```python
import os, csv, glob, logging
from biothings.utils.dataload import dict_sweep, unlist

logger = logging.getLogger(__name__)

def load_data(data_folder):
    csv_files = sorted(glob.glob(os.path.join(data_folder, "*.csv")))
    assert csv_files, f"No CSV files found in {data_folder}"
    seen_ids = set()
    for infile in csv_files:
        logger.info("Parsing %s", os.path.basename(infile))
        for doc in _parse_csv(infile, seen_ids):
            yield doc

def _parse_csv(filepath, seen_ids):
    with open(filepath, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            _id = row.get("id_field")
            if not _id or _id in seen_ids:
                continue
            seen_ids.add(_id)
            doc = {"_id": _id, "source": {"field": row.get("field")}}
            yield dict_sweep(unlist(doc), [None])
```

### JSON with orjson (FoodData pattern)
```python
import os, orjson

def load_data(data_folder):
    with open(os.path.join(data_folder, "data.json"), "rb") as f:
        data = orjson.loads(f.read())
    for record in data:
        yield {"_id": str(record["id"]), "source": record}
```

### Pre-dumped JSON files pattern
Use when the `data_folder` contains one or more JSON files (for example, manually pre-dumped API results staged into the folder by a user). The generator itself still uses manifest-based bulk download — this pattern only covers the parser side:
```python
# parser.py — reads JSON files staged in data_folder
import os, json, glob, logging
from biothings.utils.dataload import dict_sweep, unlist

logger = logging.getLogger(__name__)

def load_data(data_folder):
    json_files = sorted(glob.glob(os.path.join(data_folder, "*.json")))
    assert json_files, f"No JSON files found in {data_folder}"
    for jf in json_files:
        logger.info("Parsing %s", os.path.basename(jf))
        with open(jf, "r") as f:
            records = json.load(f)
        for rec in records:
            _id = rec.get("id") or rec.get("_id")
            if not _id:
                continue
            doc = {
                "_id": str(_id),
                "source": rec  # adapt: nest under datasource key, clean fields
            }
            yield dict_sweep(unlist(doc), [None])
```
Automated API-crawling `dumper.py` support is backlog — see `BACKLOG.md`.

## Decision Rules
- Default to singular `uploader` in manifest — standard across both pending.api and mydisease.info
- Use plural `uploaders` only for multiple entity types from the same dump
- If file > 1 GB → streaming or chunked reads
- If `_id` collisions expected → `on_duplicates: "ignore"` or pre-aggregate with `defaultdict(list)` + `groupby`
- If source uses non-standard IDs → build mapping or use `biothings_client`
- Always `dict_sweep()` + `unlist()` before yielding
- Always use manifest-based bulk download (`dumper.data_url`) — matches every reference production plugin; API-based ingestion is backlog (see `BACKLOG.md`)
- If a datasource has only an API and no bulk download, stop and escalate to the user — do NOT generate a custom `dumper.py` in this skill
- Record API availability in the relevancy/site-inspection report even though it is not used for ingestion here
- `.gz` → `uncompress: false`, let pandas handle; `.zip` → `uncompress: true`
- Include `__metadata__` with license info
- Multi-file sources: classify files as superset/independent/subset/composite, then select only what's needed
- Multi-file `data_url` list → parser must glob `data_folder` and deduplicate by `_id` with a `seen_ids` set
- Check `agent_outputs/` for prior inspection reports before re-discovering file relationships
- Always run the §7 biothings-cli workflow (`validate` → `dump` → `upload` → `list` → `inspect`) end-to-end before declaring a plugin "complete"; treat exit-0-with-zero-documents on `upload` as FAILURE

## Reference Repositories
- **pending.api**: https://github.com/biothings/pending.api/tree/master/plugins
- **mydisease.info**: https://github.com/biothings/mydisease.info/tree/master/src/plugins
- **BioThings CLI tutorial**: https://docs.biothings.io/en/latest/tutorial/cli.html
- **BioThings code style**: PEP8, max line 160, flake8: `ignore=E226,E265,E302,E402,E731,F821,W503`
