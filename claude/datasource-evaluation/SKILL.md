---
name: datasource-evaluation
description: >-
  Evaluate a biomedical datasource for BioThings ingestion fit and inspect its
  download files in a single pass. Scores relevance, novelty, and openness;
  verifies download access, samples the data schema, and confirms fields are
  relevant and novel for BioThings. Produces two structured JSON outputs — a
  relevancy verdict (RECOMMEND_INGEST / NEEDS_REVIEW / DO_NOT_INGEST) and an
  inspection report (VERIFIED / PARTIALLY_VERIFIED / BLOCKED) — that feed
  directly into the plugin generator. Use when a user provides a datasource
  name/URL and wants the complete evaluation before plugin generation.
---

# Datasource Evaluation

## Purpose
Answer five questions in a single pass:
1. **Is it relevant?** — Does this datasource cover BioThings entity types and relations?
2. **Is it novel?** — Does it add information not already in BioThings APIs?
3. **Is it open?** — Can we download the data without login, paywall, or restrictive license?
4. **Can we get the data?** — Are the download files publicly accessible and fetchable?
5. **What's in the files?** — What are the field names, types, and sample values, and are they worth ingesting?

This skill replaces the separate `datasource-relevancy-analysis` and `datasource-site-inspection` skills by combining their logic into a single research-then-assess workflow. It produces both `_relevancy.json` and `_inspection.json` so downstream skills (plugin-generator) work without changes.

## Tools to Use
1. **Web fetching** — try the datasource homepage, download page, and direct file URLs.
2. **Web search** — fallback if pages are JS-rendered or return no content.
3. **Local paper PDF** — read it for the Data Availability / Methods section if the site is opaque. This is often the most reliable source of file format and schema.
4. **E-utilities** — resolve OUP/NAR article URLs to PMC PDFs (see [references/nar-url-resolution.md](references/nar-url-resolution.md)).

Do NOT parse JS bundles, reverse-engineer network layers, or dig into web app architecture.

## Instructions

### Phase 1: Research & Data Gathering

Gather all evidence before scoring. This avoids the duplicate work of discovering URLs in relevancy and re-verifying them in inspection.

#### 1a. Resolve Input

**If the user provides an OUP article URL** (e.g., `https://academic.oup.com/nar/article/...`), do NOT fetch it directly — OUP pages are JS-rendered and will fail.

Follow the resolution procedure in [references/nar-url-resolution.md](references/nar-url-resolution.md), which tries in this order:
1. **Local PDF** — check `agent_outputs/<datasource>_datasource/*.pdf`; if present, read directly and skip all HTTP calls
2. **E-utilities → PMC PDF** — resolve OUP URL to PMCID via PubMed, then fetch the PDF
3. **PMC HTML** — fallback if PDF fetch fails
4. **Web search** — fallback if article not yet in PMC

Extract all evaluation-relevant information from the resolved paper before proceeding.

Parse input and extract:
- Datasource name
- Homepage / documentation URL
- Download or API URL(s)
- Stated license / terms of use

#### 1b. Visit the Canonical Site & Find Download Files

**Canonical source preference (MUST follow):** Always visit the datasource's own homepage and download page first (e.g., `datasource.org/download`). Do NOT blindly inherit URLs from papers, Zenodo, Figshare, Dryad, GitHub releases, or other third-party mirrors. Third-party archives often host stale snapshots or subset files — they are fallbacks only, used when the datasource's own site has no direct bulk download or is access-gated.

From the homepage, download page, paper, or documentation:
- List each available download file with its URL, format, and description
- Confirm each URL is directly accessible (no login, no redirect to a registration wall)
- **If ALL files require login/registration → note BLOCKED for inspection status.** Do not attempt to work around auth gates.
- If the user provides local file paths (already downloaded), skip access checks.

**JS-Rendered Download Page Protocol (MUST follow in order):**

If the canonical download page returns no useful content because the page is JS-rendered, work through these steps in order and stop at the first that succeeds. Do NOT jump ahead to third-party archives.

1. **Probe common download URL patterns directly** — try fetching these paths on the datasource's own domain even without a working download page:
   - `/download`, `/downloads`, `/data`, `/files`, `/bulk`, `/static/data`, `/release`, `/releases`, `/export`
   - Append common file extensions: `.gz`, `.tar.gz`, `.zip`, `.tsv`, `.csv`, `.json`, `.xml`, `.sdf`
   - Example: if site is `mydb.org`, try `mydb.org/downloads/`, `mydb.org/data/full.tsv.gz`, etc.

