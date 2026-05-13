---
name: datasource-site-inspection
description: >-
  Inspect a datasource's download files to verify ingestion suitability for a
  BioThings plugin. Finds the download file URLs, samples the data schema, and
  confirms the fields are relevant and novel for BioThings. Use after a
  datasource-relevancy-analysis has been completed. Produces a structured
  VERIFIED / PARTIALLY_VERIFIED / BLOCKED report.
---

# Datasource Site Inspection

## Goal
Answer three questions:
1. **Can we get the data?** — Are the download files publicly accessible (direct URL, no login required)?
2. **What's in the files?** — What are the field names, types, and a few sample values?
3. **Is it worth ingesting?** — Are those fields relevant and novel for a BioThings plugin?

This report feeds directly into the plugin generator. The most important outputs are the confirmed download URL(s) and the field schema.

## Tools to Use
1. **`fetch_web_pages`** — try the download page URL and any direct file URLs first.
2. **`exa_web_search`** — fallback if the download page is JS-rendered or returns no content.
3. **Local paper PDF** — read it for the Data Availability / Methods section if the site is opaque. This is often the most reliable source of file format and schema.

Do NOT parse JS bundles, reverse-engineer network layers, or dig into web app architecture.

## Prerequisites
- **Load the prior relevancy JSON** from `agent_outputs/<datasource>_datasource/<datasource>_relevancy.json`. If only a `.md` exists (legacy), parse it for: stated download URL, file format, key fields, license.
- **Check `agent_outputs/pipeline_state.json`** — confirm this datasource has `verdict: RECOMMEND_INGEST` or `NEEDS_REVIEW`. If `DO_NOT_INGEST`, warn the user and stop unless they override.
- **Check for a local paper PDF** in `agent_outputs/<datasource>_datasource/` or ask the user. Read it if present.
- **If the user provides local file paths** (already downloaded), skip access checks and go straight to schema inspection.

## Instructions

### 1. Find the Download Files
From the relevancy report, paper, or download page URL:
- List each available download file with its URL, format, and description
- Confirm each URL is directly accessible (no login, no redirect to a registration wall)
- **If any file requires login/registration → status = BLOCKED. Stop here and report.** Do not attempt to work around auth gates.

### 2. Sample the Data Schema
For each accessible download file:
- If the file is small enough, fetch it directly with `fetch_web_pages`
- If it's a large flat file (TSV/CSV/JSON), fetch just the header row or first few lines using a range/byte request if possible, or use `exa_web_search` to find any published schema documentation
- If the user has a local copy, read the first 20–50 lines with `read_files`
- Record: column names / JSON keys, data types, 2–3 sample values per key field

### 3. Assess Relevance and Novelty for BioThings
For each field found in step 2:
- **Identify BioThings-mappable identifiers** (InChIKey, Entrez Gene ID, HGVS, MONDO ID, RS number, HGVS, etc.) — these determine which BioThings API the plugin targets
- **Flag novel fields** — fields that carry information not already present in existing BioThings sources (compare to claims in the relevancy report)
- **Flag redundant fields** — fields that duplicate what's already in BioThings (e.g., re-annotating gnomAD AF when BioThings already has it)
- Confirm the primary key strategy: which field becomes `_id`, and does it map to MyVariant / MyGene / MyChem / MyDisease?

### 4. Verify License
- Confirm the license from the download page or paper matches the relevancy report
- Note any NC/ND restrictions that affect redistribution

### 5. Compare Paper Claims vs Reality
If a prior evaluation exists, check each claim:
- Entity counts: paper says X, site shows Y
- Formats: paper says CSV/JSON/SDF, site actually offers...
- API: paper says REST API, site actually provides...
- License: paper says CC-BY 4.0, site actually shows...
- Identifiers: paper says InChIKey/UniProt, API actually returns...

Flag any discrepancies as MISMATCH.

### 6. Assess Ingestion Path
Based on findings, recommend the best ingestion strategy:
- **Bulk download**: If a dump file (JSON, CSV, SQL) is available and complete — simplest path
- **API crawl**: If the API is well-paginated and returns rich detail per entity but no bulk download exists
- **Hybrid**: If bulk download gets the base data but API is needed for detail/updates
- Record the recommended primary key field for BioThings (e.g., InChIKey for MyChem)

