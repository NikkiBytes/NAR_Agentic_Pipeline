---
name: pipeline-benchmarker
description: >-
  Evaluate the BioThings plugin agent pipeline against curated ground-truth
  test cases. Run when you want to measure skill accuracy, detect regressions
  after skill edits, or generate performance metrics for reporting. Scores
  each pipeline stage (datasource-relevancy-analysis, datasource-site-inspection,
  biothings-plugin-generator) against known verdicts and saves structured JSON
  results to benchmark_outputs/. Do not use for general testing or non-BioThings
  benchmarks.
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
4. Score against ground truth using the rubric below
5. Save one JSON run record to `benchmark_outputs/benchmark_run_<YYYYMMDD_HHMMSS>.json`
6. Print a summary table

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
1. Invoke `datasource-relevancy-analysis` using the case's `test_prompt`
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
2. Invoke `datasource-site-inspection` using the case's URL
3. Parse: `status`, `download_accessible`, `primary_key_field`, `target_api`
4. Score using the Site Inspection Rubric
5. Save the output to `benchmark_outputs/<run_id>/<case_id>_site_inspection.md`

### Stage 3 — Plugin Generation
For each case with `"plugin"` in `stages`:
1. Invoke `biothings-plugin-generator` using the case name and prior site inspection output
2. Check required files are present: `manifest.json`, `parser.py`, `version.py`
3. Run `biothings-cli` validation suite: validate → dump → upload → list → inspect
4. Parse: `validate_pass`, `dump_pass`, `upload_pass`, `documents_yielded`, `id_format_check`
5. Score using the Plugin Rubric

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

### Plugin Rubric (max 10 points)
- manifest.json present: 1 point
- parser.py present: 1 point
- version.py present: 1 point
- design_rationale.md present: 1 point
- validate pass: 2 points
- dump pass: 2 points
- upload pass (non-zero docs): 2 points
- _id format correct: 1 point

## Output Format

Save to `benchmark_outputs/benchmark_run_<YYYYMMDD_HHMMSS>.json`:

```json
{
  "run_id": "benchmark_run_20260511_060000",
  "run_date": "2026-05-11",
  "run_timestamp": "2026-05-11T06:00:00Z",
  "cases_run": 9,
  "stages_run": ["relevancy"],
  "summary": {
    "relevancy_verdict_accuracy": 0.78,
    "relevancy_score_pct": 0.82,
    "site_inspection_accuracy": 0.85,
    "plugin_pass_rate": 0.90,
    "overall_pct": 0.84,
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
    }
  ]
}
```

Also create `benchmark_outputs/<run_id>/` folder containing the raw skill output files for each case.

## Summary Table (print after run)

Print a summary table after saving JSON:

```
Pipeline Benchmark Run — 2026-05-11
=====================================
Stage: relevancy  |  Cases: 9  |  Verdict Accuracy: 7/9 (78%)
                  |  Score: 58/72 (81%)

Case              Verdict GT          Verdict Pred        Match  Score
ecbd              RECOMMEND_INGEST    RECOMMEND_INGEST    ✓      8/8
signor            RECOMMEND_INGEST    RECOMMEND_INGEST    ✓      8/8
...

CRITICAL FAILURES: none
REGRESSIONS vs prior run: ttd (was NEEDS_REVIEW, now RECOMMEND_INGEST)
```

## Decision Rules
- **NEVER reuse** existing files in `agent_outputs/` — always invoke each skill fresh
- A RECOMMEND_INGEST prediction for a `blocked` or `no_license` case = critical failure
- A RECOMMEND_INGEST prediction for a `do_not_ingest` case = critical failure (skipped a level)
- `upload_pass` with 0 documents = FALSE regardless of exit code
- If a skill errors or produces no parseable output: score = 0 for that case/stage
- Compare against the previous benchmark run and flag any verdict changes as regressions or improvements

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