2. **Search for canonical download URLs** — run a targeted web search specifically for direct file URLs on the datasource's own domain:
   - Query pattern: `"<datasource name>" download filetype:gz OR filetype:tsv OR filetype:csv OR filetype:json`
   - Query pattern: `site:<datasource-domain> download bulk data`
   - The goal is to surface direct file links (`.gz`, `.tsv`, `.csv`) that are hosted on the datasource's own servers.

3. **Scan the paper's Data Availability / Methods section** — published papers often list exact download URLs or FTP paths that bypass the JS-rendered web interface entirely. If a local PDF is available, read it now.

4. **Scan the page source for embedded file links** — even JS-rendered pages often include static hrefs in the initial HTML payload. Fetch the raw HTML and grep for strings ending in `.gz`, `.tsv`, `.csv`, `.json`, `.zip`, `.tar`.

5. **Check the datasource's GitHub organization** — if the datasource has a GitHub org or repo, look at Releases for links that point back to files on the canonical domain (not GitHub itself). Do NOT treat a GitHub-hosted file as canonical unless the datasource's own domain is not hosting bulk downloads.

6. **Only after steps 1–5 all fail:** Fall back to Zenodo, Figshare, Dryad, or other third-party archives. When doing so:
   - Record the archive DOI and upload date
   - Flag `"third_party_archive": true` and `"staleness_risk": "<upload_date>"` on the download file entry
   - Note in `risks` that the canonical site was JS-rendered and canonical download URLs could not be confirmed

**Never accept a third-party archive fallback without first documenting which of steps 1–5 were attempted and why they failed.**

#### 1c. Sample the Data Schema

For each accessible download file:
- If the file is small enough, fetch it directly
- If it's a large flat file (TSV/CSV/JSON), fetch just the header row or first few lines using a range/byte request if possible, or search for published schema documentation
- If the user has a local copy, read the first 20–50 lines
- Record: column names / JSON keys, data types, 2–3 sample values per key field

#### 1d. Check API Availability

Check the datasource homepage and documentation for a public REST/GraphQL API:
- Record: endpoint base URL, auth requirements, rate limits (if documented), pagination style, whether it exposes full records or only query access
- If no API is documented, record "No public API found" with the URLs checked

#### 1e. Verify License

Check both the paper and the datasource site for license information:
- Record the license name, URL, and any restrictions
- Note any NC/ND restrictions that affect redistribution
- Flag discrepancies between paper and site

### Phase 2: Relevancy Assessment

Using the evidence gathered in Phase 1, score the datasource.

#### 2a. BioThings Sphere Relevance (score 0–5)

- 5: Directly aligned — covers core BioThings entities/relations (drug, chemical, gene, variant, disease, pathway, target, adverse event, clinical evidence).
- 3: Biomedical-adjacent but weakly structured for BioThings entity types.
- 1: Mostly out of scope.

#### 2b. Novelty to BioThings APIs (score 0–5)

Compare against known BioThings data sources and endpoints. See [references/evaluation-checklist.md](references/evaluation-checklist.md) for the known-source comparison list. Also compare against [references/existing-biothings-plugins.json](references/existing-biothings-plugins.json) and [references/pending-api-datasources.json](references/pending-api-datasources.json).

- 5: Clearly new entities, relations, or annotations not already represented.
- 3: Partial overlap with meaningful new fields or better provenance/freshness.
- 1: Largely redundant with existing sources.

**Use actual schema data when available.** If Phase 1 successfully sampled the schema, score novelty against the real fields — not just paper claims. This is more accurate than the old two-pass approach.

**Meta-aggregator rule**: If the datasource bundles data from multiple upstream sources (e.g., Harmonizome aggregates 170+ datasets from 80+ resources), do NOT score novelty monolithically. Instead:
1. List the constituent datasets/sources the resource aggregates.
2. Classify each as **NOVEL** (not in any BioThings API), **REDUNDANT** (already ingested from the primary source), or **UNCERTAIN**.
3. Score novelty based on the proportion and value of NOVEL datasets, not the overlap of REDUNDANT ones.
4. If the resource has ≥5 genuinely novel datasets with meaningful BioThings-relevant data, novelty should be ≥3 regardless of how many redundant datasets also exist.
5. In the Evidence/Overlap section, explicitly list both the novel and redundant sub-datasets so downstream steps know which to ingest and which to skip.

#### 2c. Open Download / Access (PASS / FAIL + score 0–5)