**If recommending API crawl, document the following for the plugin generator:**
- **Base URL**: exact API root (e.g., `https://pgx-db.org/api/v1`)
- **Key endpoints**: which endpoints to crawl and in what order
- **Pagination**: mechanism (offset/limit, cursor, page), max page size observed
- **Total records per endpoint**: so the dumper knows when to stop
- **Rate limits**: observed or stated (requests/sec, daily caps)
- **Auth**: none, API key (env var), or token
- **Response shape**: top-level key containing records (e.g., `{"results": [...]}` vs bare array)
- **Estimated crawl time**: (total records ÷ page size) × avg response time
- **Sample curl command**: a working `curl` one-liner that returns data, for the plugin developer to test

This section feeds directly into the `biothings-plugin-generator` skill's Section 1c (API vs Bulk Download Strategy) and the custom `dumper.py` template.

### 7. Save Output
Save to `agent_outputs/<DATASOURCE_NAME>_datasource/<DATASOURCE_NAME>_inspection.json`.
The `_datasource/` folder should already exist from the relevancy evaluation step — create it if not.

**Also update `agent_outputs/pipeline_state.json`**: read the file, update this datasource's entry with `stage: "inspected"`, `inspection_status`, `data_url`, `target_api`, `inspection_date`. Write it back.

**Markdown is optional**: Only generate a `.md` report if the user explicitly asks for one. The JSON is the canonical output.

## Required Output Format (JSON)

Write a single JSON file. The schema below is **stable** — the plugin-generator skill relies on these field names.

```json
{
    "name": "<datasource_name>",
    "status": "VERIFIED | PARTIALLY_VERIFIED | BLOCKED",
    "inspection_date": "2026-05-13",
    "download_files": [
        {
            "url": "https://...",
            "filename": "data.xlsx",
            "format": "XLSX",
            "access": "public",
            "size_mb": 7.4
        }
    ],
    "schema": {
        "fields": [
            {
                "name": "field_name",
                "type": "string",
                "sample": "example_value",
                "classification": "NOVEL | REDUNDANT | IDENTIFIER"
            }
        ],
        "primary_key": {
            "field": "ID",
            "type": "InChIKey | Entrez Gene | HGVS | MONDO | custom",
            "sample": "acc0001"
        },
        "identifiers": [
            {"type": "UniProt", "field": "Protein_uniport", "sample": "P12956"},
            {"type": "gene_symbol", "field": "Gene", "sample": "XRCC6"}
        ]
    },
    "license": {
        "stated_paper": "CC BY 4.0",
        "observed_site": "CC BY 4.0",
        "match": true,
        "restrictions": []
    },
    "plugin_inputs": {
        "data_url": ["https://..."],
        "primary_key_field": "ID",
        "target_api": "pending.api",
        "ingestion_path": "bulk_download | api_crawl | hybrid",
        "novel_fields": ["field1", "field2"],
        "redundant_fields": ["field3"]
    },
    "api_crawl_details": {
        "base_url": "https://...",
        "endpoints": ["endpoint1"],
        "pagination": "offset/limit",
        "total_records": 50000,
        "rate_limits": "unknown",
        "auth": "none",
        "response_shape": "{results: [...]}",
        "sample_curl": "curl ..."
    },
    "paper_vs_reality": [
        {"claim": "50K records", "observed": "48663", "match": true}
    ],
    "risks": ["risk 1"]
}
```

**Fields that MUST be present**: `name`, `status`, `inspection_date`, `download_files`, `plugin_inputs`.
`api_crawl_details`: include only when `ingestion_path` is `api_crawl` or `hybrid`.
`paper_vs_reality`: include only when a prior relevancy evaluation exists.
All other fields: include when known, omit when unknown.

## Decision Rules
- **VERIFIED**: Download files publicly accessible, schema confirmed, novel fields identified, license permits ingestion
- **PARTIALLY_VERIFIED**: Files accessible but schema incomplete, or some fields unverifiable, or minor license uncertainty
- **BLOCKED**: Login/registration required for downloads, license prohibits redistribution, or no download files found

## Interaction with Other Skills
- This skill is designed to run AFTER `datasource-relevancy-analysis`
- If invoked standalone (no prior evaluation), skip the "Paper vs Reality" comparison section
- The output of this skill feeds directly into `biothings-plugin-generator`:
  - If **Bulk download**: plugin generator uses `dumper.data_url` with the verified download URLs
  - If **API crawl**: plugin generator uses the API Crawl Details section to build a custom `dumper.py` (see plugin generator Section 1c)
  - If **Hybrid**: plugin generator combines both approaches
