# NAR Agentic Pipeline

An agentic pipeline for discovering, evaluating, and ingesting biomedical datasources from the [Nucleic Acids Research (NAR) Database Issue](https://academic.oup.com/nar/issue/53/D1) into the [BioThings](https://biothings.io) API ecosystem (MyChem.info, MyGene.info, MyDisease.info, MyVariant.info, pending.api).

## Overview

The pipeline takes a datasource — identified by a NAR article URL, a datasource homepage, or a name — and drives it through two automated stages (plus an optional upstream discovery step):

```
nar-biothings-scanner (optional discovery)
        │
        ▼
Stage 1 — Datasource Evaluation (relevancy + site inspection, single pass)
        │  Verdict: RECOMMEND_INGEST / NEEDS_REVIEW / DO_NOT_INGEST
        │  Status:  VERIFIED / PARTIALLY_VERIFIED / BLOCKED
        ▼
Stage 2 — Plugin Generation
           Output: manifest.json, parser.py, version.py, design_rationale.md
```

Each stage produces structured JSON outputs. Stages are gated — a `DO_NOT_INGEST` verdict or `BLOCKED` status stops the pipeline before wasting effort on the next stage.

## Repository Structure

```
NAR_Agentic_Pipeline/
├── claude/                        # Claude / Cline agent skills (the live implementation)
│   ├── CLAUDE.md                  # Project rules for Claude
│   ├── SKILL.md                   # Full pipeline orchestrator
│   ├── .clinerules                # Cline hook → reads CLAUDE.md on startup
│   ├── nar-biothings-scanner/     # Upstream discovery skill
│   ├── datasource-evaluation/     # Stage 1: relevancy analysis + site inspection combined
│   ├── biothings-plugin-generator/# Stage 2: plugin generation
│   ├── pipeline-benchmarker/      # Evaluation: accuracy against curated ground-truth cases
│   ├── benchmark_outputs/         # Results written by pipeline-benchmarker (gitignored)
│   └── references/                # Shared reference data (known sources, pending plugins)
├── agent_outputs/                 # All pipeline outputs (JSON + plugins)
│   └── pipeline_state.json        # Tracks every datasource processed
└── Pipeline_Scan_and_Verify_plugins.md   # Active pipeline run doc (candidates + status)
```

`datasource-relevancy-analysis/` and `datasource-site-inspection/` are legacy, gitignored leftovers from before the two skills were merged into `claude/datasource-evaluation/`. A separate `warp/` (Oz) implementation existed previously but was removed — `claude/` is the only agent implementation now.

## Pipeline Skills

All skills live under `claude/`:

| Skill | Purpose |
|-------|---------|
| `nar-biothings-scanner` | Scan a NAR Database Issue to discover 10–20 ingestible candidates |
| `datasource-evaluation` | Score a datasource for relevance, novelty, and openness; verify download URLs and sample the data schema — combined relevancy + inspection in one pass |
| `biothings-plugin-generator` | Generate `manifest.json`, `parser.py`, `version.py`, and `design_rationale.md` |
| `pipeline-benchmarker` | Evaluate pipeline accuracy against curated ground-truth cases |

## Outputs

All pipeline outputs live under `agent_outputs/`:

```
agent_outputs/
├── pipeline_state.json               # Global state: all datasources + their current stage
├── <name>_datasource/
│   ├── <name>_relevancy.json         # Stage 1 output
│   ├── <name>_inspection.json        # Stage 1 output
│   └── <name>_plugin/
│       ├── manifest.json
│       ├── parser.py
│       ├── version.py
│       └── design_rationale.md
```

## Quickstart

**Run the full pipeline for a datasource:**
> The `.clinerules` file in `claude/` ensures the agent reads `CLAUDE.md` on startup. Then ask: `Run the full BioThings pipeline for <URL or datasource name>`

**Run a single stage:**
> Ask the agent to invoke the individual stage skill directly (e.g., `Evaluate SIGNOR for BioThings ingestion`).

**Discover new candidates from a NAR issue:**
> Ask the agent to run `nar-biothings-scanner` on NAR 2025 or 2026.

## Candidates Tracked

See `Pipeline_Scan_and_Verify_plugins.md` for the current run's candidate list, built plugins, and pipeline status.