PASS requires **all** of:
- Downloadable via public URL or open API
- No account / login / API key required for basic acquisition
- No paywall or click-through-only access gate
- License permits reuse for integration and redistribution

FAIL if any blocker exists.

Score reflects degree of openness (5 = fully open CC0/public-domain; 3 = open with attribution; 1 = restricted).

#### 2d. Produce Verdict

- **RECOMMEND_INGEST**: relevance ≥ 4, novelty ≥ 3, openness PASS
- **NEEDS_REVIEW**: mixed scores or uncertainty in any dimension
- **DO_NOT_INGEST**: relevance < 3, OR openness FAIL, OR clearly redundant

If evidence is missing, explicitly list unknowns — do not guess.

### Gate: Relevancy Check

| Verdict            | Action                                                     |
|--------------------|------------------------------------------------------------|
| `RECOMMEND_INGEST` | Proceed to Phase 3 immediately                             |
| `NEEDS_REVIEW`     | Proceed to Phase 3 (log warning; user can override)        |
| `DO_NOT_INGEST`    | **STOP.** Save the relevancy JSON and report. Do not continue to inspection. |

If stopping at this gate, still save `_relevancy.json` and update `pipeline_state.json` before stopping.

### Phase 3: Deep Inspection

This phase uses the download files and schema data gathered in Phase 1 to produce the inspection report. Much of the raw data collection is already done — this phase focuses on classification and ingestion strategy.

#### 3a. Classify Fields for BioThings

For each field found in Phase 1c:
- **Identify BioThings-mappable identifiers** (InChIKey, Entrez Gene ID, HGVS, MONDO ID, RS number, etc.) — these determine which BioThings API the plugin targets
- **Flag NOVEL fields** — fields that carry information not already present in existing BioThings sources
- **Flag REDUNDANT fields** — fields that duplicate what's already in BioThings (e.g., re-annotating gnomAD AF when BioThings already has it)
- Confirm the primary key strategy: which field becomes `_id`, and does it map to MyVariant / MyGene / MyChem / MyDisease?

#### 3b. Paper vs Reality Comparison

If a paper was read in Phase 1, compare claims against what was actually found:
- Entity counts: paper says X, site shows Y
- Formats: paper says CSV/JSON/SDF, site actually offers...
- API: paper says REST API, site actually provides...
- License: paper says CC-BY 4.0, site actually shows...
- Identifiers: paper says InChIKey/UniProt, data actually contains...

Flag any discrepancies as MISMATCH.

#### 3c. Assess Ingestion Path

Based on findings, recommend the best ingestion strategy:
- **Bulk download**: If a dump file (JSON, CSV, SQL) is available and complete — simplest path
- **API crawl**: If the API is well-paginated and returns rich detail per entity but no bulk download exists
- **Hybrid**: If bulk download gets the base data but API is needed for detail/updates

Record the recommended primary key field for BioThings (e.g., InChIKey for MyChem).

**If recommending API crawl, document the following for the plugin generator:**
- **Base URL**: exact API root (e.g., `https://pgx-db.org/api/v1`)
- **Key endpoints**: which endpoints to crawl and in what order
- **Pagination**: mechanism (offset/limit, cursor, page), max page size observed
- **Total records per endpoint**: so the dumper knows when to stop
- **Rate limits**: observed or stated (requests/sec, daily caps)
- **Auth**: none, API key (env var), or token
- **Response shape**: top-level key containing records (e.g., `{"results": [...]}` vs bare array)
- **Estimated crawl time**: (total records ÷ page size) × avg response time
- **Sample curl command**: a working `curl` one-liner that returns data

This feeds directly into the `biothings-plugin-generator` skill's Section 1c (API vs Bulk Download Strategy).

#### 3d. Determine Inspection Status

- **VERIFIED**: Download files publicly accessible, schema confirmed, novel fields identified, license permits ingestion
- **PARTIALLY_VERIFIED**: Files accessible but schema incomplete, or some fields unverifiable, or minor license uncertainty
- **BLOCKED**: Login/registration required for downloads, license prohibits redistribution, or no download files found

### Phase 4: Save Outputs

Save both JSON files to `agent_outputs/<DATASOURCE_NAME>_datasource/`. Use lowercase, underscore-separated datasource name (e.g., `ecbd_datasource/`). Create the folder if it does not exist.

#### 4a. Save Relevancy JSON

Save to `agent_outputs/<DATASOURCE_NAME>_datasource/<DATASOURCE_NAME>_relevancy.json`.

