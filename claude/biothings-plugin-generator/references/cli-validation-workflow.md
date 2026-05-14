# biothings-cli Validation Workflow

Complete step-by-step instructions for validating a generated BioThings plugin using biothings-cli. Load this file during §7 of the plugin generator SKILL.md.

---

## Prerequisites
```bash
pip install "biothings[cli]"
biothings-cli --version          # confirm install; capture this for parser_report.json
cd agent_outputs/<datasource_name>_datasource/<datasource_name>_plugin/
```
The CLI uses a local SQLite-backed `data_src_database` and an `archive/` folder under `.biothings_hub/` inside the plugin directory — no external services needed.

**Git repository setup (required).** `biothings-cli` internally calls `git rev-list` and `git remote` to detect plugin identity and version. These calls fail silently or fatally if the plugin directory is not a proper git repo. **Always run the following before any CLI command:**
```bash
# Skip if the plugin directory already has commits on the current branch
git init                           # no-op if .git/ already exists
git add manifest.json parser.py version.py
git commit -m "Initial plugin files"  --allow-empty
git remote add origin /dev/null 2>/dev/null || true   # dummy origin; no push needed
```
- `git init` + initial commit: satisfies `git rev-list -1 <branch>` which biothings-cli runs during upload.
- Dummy `origin` remote: satisfies `git remote` lookups. Points to `/dev/null` — nothing is ever pushed.
- These are local-only operations. No GitHub repo or remote push is required.

**Clean hub state (required on re-runs).** If `.biothings_hub/` exists from a previous run (especially a failed one), stale SQLite locks or cached "canceled" status will cause new uploads to fail. **Always clean before re-running the pipeline:**
```bash
# Safe to run even on first run (files won't exist yet)
rm -f .biothings_hub/data_src_database .biothings_hub/data_src_database-journal .biothings_hub/biothings_hubdb
```
- `data_src_database-journal`: SQLite WAL/journal lock left by an interrupted upload.
- `data_src_database`: the collection store; must be recreated after removing the journal.
- `biothings_hubdb`: hub metadata that caches "stale" / "canceled" status from prior failures.
- Archive data files (`.biothings_hub/archive/`) are safe to keep — only metadata/DB files need clearing.

---

## Step 1: `dataplugin validate` — manifest schema check
```bash
biothings-cli dataplugin validate
```
- **Purpose**: lints `manifest.json` against the BioThings manifest schema. Catches missing `__metadata__`, malformed `data_url`, missing `release` wiring, parser-reference typos.
- **Pass criterion**: exit code 0; no "ERROR" or "FAIL" lines in stdout/stderr.
- **Common failures**: `parser` reference points at a function that doesn't exist in `parser.py`; `data_url` is not a string or list of strings; `__metadata__.url` missing.
- **On failure**: record the validation errors and stop — do not run `dump`.

## Step 2: `dataplugin dump` — download data + exercise version.py
```bash
biothings-cli dataplugin dump
```
- **Purpose**: invokes `version.py:get_release()` to detect the current release, then downloads every URL in `dumper.data_url` into `.biothings_hub/archive/<plugin>/<release_string>/`.
- **Pass criterion**: exit code 0; archive folder exists; every declared `data_url` file is present and non-empty.
- **Common failures**: version.py returns `None` (Hub falls back to a date string but logs a warning); HTTP 4xx/5xx on a `data_url`; `uncompress: true` fails because the file isn't a zip.
- **On failure**: capture the offending URL + HTTP status. If a single URL in a list fails, the whole dump fails — fix the URL or remove it from the manifest before retrying.

## Step 3: `dataplugin upload` — run the parser, write to local DB
```bash
biothings-cli dataplugin upload
```
- **Purpose**: runs `parser.load_data(data_folder)` against the dumped files and writes yielded documents into the SQLite collection `<plugin_name>` under `data_src_database`.
- **Pass criterion**: exit code 0; final log line shows non-zero document count; collection appears in subsequent `list` output.
- **Common failures**: parser raises (caught and logged — always check stderr even on exit 0); zero documents yielded (silent failure mode); duplicate `_id` errors when `on_duplicates: error`; document exceeds Hub size limits.
- **On failure**: record the parser exception (if any) and the final document count. **A successful exit with `documents_yielded == 0` is treated as FAILURE** — flag the silent-zero-doc condition.

## Step 4: `dataplugin list` — verify accumulated state
```bash
biothings-cli dataplugin list
```
- **Purpose**: prints two boxed sections — `Dump` (source + data folder + file list) and `Upload` (database path + collection name + archived collections + temporary collections). No mutations; pure inspection.
- **Pass criterion**: both `Dump` and `Upload` boxes are populated; `Collections` line lists `<plugin_name>`; data folder shows the expected files.
- **Common findings**: archived collections accumulate across re-runs (named `<plugin>_archive_<YYYYMMDD>_<token>`) — not a failure, but worth pruning periodically.
- **On failure**: if `Collections` is empty after a successful upload, the upload silently dropped all docs — investigate via `inspect`.

## Step 5: `dataplugin inspect` — sample document shape verification
```bash
# Basic form — use -s when prompted (required when multiple uploaders/collections exist)
biothings-cli dataplugin inspect -s <plugin_name>

# For large datasets (>100K docs): limit the sample to avoid long waits
biothings-cli dataplugin inspect -s <plugin_name> --limit 1000
```
- **Purpose**: pulls a sample of yielded documents from the collection and reports field-level statistics (key presence, type distribution, value ranges) to verify the parser's output schema matches expectations.
- **Pass criterion**: every yielded document has an `_id` of type `string`; the top-level datasource key (e.g. `harmonizome`, `signor`, `ecbd`) is present in 100% of sampled documents; no fields are unexpectedly all-null.
- **`-s` flag**: always provide `-s <plugin_name>`. The CLI requires it when multiple uploaders exist and errors with `--sub-source-name must be provided` without it. Safe to always include.
- **`--limit` flag for large datasets**: for collections with >100K documents, a full inspection is slow and unnecessary for schema validation. Use `--limit 1000` to `--limit 10000` for initial verification.
- **Common findings**: stray `None` values not cleaned by `dict_sweep`; `_id` mistakenly stored as integer instead of string; nested dicts with a single key (should have been flattened by `unlist`).

---

## Optional: Re-run Cycle / Cleanup
Between iterations during plugin development:
```bash
# Discard archived collections to keep the local DB tidy
rm -rf .biothings_hub/archive/<plugin_name>/<old_release_string>/
# Re-run dump+upload after parser changes
biothings-cli dataplugin dump && biothings-cli dataplugin upload
```

## Recording Results in parser_report.json
When the user opted into the report per §6b, populate `smoke_test.cli_validation` with one entry per command above. Status values:
- `passed`: command exited 0 AND its specific pass criterion was met
- `failed`: command exited non-zero, OR exited 0 but its pass criterion failed (e.g. zero documents on `upload`)
- `skipped`: command was not run (typically because an earlier step failed and the workflow halted)

The `cli_validation` block lives inside `smoke_test`; the overall `smoke_test.status` should be `passed` only when all five CLI steps pass. Any failed step bubbles up to `smoke_test.status: "failed"`.
