---
name: datasource-relevancy-analysis
description: >-
  Evaluate a biomedical datasource for BioThings ingestion fit. Use when a user
  provides a datasource name/URL and asks whether it is (1) relevant to the
  BioThings sphere (MyChem, MyGene, MyDisease, MyVariant, pending.api, etc.),
  (2) novel vs already-included BioThings data, and (3) openly downloadable
  without login, paywall, or restrictive license. Produces a structured
  RECOMMEND_INGEST / NEEDS_REVIEW / DO_NOT_INGEST verdict with scored evidence.
---

# Datasource Relevancy Analysis

## Instructions

### 0. Resolve Input URL (when user provides an OUP/NAR article URL)
If the user provides an OUP article URL (e.g., `https://academic.oup.com/nar/article/...`), do NOT attempt to fetch it directly — OUP pages are JS-rendered and will fail.

Instead, follow the resolution procedure in [references/nar-url-resolution.md](references/nar-url-resolution.md) to:
1. Extract the volume, issue, and start page from the URL
2. Look up the PMID via PubMed E-utilities
3. Get the PMCID from the PubMed record
4. Fetch the full-text article from PMC (reliably fetchable)

Extract all evaluation-relevant information from the resolved paper before proceeding to Step 1.

1. Parse input and extract:
   - datasource name
   - homepage / documentation URL
   - download or API URL(s)
   - stated license / terms of use

   **Canonical source preference (MUST follow):** Always check the datasource's own homepage and download page (e.g., `datasource.org/download`) for bulk files BEFORE using URLs from papers, Zenodo, Figshare, Dryad, GitHub releases, or other third-party mirrors. Third-party archives often host stale snapshots (e.g., a Zenodo deposit from 2024 when the datasource has a 2026 release on its own site) and may offer only a subset of files (e.g., a "lite" CSV vs the full download). Record the canonical download URL in `urls.download[]`; only fall back to a mirror if the datasource's own site has no direct bulk download or is access-gated.

2. Assess **BioThings sphere relevance** (score 0–5):
   - 5: Directly aligned — covers core BioThings entities/relations (drug, chemical, gene, variant, disease, pathway, target, adverse event, clinical evidence).
   - 3: Biomedical-adjacent but weakly structured for BioThings entity types.
   - 1: Mostly out of scope.

3. Assess **novelty to BioThings APIs** (score 0–5):
   - Compare against known BioThings data sources and endpoints.
   - 5: Clearly new entities, relations, or annotations not already represented.
   - 3: Partial overlap with meaningful new fields or better provenance/freshness.
   - 1: Largely redundant with existing sources.
   - See [references/evaluation-checklist.md](references/evaluation-checklist.md) for the known-source comparison list.
   - **Ground truth registries** (MUST consult for novelty scoring):
     - [references/existing-biothings-plugins.json](references/existing-biothings-plugins.json) — all sources in core BioThings APIs (MyGene, MyChem, MyVariant, MyDisease), with aliases, identifiers, domains, and record counts
     - [references/pending-api-datasources.json](references/pending-api-datasources.json) — all Translator/pending.api datasources, with overlap annotations
   - Match the candidate datasource name and aliases against registry entries. Compare identifiers and domain tags. If a match is found, the candidate has overlap and novelty must account for it.

   **Meta-aggregator rule**: If the datasource bundles data from multiple upstream sources (e.g., Harmonizome aggregates 170+ datasets from 80+ resources), do NOT score novelty monolithically. Instead:
   1. List the constituent datasets/sources the resource aggregates.
   2. Classify each as **NOVEL** (not in any BioThings API), **REDUNDANT** (already ingested from the primary source), or **UNCERTAIN**.
   3. Score novelty based on the proportion and value of NOVEL datasets, not the overlap of REDUNDANT ones.
   4. If the resource has ≥5 genuinely novel datasets with meaningful BioThings-relevant data, novelty should be ≥3 regardless of how many redundant datasets also exist.
   5. In the Evidence/Overlap section, explicitly list both the novel and redundant sub-datasets so downstream steps know which to ingest and which to skip.

4. Assess **open download / access** (PASS / FAIL + score 0–5):
   - PASS requires **all** of:
     - downloadable via public URL or open API
     - no account / login / API key required for basic acquisition
     - no paywall or click-through-only access gate
     - license permits reuse for integration and redistribution
   - FAIL if any blocker exists.
   - Score reflects degree of openness (5 = fully open CC0/public-domain; 3 = open with attribution; 1 = restricted).

5. Inspect **API availability** (informational — does NOT affect the verdict):
   - Check the datasource homepage and documentation for a public REST/GraphQL API
   - Record: endpoint base URL, auth requirements, rate limits (if documented), pagination style, whether it exposes full records or only query access
   - Note: the BioThings plugin generator currently uses manifest-based bulk download only; API availability is captured here to inform novelty/freshness scoring and to feed the backlog item for future API-first dumpers. It is NOT used to choose the ingestion strategy.
   - If no API is documented, record "No public API found" with the URLs checked.

6. Produce a final **verdict**:
   - **RECOMMEND_INGEST**: relevance ≥ 4, novelty ≥ 3, openness PASS
   - **NEEDS_REVIEW**: mixed scores or uncertainty in any dimension
   - **DO_NOT_INGEST**: relevance < 3, OR openness FAIL, OR clearly redundant

7. If evidence is missing, explicitly list unknowns — do not guess.

8. **Save output**:
   Save to `agent_outputs/<DATASOURCE_NAME>_datasource/<DATASOURCE_NAME>_relevancy.json`.
   Use lowercase, underscore-separated datasource name (e.g., `ecbd_datasource/ecbd_relevancy.json`). Create the folder if it does not exist. All subsequent outputs for this datasource will also live under this folder.

   **Also update `agent_outputs/pipeline_state.json`**: read the file, add/update the entry for this datasource with `stage`, `verdict`, `scores`, `eval_date`. Write it back.

   **Markdown is optional**: Only generate a `.md` report if the user explicitly asks for one (e.g., "write a report" or "generate markdown"). The JSON is the canonical output.

## Required Output Format (JSON)

Write a single JSON file. The schema below is **stable** — downstream skills (site-inspection, plugin-generator) rely on these field names.

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
    "next_actions": ["Run site inspection", "Proceed to plugin generation"],
    "evaluated_at": "2026-05-13"
}
```

**Fields that MUST be present**: `name`, `verdict`, `scores`, `urls.homepage`, `license.name`, `evaluated_at`.
All other fields: include when known, omit when unknown (do not use null or "unknown" strings).

## Decision Rules
- Openness FAIL is a hard blocker unless user explicitly requests restricted-source tracking.
- If novelty is uncertain, default to NEEDS_REVIEW, not RECOMMEND_INGEST.
- Always cite concrete evidence (URL, license text, docs page) — not assumptions.
- **Meta-aggregators**: When a datasource aggregates many upstream sources, never issue DO_NOT_INGEST based solely on aggregate-level overlap. If the resource contains genuinely novel sub-datasets alongside redundant ones, the verdict must be NEEDS_REVIEW with a selective ingestion recommendation listing which sub-datasets to ingest and which to skip. Only issue DO_NOT_INGEST if *every* constituent dataset is already covered by BioThings.

## Examples
- `/datasource-relevancy-analysis SIGNOR pathway database`
- `/datasource-relevancy-analysis DrugMap drug-target interactions`
- "Evaluate the STRING protein-protein interaction database for BioThings ingestion"
