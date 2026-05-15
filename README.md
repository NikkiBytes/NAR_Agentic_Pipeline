# NAR Agentic Pipeline

An agentic pipeline for discovering, evaluating, and ingesting biomedical datasources from the [Nucleic Acids Research (NAR) Database Issue](https://academic.oup.com/nar/issue/53/D1) into the [BioThings](https://biothings.io) API ecosystem (MyChem.info, MyGene.info, MyDisease.info, MyVariant.info, pending.api).

## Overview

The pipeline takes a datasource — identified by a NAR article URL, a datasource homepage, or a name — and drives it through three automated stages:

```
NAR Scanner (optional discovery)
        │
        ▼
Stage 1 — Relevancy Analysis
        │  Verdict: RECOMMEND_INGEST / NEEDS_REVIEW / DO_NOT_INGEST
        ▼
Stage 2 — Site Inspection
        │  Status: VERIFIED / PARTIALLY_VERIFIED / BLOCKED
        ▼
Stage 3 — Plugin Generation
           Output: manifest.json, parser.py, version.py, design_rationale.md
```

Each stage produces structured JSON outputs. Stages are gated — a `DO_NOT_INGEST` or `BLOCKED` result stops the pipeline before wasting effort on later stages.

## Repository Structure

```
NAR_Agentic_Pipeline/
├── warp/                          # Warp (Oz) agent skills
│   ├── agent_outputs/             # All pipeline outputs (JSON + plugins)
│   │   └── pipeline_state.json   # Tracks every datasource processed
│   ├── nar-biothings-scanner/     # Upstream discovery skill
│   ├── datasource-relevancy-analysis/
│   ├── datasource-site-inspection/
│   ├── biothings-plugin-generator/
│   └── pipeline-benchmarker/
├── claude/                        # Claude / Cline agent skills (same pipeline)
│   ├── CLAUDE.md                  # Project rules for Claude
│   ├── SKILL.md                   # Full pipeline orchestrator
│   ├── .clinerules                # Cline hook → reads CLAUDE.md on startup
│   ├── nar-biothings-scanner/
│   ├── datasource-relevancy-analysis/
│   ├── datasource-site-inspection/
│   ├── biothings-plugin-generator/
│   ├── pipeline-benchmarker/
│   └── references/                # Shared reference data (known sources, pending plugins)
└── Pipeline_Scan_and_Verify_plugins.md   # Active pipeline run doc (candidates + status)
```

## Agent Implementations

The same pipeline logic is implemented twice — once for each agent environment:

| Folder | Agent | Entry point |
|--------|-------|-------------|
| `warp/` | Warp (Oz) | Oz reads `warp/*/SKILL.md` automatically via skill registry |
| `claude/` | Claude / Cline | Cline reads `claude/CLAUDE.md` via `.clinerules`; invoke via `claude/SKILL.md` |

Skills in both folders are kept in sync. When a skill is updated, update both.

## Pipeline Skills

| Skill | Purpose |
|-------|---------|
| `nar-biothings-scanner` | Scan a NAR Database Issue to discover 10–20 ingestible candidates |
| `datasource-relevancy-analysis` | Score a datasource for relevance, novelty, and openness; produce a verdict |
| `datasource-site-inspection` | Verify download URLs, sample the data schema, confirm ingestion path |
| `biothings-plugin-generator` | Generate `manifest.json`, `parser.py`, `version.py`, and `design_rationale.md` |
| `pipeline-benchmarker` | Evaluate pipeline accuracy against curated ground-truth cases |

## Outputs

All pipeline outputs live under `warp/agent_outputs/`:

```
warp/agent_outputs/
├── pipeline_state.json               # Global state: all datasources + their current stage
├── <name>_datasource/
│   ├── <name>_relevancy.json         # Stage 1 output
│   ├── <name>_inspection.json        # Stage 2 output
│   └── <name>_plugin/
│       ├── manifest.json
│       ├── parser.py
│       ├── version.py
│       └── design_rationale.md
```

## Quickstart

**Run the full pipeline for a datasource (Warp):**
> Ask Oz: `Run the BioThings pipeline for https://academic.oup.com/nar/article/...`

**Run the full pipeline for a datasource (Cline/Claude):**
> The `.clinerules` file in `claude/` ensures the agent reads `CLAUDE.md` on startup. Then ask: `Run the full BioThings pipeline for <URL or datasource name>`

**Run a single stage:**
> Ask Oz or Claude to invoke the individual stage skill directly (e.g., `Evaluate SIGNOR for BioThings ingestion`).

**Discover new candidates from a NAR issue:**
> Ask the agent to run `nar-biothings-scanner` on NAR 2025 or 2026.

## Candidates Tracked

See `Pipeline_Scan_and_Verify_plugins.md` for the current run's candidate list, built plugins, and pipeline status.
