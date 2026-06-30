---
name: biothings-pipeline
description: >-
  Run the full BioThings plugin pipeline end-to-end for a given datasource.
  Chains two stages — datasource evaluation (relevancy + site inspection in
  one pass) and plugin generation — without stopping between them. Use when
  a user provides a datasource URL (typically a NAR article link) or datasource
  name and wants the complete pipeline output: relevancy verdict, site
  inspection report, and a validated BioThings plugin. Do not use for
  single-stage runs; invoke the individual stage skills directly for those.
---

# BioThings Pipeline Orchestrator

## Purpose
Run the complete datasource-to-plugin pipeline in one shot. The user provides a single input (NAR article URL, datasource homepage, or datasource name) and this orchestrator drives both stages to completion, passing outputs between them automatically.

## Input
One of:
- An OUP/NAR article URL (e.g., `https://academic.oup.com/nar/article/53/D1/D1383/7832351`)
- A datasource homepage URL (e.g., `https://ecbd.eu`)
- A datasource name (e.g., `SIGNOR`)

Optional user flags:
- `--skip-plugin` — stop after evaluation (skip plugin generation)
- `--force` — continue past NEEDS_REVIEW verdicts without pausing
- `--with-reports` — generate `.md` reports at each stage in addition to JSON
- `--with-parser-report` — include parser_report.json in plugin output

## Pipeline Stages

### Stage 1: Datasource Evaluation (Relevancy + Inspection)
**Skill**: `datasource-evaluation/SKILL.md`
**Action**: Read and follow all instructions in `datasource-evaluation/SKILL.md`. This skill performs relevancy analysis and site inspection in a single pass. It handles the relevancy gate internally — if the verdict is `DO_NOT_INGEST`, the skill stops and reports without proceeding to inspection.
**Output**: Both `agent_outputs/<name>_datasource/<name>_relevancy.json` and `agent_outputs/<name>_datasource/<name>_inspection.json`

### Gate — Inspection Check
| Status                | Action                                                  |
|------------------------|--------------------------------------------------------|
| `VERIFIED`             | Proceed to Stage 2 immediately                         |
| `PARTIALLY_VERIFIED`   | Proceed to Stage 2 (log warnings about unverified items)|
| `BLOCKED`              | **STOP.** Report the blocker. Do not generate a plugin. |

Note: The `DO_NOT_INGEST` relevancy verdict is handled internally by the evaluation skill — it will not produce an inspection JSON, so the pipeline stops before this gate.

### Stage 2: Plugin Generation
**Skill**: `biothings-plugin-generator/SKILL.md`
**Action**: Read and follow all instructions in `biothings-plugin-generator/SKILL.md`. Use the inspection JSON from Stage 1 to populate download URLs, schema fields, primary key, and target API — do not re-prompt the user for information already captured.
**Output**: `agent_outputs/<name>_datasource/<name>_plugin/` containing `manifest.json`, `parser.py`, `version.py`, `design_rationale.md`

This stage includes the full `biothings-cli` validation workflow (validate → dump → upload → list → inspect) as defined in the plugin generator skill.

## Data Flow Between Stages

```
User Input (URL or name)
        │
        ▼
┌─────────────────────────┐
│  Stage 1: Evaluation    │──→ <name>_relevancy.json
│  (datasource-evaluation │    + <name>_inspection.json
│   /SKILL.md)            │    Contains: verdict, scores, download URLs,
│                         │    license, verified schema, ingestion path,
│  Phases:                │    novel/redundant fields, primary key
│   1. Research & Gather  │
│   2. Relevancy Scoring  │    Internal gate: DO_NOT_INGEST → STOP
│   3. Deep Inspection    │    (no inspection JSON produced)
│   4. Save Both JSONs    │
└────────────┬────────────┘
             │ Gate: BLOCKED → STOP
             ▼
┌─────────────────────────┐
│  Stage 2: Plugin Gen    │──→ <name>_plugin/
│  (biothings-plugin-     │    Contains: manifest.json, parser.py,
│   generator/SKILL.md)   │    version.py, design_rationale.md
└─────────────────────────┘
```

Stage 2 reads Stage 1's inspection JSON from `agent_outputs/<name>_datasource/`. Do not ask the user to re-supply information that was already captured.

## Pipeline State Tracking

Maintain `agent_outputs/pipeline_state.json` throughout the run. Each stage updates this file (as specified in the individual skill instructions). The file tracks all datasources processed and their current stage.

Initialize the file if it does not exist:
```json
{
  "datasources": {}
}
```

Each datasource entry is updated by the individual stage skills as they execute.

## Execution Rules

1. **No stopping between stages.** Unless a gate condition triggers a STOP, proceed directly from one stage to the next. Do not ask the user for confirmation between stages.
2. **Carry context forward.** The evaluation stage's JSON outputs feed the plugin generation stage. Do not discard or re-derive information already captured.
3. **Follow sub-skill instructions exactly.** This orchestrator defines the sequencing and gates. The detailed work of each stage is defined in its own SKILL.md — read and follow those instructions completely.
4. **Report progress briefly.** At the start of each stage, print one line: `── Stage N: <stage name> ──`. At gates, print the verdict/status and whether the pipeline continues or stops.
5. **On failure mid-stage**: If any stage encounters an unrecoverable error (e.g., cannot resolve the article URL, all download URLs are inaccessible), stop and report what succeeded and what failed. Do not silently skip a stage.

## Output Summary

After the final stage completes (or a gate stops the pipeline), print a brief summary:

```
Pipeline complete for <datasource_name>
─────────────────────────────────
Stage 1 — Evaluation:   RECOMMEND_INGEST (relevance: 5, novelty: 4, openness: PASS)
                        VERIFIED (3 files, bulk_download)
Stage 2 — Plugin:       GENERATED (validate ✓, dump ✓, upload ✓, N docs)
─────────────────────────────────
Output: agent_outputs/<name>_datasource/
```

## Examples
- `Run the full BioThings pipeline for https://academic.oup.com/nar/article/53/D1/D1383/7832351`
- `Run the BioThings pipeline for SIGNOR`
- `Run the pipeline for https://ecbd.eu --with-reports`
- `Run the pipeline for https://academic.oup.com/nar/article/53/D1/D1016/7905315 --skip-plugin`
