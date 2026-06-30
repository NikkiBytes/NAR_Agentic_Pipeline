---
name: pipeline-benchmarker
description: >-
  Evaluate the BioThings plugin agent pipeline against curated ground-truth
  test cases. Run when you want to measure skill accuracy, detect regressions
  after skill edits, or generate performance metrics for reporting. Scores
  relevancy/site-inspection stages against known verdicts and evaluates
  plugin output by inspecting actual data (document counts, field coverage,
  _id format, manifest accuracy) with detailed per-session reports.
  Saves structured JSON results to benchmark_outputs/. Do not use for
  general testing or non-BioThings benchmarks.
---

# Pipeline Benchmarker

## When to Use
- After editing any pipeline skill to check for regressions
- Periodically (e.g. monthly) to track pipeline performance over time
- Before presentations — generates reproducible metrics from known-answer cases
- To compare model versions: run with model A, then model B, diff the results

## How It Works
1. Load `references/benchmark-cases.json` — 9 curated cases with expert ground truth
2. For each selected case, invoke the relevant pipeline skill(s) fresh (do NOT use cached outputs from `agent_outputs/`)
3. Parse the structured fields from each skill's output
4. For relevancy/site_inspection: score against ground truth using rubrics below
5. For plugin: run the full CLI pipeline and evaluate actual output data (document counts, field coverage, _id formats, manifest accuracy) — no point scoring
6. Save one JSON run record to `benchmark_outputs/benchmark_run_<YYYYMMDD_HHMMSS>.json`
7. Print a summary — tabular for relevancy/site_inspection, detailed per-session reports for plugin

## Test Case Selection

Default (no args): run all cases tagged `"core"` for the `relevancy` stage only (fastest).

Override with:
- `pipeline-benchmarker all` — all cases, all stages they support
- `pipeline-benchmarker relevancy` — relevancy stage only, all core cases
- `pipeline-benchmarker plugins` — only cases with a `plugin` stage (ecbd, signor, rnacentral)
- `pipeline-benchmarker ecbd signor` — specific case IDs only
- `pipeline-benchmarker --stage site_inspection` — only site_inspection stage for eligible cases
- `pipeline-benchmarker robustness` — only cases tagged `blocked` or `no_license` (tests hard-stop detection)

## Stage Execution

### Stage 1 — Relevancy Evaluation
For each case with `"relevancy"` in `stages`:
1. Invoke `datasource-evaluation` using the case's `test_prompt` (relevancy phase only — stop after Phase 2 verdict)
2. Parse from the skill's output:
   - `verdict` — RECOMMEND_INGEST, NEEDS_REVIEW, or DO_NOT_INGEST
   - `relevance_score` — integer 0-5
   - `novelty_score` — integer 0-5
   - `openness_verdict` — PASS or FAIL
   - `openness_score` — integer 0-5
   - `license` — license name
3. Score using the Relevancy Rubric
4. Save the output to `benchmark_outputs/<run_id>/<case_id>_relevancy.md`

### Stage 2 — Site Inspection
For each case with `"site_inspection"` in `stages`:
1. First check: if a `relevancy` stage was run in this session for this case, use its output. Otherwise load the source artifact from `source_artifacts.relevancy`.
2. Invoke `datasource-evaluation` using the case's URL (if relevancy was already run in this session, the evaluation skill's inspection phase output is used directly)
3. Parse: `status`, `download_accessible`, `primary_key_field`, `target_api`
4. Score using the Site Inspection Rubric
5. Save the output to `benchmark_outputs/<run_id>/<case_id>_site_inspection.md`

