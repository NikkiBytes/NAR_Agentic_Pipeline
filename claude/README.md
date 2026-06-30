# claude/ — Claude / Cline Agent Skills

This folder contains the Claude/Cline implementation of the NAR BioThings agentic pipeline. It mirrors the skills in `../warp/` but is structured for use with Claude via the [Cline](https://github.com/clinebot/cline) VS Code extension or any Claude-compatible agent that supports `.clinerules` and `CLAUDE.md` project rules.

## Entry Points

| File | Purpose |
|------|---------|
| `.clinerules` | Cline hook — loaded automatically when Cline starts in this repo. Tells the agent where to find project rules and how to trigger the pipeline. |
| `CLAUDE.md` | Project rules for Claude — defines output locations, stage sequencing, and key behaviors. Read this before running anything. |
| `SKILL.md` | Full pipeline orchestrator — chains all three stages end-to-end. This is the main skill to invoke when running the pipeline. |

## Skills

### Pipeline Orchestrator
**`SKILL.md`** — Runs the complete datasource-to-plugin pipeline in one shot. Chains Stage 1 → Stage 2 with gate checks between each. Reads each stage's `SKILL.md` as it reaches that stage.

### Stage Skills

| Folder | Stage | What it does |
|--------|-------|--------------|
| `nar-biothings-scanner/` | Upstream discovery | Scans a NAR Database Issue to produce a ranked list of 10–20 ingestible candidates |
| `datasource-evaluation/` | Stage 1 | Combined relevancy analysis + site inspection in one pass. Scores relevance (0–5), novelty (0–5), openness (PASS/FAIL); verifies downloads, samples schema, classifies fields. Outputs both `_relevancy.json` (verdict) and `_inspection.json` (status) |
| `biothings-plugin-generator/` | Stage 2 | Generates `manifest.json`, `parser.py`, `version.py`, and `design_rationale.md`. Validates with `biothings-cli` |
| `pipeline-benchmarker/` | Evaluation | Runs all pipeline stages against curated ground-truth cases and scores accuracy |

## References

`references/` contains shared reference data used across stages:

- `existing-biothings-plugins.json` — plugins already in pending.api (used to avoid redundancy)
- `pending-api-datasources.json` — datasources already tracked in the pipeline

Each stage skill folder also has its own `references/` with stage-specific docs (URL resolution guides, manifest schema, parser patterns, etc.).

## How to Invoke

**Run the full pipeline (Cline / Claude):**
```
Run the full BioThings pipeline for https://academic.oup.com/nar/article/53/D1/D1383/7832351
```
```
Run the BioThings pipeline for SIGNOR
```

**Run a single stage:**
```
Evaluate DMRdb for BioThings ingestion
```
```
Run site inspection for COCONUT
```

**Discover new candidates:**
```
Scan NAR 2025 for BioThings-ingestible databases
```

**Optional pipeline flags:**
- `--skip-plugin` — stop after evaluation
- `--force` — continue past `NEEDS_REVIEW` without pausing
- `--with-reports` — also write `.md` reports alongside JSON outputs
- `--with-parser-report` — include `parser_report.json` in plugin output

## Outputs

All outputs go to `../warp/agent_outputs/` (shared with the Warp implementation):

```
agent_outputs/
├── pipeline_state.json
└── <name>_datasource/
    ├── <name>_relevancy.json
    ├── <name>_inspection.json
    └── <name>_plugin/
        ├── manifest.json
        ├── parser.py
        ├── version.py
        └── design_rationale.md
```

## Key Behaviors

- The pipeline does **not** stop between stages to ask for confirmation — unless a gate check triggers a `STOP`.
- All context (URLs, schema, identifiers) is carried forward through JSON output files. Do not re-supply information already captured by a prior stage.
- Every generated plugin must pass `biothings-cli` validation before being declared complete.
- Markdown reports are optional — the JSON is the canonical output.
