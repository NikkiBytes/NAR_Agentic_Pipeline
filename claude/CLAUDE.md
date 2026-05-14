# BioThings Agentic Pipeline — Project Rules

## Pipeline Orchestrator
When the user asks to "run the pipeline", "run the full pipeline", "evaluate a datasource", or provides a NAR/OUP article URL, read and follow the instructions in `SKILL.md` (in this directory). That file defines the full 3-stage pipeline (relevancy → site inspection → plugin generation) with gate checks and output formats.

## Individual Stage Skills
Each stage has its own detailed skill file in this directory:
- `datasource-relevancy-analysis/SKILL.md` — Stage 1: relevancy evaluation
- `datasource-site-inspection/SKILL.md` — Stage 2: site inspection
- `biothings-plugin-generator/SKILL.md` — Stage 3: plugin generation
- `pipeline-benchmarker/SKILL.md` — benchmarking/regression testing

When running the full pipeline, read each stage's SKILL.md as you reach that stage. Do not skip reading them — they contain required output schemas, decision rules, and validation steps.

## Output Location
All outputs go to `agent_outputs/<datasource_name>_datasource/`. Pipeline state is tracked in `agent_outputs/pipeline_state.json`.

## Key Behaviors
- Do NOT stop between pipeline stages to ask the user for confirmation (unless a gate check triggers a STOP).
- Carry all context (URLs, schema, identifiers) forward between stages via the JSON output files.
- Always validate generated plugins with `biothings-cli` before declaring them complete.
