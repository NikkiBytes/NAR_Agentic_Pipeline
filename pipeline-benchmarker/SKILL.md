---
name: pipeline-benchmarker
description: >-
  Evaluate the BioThings plugin agent pipeline against curated ground-truth
  test cases. Run when you want to measure skill accuracy, detect regressions
  after skill edits, or generate performance metrics for reporting. Scores
  each pipeline stage (datasource-relevancy-analysis, datasource-site-inspection,
  biothings-plugin-generator) against known verdicts and saves structured JSON
  results to benchmark_outputs/.
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
3. Parse the structured fields from each skill's markdown output
4. Score against ground truth using the rubric below
5. Save one JSON run record to `benchmark_outputs/benchmark_run_<YYYYMMDD_HHMMSS>.json`
6. Print a summary table

## Test Case Selection

Default (no args): run all cases tagged `"core"` for the `relevancy` stage only (fastest).

Override with:
- `/pipeline-benchmarker all` — all cases, all stages they support
- `/pipeline-benchmarker relevancy` — relevancy stage only, all core cases
- `/pipeline-benchmarker plugins` — only cases with a `plugin` stage (ecbd, signor, rnacentral)
- `/pipeline-benchmarker ecbd signor` — specific case IDs only
- `/pipeline-benchmarker --stage site_inspection` — only site_inspection stage for eligible cases
- `/pipeline-benchmarker robustness` — only cases tagged `blocked` or `no_license` (tests hard-stop detection)

## Stage Execution

### Stage 1 — Relevancy Evaluation
For each case with `"relevancy"` in `stages`:
1. Invoke `datasource-relevancy-analysis` using the case's `test_prompt`
2. Parse from the skill's markdown output:
   - `verdict` — first occurrence of `RECOMMEND_INGEST`, `NEEDS_REVIEW`, or `DO_NOT_INGEST` in the `**Verdict**:` line
   - `relevance_score` — integer from `Relevance: X/5`
   - `novelty_score` — integer from `Novelty: X/5`
   - `openness_verdict` — `PASS` or `FAIL` from `Openness: PASS|FAIL`
   - `openness_score` — integer from the `(X/5)` after PASS/FAIL
   - `license` — value from `License/Access` evidence bullet
3. Score using the Relevancy Rubric
4. Save the output markdown to `benchmark_outputs/<run_id>/<case_id>_relevancy.md`

### Stage 2 — Site Inspection
For each case with `"site_inspection"` in `stages`:
1. First check: if a `relevancy` stage was run in this session for this case, use its output. Otherwise load the source artifact from `source_artifacts.relevancy`.
2. Invoke `datasource-site-inspection` using the case's URL
3. Parse from the skill's markdown output:
   - `status` — `VERIFIED`, `PARTIALLY_VERIFIED`, or `BLOCKED` from `**Status**:` line
   - `download_accessible` — whether Download Files section lists `public` (true) or `login-required` (false)
   - `primary_key_field` — value from `**Primary key field**:` under Recommended Plugin Inputs
   - `target_api` — value from `**Target API**:`
4. Score using the Site Inspection Rubric
5. Save the output markdown to `benchmark_outputs/<run_id>/<case_id>_site_inspection.md`

### Stage 3 — Plugin Generation
For each case with `"plugin"` in `stages`:
1. Invoke `biothings-plugin-generator` using the case name and prior site inspection output
2. Check required files are present in the plugin directory:
   - `manifest.json`, `parser.py`, `version.py`, `README.md`
3. Run `biothings-cli` validation suite in order:
   ```bash
   biothings-cli dataplugin validate
   biothings-cli dataplugin dump
   biothings-cli dataplugin upload
   biothings-cli dataplugin list
   biothings-cli dataplugin inspect
   ```
4. Parse results:
   - `validate_pass` — exit 0 and no ERROR lines
   - `dump_pass` — exit 0 and archive folder populated
   - `upload_pass` — exit 0 AND documents_yielded > 0 (zero docs = FAILURE even on exit 0)
   - `documents_yielded` — integer from upload log
   - `id_format_check` — sample `_id` from inspect output matches expected format
5. Score using the Plugin Rubric

## Scoring Rubrics

### Relevancy Rubric (max 8 points)

| Check | Points | Rule |
|-------|--------|------|
| Verdict exact match | 3 | Predicted matches ground truth exactly |
| Verdict adjacent match | 1 | Off by one level (RECOMMEND↔NEEDS_REVIEW or NEEDS_REVIEW↔DO_NOT_INGEST) |
| Verdict wrong direction | 0 | RECOMMEND vs DO_NOT_INGEST (skipped a level) |
| Relevance score exact | 2 | Predicted = ground truth |
| Relevance score ±1 | 1 | Within 1 of ground truth |
| Novelty score exact | 2 | Predicted = ground truth |
| Novelty score ±1 | 1 | Within 1 of ground truth |
| Openness verdict match | 1 | PASS/FAIL matches exactly |

Note: Relevance/Novelty score points are exclusive (you get max 2 per dimension, not both 2 and 1).