### Stage 3 — Plugin Evaluation
For each case with `"plugin"` in `stages`:
1. Invoke `biothings-plugin-generator` using the case name and prior site inspection output
2. **File inventory**: Check which files were generated (`manifest.json`, `parser.py`, `version.py`, `design_rationale.md`). Record present/missing — do not score.
3. **CLI pipeline**: Run `biothings-cli` validation suite in order: `validate` → `dump` → `upload` → `list` → `inspect --limit 1000`
4. **Document count**: Record the exact document count from `upload`. Compare against ground truth `min_documents`. Calculate `count_ratio = actual / expected`.
5. **_id format analysis**: Sample 20 `_id` values from inspected output. Check each against the expected format (e.g. InChIKey regex, SIGNOR ID pattern). Record the match rate and any malformed IDs.
6. **Field coverage audit**: From the `inspect` output, extract all top-level and nested fields under the datasource namespace. Compare against ground truth `novel_fields` from the `site_inspection` stage. For each expected field, record: present/absent, non-null percentage (from the `--limit 1000` sample).
7. **Manifest review**: Parse the generated `manifest.json` and verify:
   - `data_url` resolves to actual data (not HTML)
   - `on_duplicates` matches ground truth expectation
   - `__metadata__.license` matches ground truth license
   - `version.py` is wired via `release: "version:get_release"`
8. **Parser output snapshot**: Save a dedicated `<case_id>_parser_output.json` to `benchmark_outputs/<run_id>/` containing:
   - `total_documents`: exact count from upload
   - `field_tree`: the complete nested field structure from `inspect`, showing every key path and its type (e.g. `ecbd.bioactivity_results[].activity_type: str`)
   - `sample_documents`: 5 full documents from the parser (first 2, middle 1, last 2) — **no truncation, no `"..."`** — every field and value exactly as yielded by `load_data()`. Each document must show the complete `_id` and the full nested structure under the datasource namespace.
   - `id_samples`: the 20 sampled `_id` values used for format analysis
   - `field_stats`: for each field path, the count and percentage of documents where it is non-null (from the `--limit 1000` inspect sample)
   This file is the primary artifact for understanding what the parser actually produces.
9. **Sample document review**: From the 5 snapshot documents, flag any fields with missing expected values, unexpected types (e.g. string where int expected), or empty nested objects. Record these as discrepancies.
10. **Compile session report** with all findings above — see Output Format below

### Stage 3b — API Spot Check

Run immediately after step 10 above, before writing the final session report. This step compares one real parser document against the same record fetched live from the source API.

**When to run:** Only if `ground_truth.plugin.api_spot_check` is present in the case AND `type != "not_available"`. If `type == "not_available"`, record `api_spot_check: {status: "SKIPPED", reason: <the reason string from the case>}` in the report and stop.

**Step-by-step:**

1. **Read** `api_spot_check` from the case. Note `type`, `example_id`, `example_plugin_id`, `fetch`, `field_map`, `api_only_fields`, and `plugin_only_fields`.

2. **Auth check — hard skip if any auth required:**
   - If `fetch.auth.type != "none"`: immediately record `status: "SKIPPED", reason: "API requires authentication — pipeline policy prohibits any login or credentials for automated spot checks"` and stop. Do NOT attempt login, check env vars, or use tokens.
   - Only proceed to the fetch step when `fetch.auth.type == "none"`.