```json
{
    "name": "<datasource_name>",
    "verdict": "RECOMMEND_INGEST | NEEDS_REVIEW | DO_NOT_INGEST",
    "scores": {
        "relevance": {"score": 0, "justification": "..."},
        "novelty":   {"score": 0, "justification": "..."},
        "openness":  {"pass": true, "score": 0, "justification": "..."}
    },
    "evidence": {
        "scope": "what entities/relations it covers",
        "overlap": "what it shares with existing BioThings sources",
        "entity_types": ["gene", "disease"],
        "identifiers_found": ["NCBI Gene", "MONDO"],
        "record_count": 50000
    },
    "license": {
        "name": "CC BY 4.0",
        "url": "https://creativecommons.org/licenses/by/4.0/",
        "restrictions": []
    },
    "urls": {
        "homepage": "https://...",
        "download": ["https://..."],
        "api": "https://...",
        "paper_doi": "10.1093/nar/...",
        "pmid": "12345678",
        "pmc": "PMC12345678"
    },
    "api_info": {
        "exists": true,
        "base_url": "https://...",
        "auth_required": false,
        "rate_limits": "unknown",
        "pagination": "offset/limit",
        "record_coverage": "full"
    },
    "target_api": "pending.api",
    "risks": ["risk 1", "risk 2"],
    "next_actions": ["Proceed to plugin generation"],
    "evaluated_at": "2026-05-13"
}
```

**Fields that MUST be present**: `name`, `verdict`, `scores`, `urls.homepage`, `license.name`, `evaluated_at`.
All other fields: include when known, omit when unknown (do not use null or "unknown" strings).

#### 4b. Save Inspection JSON

Save to `agent_outputs/<DATASOURCE_NAME>_datasource/<DATASOURCE_NAME>_inspection.json`.

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
`paper_vs_reality`: include only when a paper was read during evaluation.
All other fields: include when known, omit when unknown.

#### 4c. Update Pipeline State

Read `agent_outputs/pipeline_state.json` and update this datasource's entry with fields from both stages:
- From relevancy: `stage`, `verdict`, `scores`, `eval_date`
- From inspection: `stage: "inspected"`, `inspection_status`, `data_url`, `target_api`, `inspection_date`

If the gate stopped the pipeline at DO_NOT_INGEST, set `stage: "evaluated"` (not "inspected").

Write it back.

**Markdown is optional**: Only generate `.md` reports if the user explicitly asks for one. The JSONs are the canonical outputs.

## Decision Rules

### Relevancy Verdicts
- Openness FAIL is a hard blocker unless user explicitly requests restricted-source tracking.
- If novelty is uncertain, default to NEEDS_REVIEW, not RECOMMEND_INGEST.
- Always cite concrete evidence (URL, license text, docs page) — not assumptions.
- **Meta-aggregators**: When a datasource aggregates many upstream sources, never issue DO_NOT_INGEST based solely on aggregate-level overlap. If the resource contains genuinely novel sub-datasets alongside redundant ones, the verdict must be NEEDS_REVIEW with a selective ingestion recommendation listing which sub-datasets to ingest and which to skip. Only issue DO_NOT_INGEST if *every* constituent dataset is already covered by BioThings.

### Inspection Statuses
- **VERIFIED**: Download files publicly accessible, schema confirmed, novel fields identified, license permits ingestion
- **PARTIALLY_VERIFIED**: Files accessible but schema incomplete, or some fields unverifiable, or minor license uncertainty
- **BLOCKED**: Login/registration required for downloads, license prohibits redistribution, or no download files found

## Interaction with Other Skills
- This skill replaces the separate `datasource-relevancy-analysis` and `datasource-site-inspection` skills
- If invoked standalone with no paper (just a datasource URL/name), skip the Paper vs Reality comparison
- The output feeds directly into `biothings-plugin-generator`:
  - If **Bulk download**: plugin generator uses `plugin_inputs.data_url` with the verified download URLs
  - If **API crawl**: plugin generator uses the `api_crawl_details` section to build a custom `dumper.py` (see plugin generator Section 1c)
  - If **Hybrid**: plugin generator combines both approaches

## Examples
- `Evaluate SIGNOR pathway database for BioThings ingestion`
- `Evaluate DrugMap drug-target interactions for BioThings ingestion`
- `Evaluate the STRING protein-protein interaction database for BioThings ingestion`
- `Evaluate https://academic.oup.com/nar/article/53/D1/D1383/7832351 for BioThings`