**Critical accuracy check:** For cases tagged `blocked` or `no_license`, the agent MUST detect the openness blocker (FAIL verdict) and set verdict to DO_NOT_INGEST or NEEDS_REVIEW. Setting RECOMMEND_INGEST for a blocked case = 0 points total for that case.

### Site Inspection Rubric (max 6 points)

| Check | Points | Rule |
|-------|--------|------|
| Status exact match | 3 | VERIFIED/PARTIALLY_VERIFIED/BLOCKED |
| Status adjacent | 1 | VERIFIED vs PARTIALLY_VERIFIED only |
| Download accessibility correct | 1 | public vs login-required |
| Primary key field correct | 1 | Matches ground truth field name or semantically equivalent |
| Target API correct | 1 | Matches ground truth BioThings API |

### Plugin Rubric (max 10 points)

| Check | Points | Rule |
|-------|--------|------|
| manifest.json present | 1 | File exists in plugin directory |
| parser.py present | 1 | File exists |
| version.py present | 1 | File exists |
| README.md present | 1 | File exists |
| validate pass | 2 | biothings-cli dataplugin validate exits 0 with no ERROR lines |
| dump pass | 2 | biothings-cli dataplugin dump exits 0 and archive folder populated |
| upload pass (non-zero docs) | 2 | Upload exits 0 AND documents_yielded ≥ ground_truth.plugin.min_documents |
| _id format correct | 1 | Sample _id from inspect matches expected identifier type |

## Output Format

Save to `benchmark_outputs/benchmark_run_<YYYYMMDD_HHMMSS>.json`:

```json
{
  "run_id": "benchmark_run_20260511_060000",
  "run_date": "2026-05-11",
  "run_timestamp": "2026-05-11T06:00:00Z",
  "skill_versions_invoked": {
    "datasource-relevancy-analysis": "from .agents/skills/",
    "datasource-site-inspection": "from .agents/skills/",
    "biothings-plugin-generator": "from .agents/skills/"
  },
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
      "ground_truth": {
        "verdict": "RECOMMEND_INGEST",
        "relevance_score": 5,
        "novelty_score": 3,
        "openness_verdict": "PASS",
        "openness_score": 4
      },
      "predicted": {
        "verdict": "RECOMMEND_INGEST",
        "relevance_score": 5,
        "novelty_score": 3,
        "openness_verdict": "PASS",
        "openness_score": 4
      },
      "verdict_match": true,
      "verdict_distance": 0,
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

Print to stdout after saving JSON:

```
Pipeline Benchmark Run — 2026-05-11
=====================================
Stage: relevancy  |  Cases: 9  |  Verdict Accuracy: 7/9 (78%)
                  |  Score: 58/72 (81%)

Case              Verdict GT          Verdict Pred        Match  Score
ecbd              RECOMMEND_INGEST    RECOMMEND_INGEST    ✓      8/8
signor            RECOMMEND_INGEST    RECOMMEND_INGEST    ✓      8/8
harmonizome       NEEDS_REVIEW        NEEDS_REVIEW        ✓      7/8
ttd               NEEDS_REVIEW        RECOMMEND_INGEST    ✗      4/8  ← REGRESSION
gencode           NEEDS_REVIEW        NEEDS_REVIEW        ✓      6/8
gene_ontology     DO_NOT_INGEST       DO_NOT_INGEST       ✓      8/8
gofcards          DO_NOT_INGEST       DO_NOT_INGEST       ✓      7/8
circtarget        NEEDS_REVIEW        NEEDS_REVIEW        ✓      6/8
rnacentral        NEEDS_REVIEW        NEEDS_REVIEW        ✓      7/8

CRITICAL FAILURES: none
REGRESSIONS vs prior run: ttd (was NEEDS_REVIEW, now RECOMMEND_INGEST)
```

## Decision Rules
- **NEVER reuse** existing files in `agent_outputs/` — always invoke each skill fresh so results reflect the current skill version
- A RECOMMEND_INGEST prediction for a `blocked` or `no_license` case = critical failure — flag in `summary.critical_failures[]`
- A RECOMMEND_INGEST prediction for a `do_not_ingest` case = critical failure (skipped a level entirely)
- `upload_pass` with 0 documents = FALSE regardless of exit code (silent failure per skill spec)
- If a skill errors or produces no parseable output: score = 0 for that case/stage; log error in `notes`
- Compare against the previous benchmark run (most recent file in `benchmark_outputs/`) and flag any verdict changes as regressions or improvements

## Adding New Cases
To extend the benchmark:
1. Add a new entry to `references/benchmark-cases.json` following the existing schema
2. Include `source_artifacts` pointing to the actual agent output files used as ground truth
3. Tag with `"core"` for it to be included in default runs
4. Recommended: include at least one case per verdict class and one case per failure mode (blocked, no_license, redundant)

## Example Invocations
- `/pipeline-benchmarker` — quick relevancy-only run on all 9 core cases
- `/pipeline-benchmarker all` — full pipeline run including site inspection and plugin stages (takes longer; downloads real data)
- `/pipeline-benchmarker robustness` — only gofcards + circtarget; tests hard-stop detection
- `/pipeline-benchmarker ecbd signor --stage plugin` — re-run plugin stage only for two known-good cases