3. **Fetch** the source API document:
   - Substitute `{{example_id}}` in `fetch.url` and `fetch.payload_template` (if present) with the actual `example_id` value.
   - Execute the HTTP request (`fetch.method`), passing the Bearer token in `Authorization: Bearer <token>` if required.
   - Navigate `fetch.result_path` to reach the record object. Use dot notation for nested keys and `[N]` for array indices (e.g. `"data[0]"` → response body's `data` array first element). If `result_path` is `null`, the response body itself is the record.
   - If the request fails or returns no data, record `status: "SKIPPED", reason: "API fetch failed: <error>"` and stop.

4. **Find the parser document** for `example_plugin_id`:
   - First look in the `inspect --limit 1000` sample already collected in Stage 3. Search for `_id == example_plugin_id`.
   - If not in the sample, re-run the parser on just that record: locate the source row matching `example_id` in the downloaded data file (grep/filter by the primary key field), write it to a temp file, run `load_data()` on it, and take the yielded document.
   - If the record cannot be found, record `status: "SKIPPED", reason: "example_plugin_id not found in parser output"` and stop.

5. **Compare** field by field:

   *Mapped fields* — for each entry in `field_map`:
   - Resolve the `api` path in the API document (dot notation, e.g. `"properties.alogp"` → `doc["properties"]["alogp"]`).
   - Resolve the `plugin` path in the parser document (e.g. `"rnacentral.rna_type"` → `doc["rnacentral"]["rna_type"]`; `"_id"` → `doc["_id"]`).
   - Record one of: `MATCH`, `MISMATCH` (both present, values differ), `ABSENT_IN_PLUGIN` (in API but missing from plugin doc), `ABSENT_IN_API` (in plugin but API returned null/missing).

   *API-only fields* — for each field in `api_only_fields`:
   - Record the actual value from the API document. These are intentionally absent from the plugin and must NOT be flagged as failures — they are documentation of conscious scope decisions.

   *Uncovered fields* — any top-level API fields (and nested fields under any included relations) that are NOT in `field_map` AND NOT in `api_only_fields`:
   - List them with their API values. These represent potential data the plugin is silently dropping and warrant a note in findings.

   *Plugin-only fields* — for each field in `plugin_only_fields` (fields the plugin produces that the base API endpoint does not expose):
   - Verify the field is present and non-null in the parser document. Record `PRESENT` or `ABSENT`.

6. **Determine status:**
   - `PASS` — all mapped fields are `MATCH` or `ABSENT_IN_API`; no uncovered fields
   - `MISMATCH` — at least one mapped field shows `MISMATCH` or unexpected `ABSENT_IN_PLUGIN`
   - `PARTIAL` — all values match but uncovered fields exist (potential silent data loss)
   - `SKIPPED` — auth unavailable, API unreachable, or `type == "not_available"`

7. **Append to session report** an `api_spot_check` section:

```text
── API Spot Check ────────────────────────────────────────────
Status: PASS | MISMATCH | PARTIAL | SKIPPED
Source API: <fetch.url with example_id substituted>
Example:    <example_id>  →  plugin _id: <example_plugin_id>

Mapped fields:
  MATCH           rnacentral_id      api=URS0000000A8C       plugin=URS0000000A8C
  MATCH           rna_type           api=vault_RNA            plugin=vault_RNA
  ABSENT_IN_PLUGIN  length           api=88                  plugin=—

API-only fields (intentionally not captured):
  md5               7bcc7b742c665d73b17da2b8e823e7cf
  sequence          GGCUGGCU...
  is_active         true

Uncovered fields (in API, not in field_map or api_only_fields):
  <none> | <field: value, ...>

Plugin-only fields (produced by parser, absent from base API):
  rnacentral.rfam_family          PRESENT
  rnacentral.disease_associations ABSENT  ← flag as finding
```

Add any `MISMATCH`, unexpected `ABSENT_IN_PLUGIN`, or uncovered fields to the session report's `discrepancies` list.

**What api_spot_check does NOT do:**

- Does not affect the overall plugin `PASS`/`PARTIAL`/`FAIL` status — it is informational only.
- Does not validate bulk data — one example is a spot check, not a regression suite.
- Does not fail the benchmark if auth env vars are unset — it gracefully skips.

**Supported fetch types:**

| `type` | Auth | Method | When to use |
|--------|------|--------|-------------|
| `GET_JSON` | `none` only | GET | Public REST API returning JSON — no login or token required |
| `POST_JSON` | `none` only | POST | Public REST API requiring a JSON search payload — no login or token required |
| `not_available` | — | — | No public per-record API exists (no REST API, auth required, bulk-only, self-signed TLS, etc.) — skip with reason |

When adding a new benchmark case with a plugin stage, determine which type applies by checking whether the source database has a per-record REST API endpoint. If it does, add a `GET_JSON` or `POST_JSON` block. If not (bulk-only download, self-signed TLS, no REST API), set `type: "not_available"` with a reason string — this explicitly documents the decision rather than leaving it ambiguous.

## Scoring Rubrics

### Relevancy Rubric (max 8 points)
- Verdict exact match: 3 points
- Verdict adjacent match (off by one level): 1 point
- Verdict wrong direction (skipped a level): 0 points
- Relevance score exact: 2 points (±1: 1 point)
- Novelty score exact: 2 points (±1: 1 point)
- Openness verdict match: 1 point

Note: score points are exclusive (max 2 per dimension, not both 2 and 1).

**Critical accuracy check:** For cases tagged `blocked` or `no_license`, the agent MUST detect the openness blocker. Setting RECOMMEND_INGEST for a blocked case = 0 points total.

### Site Inspection Rubric (max 6 points)
- Status exact match: 3 points (adjacent: 1 point)
- Download accessibility correct: 1 point
- Primary key field correct: 1 point
- Target API correct: 1 point

### Plugin Evaluation Criteria (no point scoring)
Plugin evaluation produces a detailed session report instead of a numeric score. Each criterion is assessed and reported narratively:

**File inventory**
- Record which required files are present/missing: `manifest.json`, `parser.py`, `version.py`, `design_rationale.md`

**CLI pipeline results**
- `validate`: pass/fail + any warnings or errors (full output)
- `dump`: pass/fail + file sizes downloaded, time elapsed
- `upload`: pass/fail + exact document count + comparison to ground truth `min_documents`
- `inspect`: field tree from `--limit 1000`, used for field coverage audit

**Data quality checks**
- `_id format`: sample 20 IDs, report match rate against expected pattern, list any malformed IDs
- `field coverage`: for each ground truth `novel_field`, report present/absent + non-null percentage
- `manifest accuracy`: verify `data_url` resolves to data, `on_duplicates` matches, license matches, `version.py` is wired
- `parser output snapshot`: 5 full documents saved to `<case_id>_parser_output.json` with field tree and stats — the definitive reference for what the parser produces

**Overall assessment**
- `status`: one of `PASS`, `PARTIAL`, or `FAIL`
  - `PASS` — all CLI steps succeed, document count ≥ `min_documents`, _id format match ≥ 90%, all novel fields present
  - `PARTIAL` — CLI steps succeed but with gaps (document count below threshold, missing fields, _id issues)
  - `FAIL` — any CLI step fails, or zero documents uploaded

## Output Format

Save to `benchmark_outputs/benchmark_run_<YYYYMMDD_HHMMSS>.json`:

```json
{
  "run_id": "benchmark_run_20260511_060000",
  "run_date": "2026-05-11",
  "run_timestamp": "2026-05-11T06:00:00Z",
  "cases_run": 9,
  "stages_run": ["relevancy", "plugin"],
  "summary": {
    "relevancy_verdict_accuracy": 0.78,
    "relevancy_score_pct": 0.82,
    "site_inspection_accuracy": 0.85,
    "plugin_status_counts": { "PASS": 2, "PARTIAL": 1, "FAIL": 0 },
    "cases_passed": 7,
    "cases_failed": 2,
    "critical_failures": []
  },
  "results": [
    {
      "case_id": "ecbd",
      "case_name": "ECBD (European Chemical Biology Database)",
      "stage": "relevancy",
      "ground_truth": { "verdict": "RECOMMEND_INGEST", "relevance_score": 5, "novelty_score": 3, "openness_verdict": "PASS" },
      "predicted": { "verdict": "RECOMMEND_INGEST", "relevance_score": 5, "novelty_score": 3, "openness_verdict": "PASS" },
      "verdict_match": true,
      "score": 8,
      "max_score": 8,
      "pct": 1.0,
      "pass": true,
      "notes": ""
    },
    {
      "case_id": "ecbd",
      "case_name": "ECBD (European Chemical Biology Database)",
      "stage": "plugin",
      "status": "PASS",
      "files": {
        "manifest.json": true,
        "parser.py": true,
        "version.py": true,
        "design_rationale.md": true
      },
      "cli_results": {
        "validate": { "pass": true, "output_summary": "No errors or warnings" },
        "dump": { "pass": true, "files_downloaded": 3, "total_size_mb": 12.4, "elapsed_seconds": 18 },
        "upload": { "pass": true, "documents_yielded": 4831, "expected_min": 500, "count_ratio": 9.66 },
        "inspect": { "pass": true, "fields_found": 14, "sample_limit": 1000 }
      },
      "id_format": {
        "expected_pattern": "InChIKey",
        "sample_size": 20,
        "match_rate": 1.0,
        "malformed_ids": []
      },
      "field_coverage": {
        "bioactivity_results": { "present": true, "non_null_pct": 98.2 },
        "bioprofiling": { "present": true, "non_null_pct": 74.1 },
        "screening_qc_metadata": { "present": true, "non_null_pct": 100.0 }
      },
      "manifest_review": {
        "data_url_resolves": true,
        "on_duplicates_match": true,
        "license_match": true,
        "version_wired": true
      },
      "parser_output_file": "benchmark_outputs/benchmark_run_20260511_060000/ecbd_parser_output.json",
      "sample_documents": [
        {
          "_id": "AQTQHPDCURKLKT-PNYVAJAMSA-N",
          "ecbd": {
            "name": "Dasatinib",
            "smiles": "CC1=C(C(=O)N1)C2=CC(=CC=C2)NC(=O)C3=CC=C(C=C3)CN4CCN(CC4)C",
            "bioactivity_results": [
              {
                "assay_id": "ECBD-A-001",
                "activity_type": "IC50",
                "activity_value": 0.012,
                "activity_unit": "uM",
                "target": "ABL1"
              }
            ],
            "bioprofiling": {
              "selectivity_index": 0.87,
              "hit_rate": 0.34,
              "cytotoxicity_flag": false
            },
            "screening_qc_metadata": {
              "plate_id": "ECBD-P-2024-042",
              "z_prime": 0.72,
              "signal_to_noise": 12.4
            },
            "xrefs": {
              "pubchem": "CID3062316",
              "chembl": "CHEMBL941",
              "zinc": "ZINC000003927171"
            }
          }
        },
        {
          "_id": "BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
          "ecbd": {
            "name": "Aspirin",
            "smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",
            "bioactivity_results": [
              {
                "assay_id": "ECBD-A-003",
                "activity_type": "EC50",
                "activity_value": 45.2,
                "activity_unit": "uM",
                "target": "COX2"
              }
            ],
            "bioprofiling": {
              "selectivity_index": 0.21,
              "hit_rate": 0.08,
              "cytotoxicity_flag": false
            },
            "screening_qc_metadata": {
              "plate_id": "ECBD-P-2024-015",
              "z_prime": 0.68,
              "signal_to_noise": 9.1
            },
            "xrefs": {
              "pubchem": "CID2244",
              "chembl": "CHEMBL25"
            }
          }
        }
      ],
      "field_tree": [
        "_id: str",
        "ecbd.name: str",
        "ecbd.smiles: str",
        "ecbd.bioactivity_results[]: list",
        "ecbd.bioactivity_results[].assay_id: str",
        "ecbd.bioactivity_results[].activity_type: str",
        "ecbd.bioactivity_results[].activity_value: float",
        "ecbd.bioactivity_results[].activity_unit: str",
        "ecbd.bioactivity_results[].target: str",
        "ecbd.bioprofiling.selectivity_index: float",
        "ecbd.bioprofiling.hit_rate: float",
        "ecbd.bioprofiling.cytotoxicity_flag: bool",
        "ecbd.screening_qc_metadata.plate_id: str",
        "ecbd.screening_qc_metadata.z_prime: float",
        "ecbd.screening_qc_metadata.signal_to_noise: float",
        "ecbd.xrefs.pubchem: str",
        "ecbd.xrefs.chembl: str",
        "ecbd.xrefs.zinc: str"
      ],
      "findings": [
        "All 4831 documents uploaded successfully (9.66× minimum threshold)",
        "All 20 sampled _ids are valid InChIKeys",
        "3/3 expected novel fields present with >74% non-null coverage"
      ],
      "discrepancies": []
    }
  ]
}
```

Also create `benchmark_outputs/<run_id>/` folder containing:
- Raw skill output files for each case (`<case_id>_relevancy.md`, `<case_id>_site_inspection.md`)
- **`<case_id>_parser_output.json`** for each plugin case — the primary reference for what the parser actually produces. Contains `total_documents`, `field_tree`, `sample_documents` (5 full untruncated docs), `id_samples` (20 _ids), and `field_stats` (non-null % per field path)

## Summary Table (print after run)

Print a summary after saving JSON. Use separate sections for each stage.

**Relevancy / Site Inspection stages** — tabular summary (unchanged):
```
Pipeline Benchmark Run — 2026-05-11
=====================================
Stage: relevancy  |  Cases: 9  |  Verdict Accuracy: 7/9 (78%)
                  |  Score: 58/72 (81%)

Case              Verdict GT          Verdict Pred        Match  Score
ecbd              RECOMMEND_INGEST    RECOMMEND_INGEST    ✓      8/8
signor            RECOMMEND_INGEST    RECOMMEND_INGEST    ✓      8/8
...
```

**Plugin stage** — detailed per-session report (no point scores):
```
Stage: plugin  |  Cases: 3  |  PASS: 2  |  PARTIAL: 1  |  FAIL: 0

── ecbd ──────────────────────────────────────────────────────
Status: PASS
Files: manifest.json ✓  parser.py ✓  version.py ✓  design_rationale.md ✓
CLI:   validate ✓ → dump ✓ (3 files, 12.4 MB) → upload ✓ (4831 docs, expected ≥500) → inspect ✓
IDs:   20/20 valid InChIKeys (100%)
Field coverage:
  bioactivity_results    ✓  98.2% non-null
  bioprofiling           ✓  74.1% non-null
  screening_qc_metadata  ✓  100.0% non-null
Manifest: data_url OK | on_duplicates OK | license OK | version.py wired
Parser output → ecbd_parser_output.json (5 docs, 18 field paths)
  Sample: {_id: "AQTQHPDCURKLKT-PNYVAJAMSA-N", ecbd: {name, smiles, bioactivity_results[], bioprofiling{}, screening_qc_metadata{}, xrefs{}}}
Findings:
  • All 4831 documents uploaded (9.66× threshold)
  • All novel fields present with >74% coverage
Discrepancies: none

── signor ────────────────────────────────────────────────────
Status: PASS
...

── rnacentral ────────────────────────────────────────────────
Status: PARTIAL
Files: manifest.json ✓  parser.py ✓  version.py ✓  design_rationale.md ✗
CLI:   validate ✓ → dump ✓ (4 files, 89.2 MB) → upload ✓ (1203 docs, expected ≥1000) → inspect ✓
IDs:   18/20 valid URS IDs (90%)
Field coverage:
  rna_type               ✓  100.0% non-null
  rfam_family            ✓  42.3% non-null
  database_xrefs         ✓  97.8% non-null
  disease_associations   ✗  not found in output
Manifest: data_url OK | on_duplicates OK | license OK | version.py wired
Parser output → rnacentral_parser_output.json (5 docs, 11 field paths)
  Sample: {_id: "URS0000000A8C", rnacentral: {rna_type, rfam_family, database_xrefs[], ...}}
  ⚠ disease_associations absent from field tree
Findings:
  • 1203 documents uploaded (1.20× threshold)
  • 2 malformed _ids: URS_INVALID_001, URS_INVALID_002
  • disease_associations field missing from parser output
Discrepancies:
  • Missing field: disease_associations (expected from site_inspection ground truth)
  • design_rationale.md not generated
```

```
CRITICAL FAILURES: none
REGRESSIONS vs prior run: ttd (was NEEDS_REVIEW, now RECOMMEND_INGEST)
```

## Decision Rules
- **NEVER reuse** existing files in `agent_outputs/` — always invoke each skill fresh
- A RECOMMEND_INGEST prediction for a `blocked` or `no_license` case = critical failure
- A RECOMMEND_INGEST prediction for a `do_not_ingest` case = critical failure (skipped a level)
- `upload` with 0 documents = FAIL regardless of exit code
- If a skill errors or produces no parseable output: relevancy/site_inspection score = 0; plugin status = FAIL with error details recorded
- Compare against the previous benchmark run and flag any verdict changes as regressions or improvements
- Plugin stage never produces a numeric score — use `PASS` / `PARTIAL` / `FAIL` status with detailed findings

## Adding New Cases
1. Add a new entry to `references/benchmark-cases.json` following the existing schema
2. Include `source_artifacts` pointing to the actual agent output files used as ground truth
3. Tag with `"core"` for it to be included in default runs
4. Recommended: include at least one case per verdict class and one case per failure mode

## Example Invocations
- `pipeline-benchmarker` — quick relevancy-only run on all 9 core cases
- `pipeline-benchmarker all` — full pipeline run (takes longer; downloads real data)
- `pipeline-benchmarker robustness` — only gofcards + circtarget; tests hard-stop detection
- `pipeline-benchmarker ecbd signor --stage plugin` — re-run plugin stage only for two known-good cases
https://coconut.naturalproducts.net/api-documentation