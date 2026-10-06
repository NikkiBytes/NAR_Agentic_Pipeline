# NAR Agentic Pipeline

An agentic pipeline for discovering, evaluating, and ingesting biomedical datasources from the [Nucleic Acids Research (NAR) Database Issue](https://academic.oup.com/nar/issue/53/D1) into the [BioThings](https://biothings.io) API ecosystem (MyChem.info, MyGene.info, MyDisease.info, MyVariant.info, pending.api).

Given nothing more than a datasource name or URL, the pipeline decides whether it's worth ingesting, checks that its data is actually reachable and usable, and — if so — writes the BioThings plugin code needed to pull it in. Claude/Cline agent skills drive each step; gated verdicts stop the run early on datasources that turn out to be duplicates, closed, or unreachable, so effort isn't wasted generating plugins for sources that shouldn't be ingested.

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
           Output: manifest.json, parser.py, version.py, README.md
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

## Pipeline Skills

All skills live under `claude/`:

| Skill | Purpose |
|-------|---------|
| `nar-biothings-scanner` | Scan a NAR Database Issue to discover 10–20 ingestible candidates |
| `datasource-evaluation` | Score a datasource for relevance, novelty, and openness; verify download URLs and sample the data schema — combined relevancy + inspection in one pass |
| `biothings-plugin-generator` | Generate `manifest.json`, `parser.py`, `version.py`, and `README.md` |
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
│       └── README.md
```

## Getting Started

### Prerequisites

- Python ≥ 3.10
- `git` and `curl` (used by the skills and by `biothings-cli`)
- An agent host: [Claude Code](https://claude.com/claude-code) or the [Cline](https://github.com/clinebot/cline) VS Code extension

### Install

```bash
git clone https://github.com/<org>/NAR_Agentic_Pipeline.git
cd NAR_Agentic_Pipeline
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
biothings-cli --help    # should list the `dataplugin` command, not a traceback
```

> **biothings must be ≥ 1.1.0.** `biothings` 1.0.x crashes on startup with
> `AttributeError: module 'typer' has no attribute 'rich_utils'` when `typer` ≥ 0.17 is installed
> (fixed upstream in [biothings.api#426](https://github.com/biothings/biothings.api/pull/426)).
> If you're stuck on 1.0.x, `pip install "typer<0.17"` also works.

### Optional: NCBI API key

Stage 1 verifies DOIs/PMIDs through NCBI E-utilities, which are rate-limited to 3 requests/s without a key. This is usually fine for single datasources; for scanner or benchmark runs, get a key ([NCBI account settings](https://www.ncbi.nlm.nih.gov/account/settings/)) and tell the agent to append `&api_key=<your-key>` to E-utilities calls (see [`nar-url-resolution.md`](claude/datasource-evaluation/references/nar-url-resolution.md)).

### First run

Launch the agent from the repo root (so outputs land in `agent_outputs/`). `agent_outputs/` and `pipeline_state.json` are created on the first run.

- **Cline**: `claude/.clinerules` points the agent at `claude/CLAUDE.md` automatically.
- **Claude Code**: rules in `claude/CLAUDE.md` aren't loaded at startup from the repo root, so reference them in your first prompt:
  `Read claude/CLAUDE.md, then run the full BioThings pipeline for SIGNOR`

## Quickstart

**Run the full pipeline for a datasource:**
> See [First run](#first-run) for how the agent picks up `claude/CLAUDE.md`. Then ask: `Run the full BioThings pipeline for <URL or datasource name>`

**Run a single stage:**
> Ask the agent to invoke the individual stage skill directly (e.g., `Evaluate SIGNOR for BioThings ingestion`).

**Discover new candidates from a NAR issue:**
> Ask the agent to run `nar-biothings-scanner` on NAR 2025 or 2026.

**Pipeline flags** (append to the request): `--skip-plugin` (stop after evaluation), `--force` (continue past `NEEDS_REVIEW`), `--with-reports` (also write `.md` reports), `--with-parser-report` (include `parser_report.json`).

## Testing a Generated Plugin Manually

Stage 2 runs this automatically, but to re-check a plugin yourself:

```bash
cd agent_outputs/<name>_datasource/<name>_plugin

# biothings-cli calls git internally — a local-only repo with a dummy remote is enough
git init && git add . && git commit -m "Initial plugin files"
git remote add origin /dev/null

biothings-cli dataplugin validate    # lint manifest.json
biothings-cli dataplugin dump        # run version.py, download data_url files
biothings-cli dataplugin upload      # run parser.load_data() into local SQLite
biothings-cli dataplugin list        # confirm the collection exists
biothings-cli dataplugin inspect -s <name>   # field types + stats
```

**An `upload` that exits 0 but yields zero documents is a failure.** Check the doc count in `list`/`inspect`.

The full step-by-step spec (pass criteria, common failures) is in [`cli-validation-workflow.json`](claude/biothings-plugin-generator/references/cli-validation-workflow.json).


## Skills in Detail

### `nar-biothings-scanner` — discovery (optional, upstream)

Scans a NAR Database Issue (2025+) editorial and its cited papers to find 10–20 candidate datasources worth ingesting into BioThings. Filters against known BioThings sources and pending.api plugins to avoid duplicates, scores each candidate on relevance/novelty/openness, and ranks them.

- **Output**: `agent_outputs/NAR_BioThings_Ingestion_Report_<YEAR>.md` — markdown report with per-candidate metadata (URL, DOI, identifiers, data format, BioThings fit) plus an ingestion strategy section. Feeds candidate names into Stage 1.

### `datasource-evaluation` — Stage 1 (gated)

Given one datasource (name/URL), answers five questions in one pass: **is it relevant, novel, open, actually downloadable, and what's in the files.** Verifies `DOI/PMID/PMC` via a live lookup — never from memory, (*NAR DOIs within the same issue are easy to misremember.*)

- **Outputs** (to `agent_outputs/<name>_datasource/`):
  - `<name>_relevancy.json` — verdict (`RECOMMEND_INGEST` / `NEEDS_REVIEW` / `DO_NOT_INGEST`), scores, license, URLs
  - `<name>_inspection.json` — status (`VERIFIED` / `PARTIALLY_VERIFIED` / `BLOCKED`), download files, schema/fields classified NOVEL vs REDUNDANT, recommended `_id` strategy, and a `plugin_inputs` block consumed directly by Stage 2
- **Gate**: a `DO_NOT_INGEST` verdict stops the pipeline here — no Stage 2 run.

### `biothings-plugin-generator` — Stage 2

Takes the inspection JSON's `plugin_inputs` and generates the actual ingestion code. Verifies every candidate download URL actually returns data (not HTML) before writing anything, and re-verifies the DOI rather than trusting what Stage 1 recorded.

- **Outputs** (to `agent_outputs/<name>_datasource/<name>_plugin/`):
  - `manifest.json` — data URLs, parser reference, license/publication metadata
  - `parser.py` — generator function that yields `_id`-keyed documents
  - `version.py` — fetches the datasource's current release string
  - `README.md` — why these files/fields were chosen, sample output docs, field coverage %, CLI test results
- Also runs `biothings-cli validate → dump → upload → list → inspect` and updates `references/built-plugins-index.md`.

### `pipeline-benchmarker` — QA, run on demand

Not part of the normal per-datasource flow — used after editing a skill, or periodically, to catch regressions. Re-runs the pipeline fresh (never reuses cached `agent_outputs/`) against curated ground-truth cases in `references/benchmark-cases.json`.

- **Outputs** (to `benchmark_outputs/<run_id>/`):
  - `benchmark_run_<timestamp>.json` — verdict/score accuracy per case
  - `<case_id>_relevancy.md`, `<case_id>_site_inspection.md` — raw skill outputs per case
  - `<case_id>_parser_output.json` — 5 full sample documents, field tree, `_id` samples, field non-null stats
  - Prints a tabular summary (relevancy/inspection) and a per-session narrative report (plugin stage: PASS / PARTIAL / FAIL)

All stages read and update `agent_outputs/pipeline_state.json`, which tracks each datasource's current stage, verdict, and status.

## Contributing

- **Editing a skill**: after changing any `SKILL.md` or its references, run `pipeline-benchmarker` (ask: `Run the pipeline benchmark`) and compare against the previous run in `claude/benchmark_outputs/` to catch regressions.
- **Adding a skill**: create `claude/<skill-name>/SKILL.md` (with `name`/`description` frontmatter) plus a `references/` folder, then add it to the skills tables here and in `claude/README.md`, and to `claude/CLAUDE.md` if the orchestrator should call it.
- **Adding benchmark cases**: append to `claude/pipeline-benchmarker/references/benchmark-cases.json` (the file the benchmarker loads) following the existing schema.

## Candidates Tracked

See `Pipeline_Scan_and_Verify_plugins.md` for the current run's candidate list, built plugins, and pipeline status.
