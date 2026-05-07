# BioThings Plugin Generator — Tech Backlog

Tracks all design decisions, changes made, and outstanding work items for this skill.
Update this file whenever a decision is made, a change is applied, or a new improvement is identified.

---

## Decision Log

Decisions made during skill design and iteration, in chronological order.

### [2026-04-16] Initial skill authored
- Created `SKILL.md` with sections for file structure, manifest generation, parser generation, `_id` strategy, document structure, and output
- Included inline code templates for all major parser patterns (CSV, groupby, pandas, HGVS, multi-file, JSON, API dump-then-parse)
- Decision: skill works standalone but will load prior site inspection reports from `agent_outputs/` if available

### [2026-04-16] Added references/ directory
- Created `references/built-plugins-index.md` — local registry of all generated plugins to prevent duplicate work
  - Pre-populated with `ecbd` (MyChem.info, InChIKey, multi-file CSV) and `signor` (pending.api, SIGNOR ID, TSV groupby)
- Created `references/production-plugin-examples.md` — four real annotated plugins fetched from GitHub:
  - Pattern 1: DISEASES (multi-file TSV + itertools.groupby + DOID→MONDO resolution)
  - Pattern 2: disgenet (pandas gzip + defaultdict + UMLS→MONDO via bundled mondo.json)
  - Pattern 3: FoodData (JSON + subject/object/relation triple + composite _id)
  - Pattern 4: go (shared OBO parser via parser_kwargs — no custom parser.py)
- Created `references/manifest-schema.md` — complete field reference for manifest.json with validated examples
- Rationale: skill was generating code from abstract guidance alone; real examples reduce pattern drift and prevent common mistakes

### [2026-04-16] Added Section 0 (load reference files first)
- Skill now explicitly instructs the agent to load all three reference files before doing anything else
- Built-plugins-index check prevents re-generating an existing plugin without user confirmation
- Rationale: without an explicit instruction, agents tend to skip reference files and rely on SKILL.md alone

### [2026-04-16] Added `name` and `description` as required `__metadata__` fields
- Both fields added to the manifest template, manifest-schema.md sub-fields table, all validated examples, and the common mistakes table
- Rationale: user requirement; these fields are essential for Hub discoverability and documentation

### [2026-04-16] Flipped API vs bulk download preference (API-first)
- Section 1c decision tree changed: API is now preferred when available; bulk download is the fallback
- Added explicit "when to fall back" list (auth unavailable, rate limit infeasible, API is query-only interface over the bulk file)
- Decision rules at bottom of SKILL.md updated to match
- Quick reference table in production-plugin-examples.md updated: API pattern now listed first
- Rationale: user requirement — API data is fresher and more granular; bulk files can become stale

### [2026-04-17] Reverted API-first — manifest/bulk download is the only supported ingestion path
- Section 1c reverted: generator now always produces manifest-first plugins using `dumper.data_url`, matching every production example plugin
- Removed API-first decision rules from the Decision Rules block
- Replaced the REST API dump-then-parse section's dumper guidance with a parser-only "pre-dumped JSON files" pattern; custom `dumper.py` templates removed from SKILL.md
- API-first / custom `dumper.py` crawling remains on the backlog (see "Outstanding Improvements" below) — not emitted by the generator today
- Added an **API availability** inspection step to `datasource-relevancy-analysis` (informational only): records endpoint, auth, rate limits, pagination, and record coverage. Does NOT affect the ingest verdict or the generator's strategy.
- Rationale: the manifest must always load as in the reference plugins. API existence is still useful evidence during relevancy/site inspection, but API-based ingestion is explicitly future work.

### [2026-04-16] Added `version.py` as a required generated file
- Moved from "optional" to required in plugin file structure
- Added Section 2b with: exact function signature, 5-step discovery checklist, 4 concrete patterns (dedicated endpoint, JSON info, plain-text summary, dated URL regex)
- Manifest template updated to always include `"release": "version:get_release"` in `dumper`
- manifest-schema.md: `release` changed from optional to required, all examples updated, common mistakes table updated
- built-plugins-index.md: entry template gets a `version.py strategy` field
- Rationale: user requirement — consistent with mygeneset.info production plugins; enables Hub to detect new releases and auto-re-dump

### [2026-05-06] Replaced commented-out Section 7 with a real biothings-cli validation workflow
- Section 7 now defines a 5-step required CLI validation: `dataplugin validate` → `dump` → `upload` → `list` → `inspect`
- Each step documents: purpose, exact command, pass criterion, common failures, on-failure handling
- Added §7.6 cleanup guidance (between-iteration archive pruning) and §7.7 results-recording rules
- Extended §6b `parser_report.json` schema with a `smoke_test.cli_validation` block: `runner`, `runner_version`, and `steps[]` array (one entry per CLI command with `status`, `summary`, `errors[]`)
- Crucially: `dataplugin upload` exit-0 with `documents_yielded == 0` is now treated as FAILURE (the SIGNOR v1.0 silent-failure mode)
- Rationale: user requirement — the parser-only smoke test in §6b runs the parser in isolation and cannot catch manifest schema errors, network failures during dump, or uploaded-document shape regressions. The CLI workflow is the canonical end-to-end gate before a plugin is considered "complete".

---

## Outstanding Improvements

Items identified but not yet implemented. Move to Decision Log when completed.

### High Priority

- **API-first custom `dumper.py` support** — Reintroduce optional API-first ingestion: when a datasource has a well-documented public API (recorded by `datasource-relevancy-analysis`), emit a `dumper.py` that paginates and saves JSON into `data_folder`, with the existing pre-dumped-JSON parser pattern consuming it. Gate behind an explicit user opt-in so the default stays manifest-first. Must include: pagination handling, rate-limit/sleep guidance, auth via env vars, and progress logging.

- ~~**Uncomment and enable testing step**~~ — **DONE 2026-05-06.** Replaced with a full 5-command workflow in §7 (validate → dump → upload → list → inspect) plus `cli_validation` block in `parser_report.json`. Silent zero-doc upload is now flagged as FAILURE.

- **Add data sampling step before parser generation** — Before writing `parser.py`, the agent should download the first 5-10 rows of the actual file (or first API page) and confirm actual column names, delimiters, encoding, and null patterns. Currently the agent relies solely on site inspection reports, which can be stale or incomplete.

- **Handle versioned/dated URLs** — If `data_url` contains a date or version string (e.g., `Apr2026_release.txt`), flag it in the README and suggest a strategy for keeping the URL current (e.g., scrape the releases index in `version.py`, or document the manual update step explicitly).

### Medium Priority

- **Add SDF parsing pattern** — SDF is listed as a supported format in Section 1 but has no example. Chemical databases (MyChem targets) frequently use SDF. Add a pattern using `rdkit.Chem.SDMolSupplier` or equivalent.

- **Add `mapping.py` template and decision rule** — Currently mentioned as optional with no guidance. Add a minimal Elasticsearch mapping template and a rule: generate for core BioThings APIs (MyChem, MyGene, etc.); skip for pending.api prototypes.

- **Add document count logging to parser** — Instruct parsers to log a final summary: total documents yielded, rows skipped, and reason for skipping (missing `_id`, duplicate, parse error). Makes debugging significantly easier.

- **Add pre-yield `_id` length assertion** — Add `assert len(str(_id)) <= 512` pattern to the parser rules. Catches a common Hub rejection mode before upload.

- **Strengthen upstream integration** — Replace "check `agent_outputs/` for prior inspection reports" with the exact glob pattern and field names to extract (e.g., parse `### Download Options` and `### API Crawl Details` sections from `*_site_inspection_*.md`).

### Lower Priority

- **Add `version.py` template to `version.py strategy` in built-plugins-index** — When logging a new plugin, also record which `version.py` pattern was used (A/B/C/D) so future plugins targeting the same datasource family can reuse the approach.

- **Add `version.py` examples to `production-plugin-examples.md`** — The file currently covers manifest + parser but not version.py. Add the KEGG, Reactome, and GO examples from mygeneset.info with annotations.

- **Clarify custom `dumper.py` manifest wiring** — Section 1c shows a `dumper.py` template but the manifest snippet still uses `"data_url": "__REPLACE__"`. Add a complete paired example showing the full manifest + dumper.py for an API-only source.

---

## Testing Plan

### Test Cases to Write
1. "Build a BioThings plugin for SIGNOR" — should produce API-first dumper.py (SIGNOR has a REST API), version.py querying the SIGNOR release endpoint, and use the PTM-view groupby parser pattern
2. "Create a plugin for a datasource that only has a REST API, no bulk download" — should produce custom dumper.py, warn about rate limits, produce version.py
3. "Build a MyChem.info plugin for a new chemical database with a CSV bulk download and an API" — should prefer API (per updated strategy), ask about `_id` field, confirm InChIKey is available

### Assertions to Check Per Run
- `manifest.json` exists and is valid JSON
- `manifest.json` contains `__metadata__` with `name`, `description`, `license`, `license_url`, `url`
- `manifest.json` `dumper` block contains `"release": "version:get_release"`
- `parser.py` contains a `load_data(data_folder)` generator function
- `parser.py` yields dicts with `_id` key
- `version.py` contains a `get_release(self)` function
- `version.py` imports `requests` inside the function body
- `README.md` exists and contains biothings-cli test commands
- `references/built-plugins-index.md` was updated with a new entry

### Known Failure Modes to Watch
- Agent skips `version.py` generation (pre-existing habit from "optional" framing)
- Agent uses bulk download when API is available (pre-flip behavior)
- Agent generates `uploaders` (plural) instead of `uploader` for multi-file sources
- Agent omits `name`/`description` from `__metadata__`
- Agent hardcodes a version string in `version.py` instead of fetching dynamically
