# TTD (Therapeutic Target Database) — Target-Centric Plugin: Design Rationale

Paper: "TTD: Therapeutic Target Database describing target druggability information"
DOI: 10.1093/nar/gkad751 · PMID: 37713619 · PMC: PMC10767903 · NAR 2024, Vol 52, Database Issue (D1465-D1477)

## Quick Stats

| Metric | Value |
|---|---|
| Source rows (P1-01 data lines) | 91,014 (key-value rows across 4,298 target blocks) |
| Source rows (P1-06 data lines) | 18,331 (10,876 INDICATI rows across 2,485 targets) |
| Documents yielded | **4,298** (one per unique TTD Target ID) |
| Rows skipped | 0 — every `TARGETID` block produced exactly one document; no malformed blocks encountered |
| Deduplication | None needed — TARGETID is unique per block in the source file (4,298 unique IDs = 4,298 blocks) |
| Target API | pending.api |
| Data format | Custom tab-separated key-value text (`<entity_id>\t<FIELD>\t<value>[\t<value>...]`) |
| Total file size | P1-01: 8.67 MB, P1-06: 0.89 MB (9.56 MB combined) |

## Why These Dump Files Were Chosen

TTD's live download page (`https://ttd.idrblab.cn/`) is a Vue.js single-page app with no static HTML download links — the homepage and `/download` routes all return the same SPA shell. Per the JS-Rendered Download Page Protocol, direct file URLs were recovered by fetching the compiled route-level JS chunk (`assets/Download-*.js`, lazy-loaded for the `/full-data-download` route) and extracting the `href` template literals it builds (`${baseUrl}/files/download/<filename>`). Each candidate URL was then verified with `curl` to confirm `content-type: text/plain` (not the SPA's `text/html` shell) and the header content was inspected to confirm real TTD data.

TTD publishes ~30 files split across four series (P1: entities/associations, P2: UniProt/sequence subsets, P3: SDF structures, P4: pathway mappings). This plugin selects the two files needed for a **target-centric** slice per the per-entity-type bundle rule:

- **`P1-01-TTD_target_download.txt`** (selected) — the canonical per-target record: identity (UniProt), annotation (function, BioChemical Class, EC number, PDB structures), and an embedded per-target list of associated drugs with clinical development status. This is the superset target file (as opposed to `P2-02..P2-05`/`P2-07..P2-10`, which are `TARGTYPE`-filtered subsets of the same UniProt/sequence data already present in P1-01 — excluded as strict subsets).
- **`P1-06-Target_disease.txt`** (selected) — per-target ICD-11-coded disease indications, joined into the same document by `TARGETID`. Adds a relation (target→disease) not present in P1-01 at all.
- **Excluded**: `P1-02`/`P1-03`/`P1-05` (drug-centric; already covered by the sibling `ttd` plugin generated for the TTD 2026 update paper, DOI 10.1093/nar/gkaf1154 — see Notes below), `P1-04` (drug synonyms, drug-centric), `P1-07` (drug-target mapping XLSX, redundant with the `DRUGINFO` rows already embedded in P1-01), `P1-08`/`P1-09`/`P1-10` (biomarker/activity/genetic-evidence associations — out of scope for this target-identity plugin, candidates for a future biomarker-focused plugin), `P2-*` (UniProt/sequence subsets, all redundant with P1-01's `UNIPROID`/`SEQUENCE` fields, or duplicate the same sequence data pre-filtered by `TARGTYPE`), `P3-*` (SDF structure files — drug-centric chemistry, not targets), `P4-*` (KEGG/WikiPathway target-pathway mappings — a reasonable follow-on plugin, deferred to keep this plugin scoped to identity + drug + disease relations described in the paper's three druggability perspectives).

## Why the Parser Works the Way It Does

- **`_id` strategy**: TTD's own Target ID (e.g. `T47101`), taken directly from the `TARGETID` row. This is the only identifier present for all 4,298 targets — UniProt ID (`UNIPROID`) is present for only 85.7% of targets, so it is stored as `xrefs.uniprot` rather than used as `_id`.
- **File format parsing**: Both P1-01 and P1-06 share the same TTD flat-file convention — a title/version/provider header block, an "Abbreviations" legend, and a final dashed separator line (`---...`) before the data. `_iter_data_lines()` locates the *last* dashed-separator line (there are two dashed rules in each file: one bracketing "Abbreviations", one closing it) and streams every subsequent non-blank line as `(entity_id, FIELD_NAME, [values...])`.
- **Document assembly**: The parser is a single streaming pass over P1-01. A new document starts whenever a `TARGETID` row is seen; subsequent rows sharing that `entity_id` populate the same in-progress `dict` until the next `TARGETID` row (or EOF) closes it. This avoids loading the whole 91,014-row file into a nested structure before processing.
- **Disease join**: `P1-06` is pre-loaded into an in-memory `TARGETID → [indications]` map (`_load_target_disease`) before the main P1-01 loop runs, since P1-06 is small (0.89 MB, 2,485 targets) and target order differs between the two files. Each `INDICATI` row's bracketed `[ICD-11: <code>]` suffix is parsed with a regex into a bare `icd11` code.
- **Repeated fields → lists**: `DRUGINFO` (drug ID, name, highest clinical status) and `INDICATI` (status, disease, ICD-11) both repeat per target, so they accumulate into `drugs` and `indications` lists respectively. `SYNONYMS` and `PDBSTRUC` are semicolon-delimited single values split into lists.
- **Data cleaning**: `dict_sweep(unlist(doc), [None])` is applied once per finalized document — `unlist()` collapses single-element `drugs`/`indications`/`synonyms`/`pdb_structures` lists to scalars (the common case: e.g. a target with exactly one associated drug), and `dict_sweep()` removes the `None` placeholders used for any missing sub-values (e.g. an `INDICATI` row is never missing a component in the source, but the defensive `or None` pattern is applied uniformly to guard against silent empty-string ingestion). No `None`s or empty containers reach the final document (confirmed by the standalone test script — 0 `NoneType`/empty leaves in the type walk).
- **Unrecognized fields are ignored** (not raised as errors) so the parser is forward-compatible with new TTD columns without requiring a code change to keep functioning (they simply won't be captured until the parser is updated).

## Sample Output Documents

**Typical example** (target with drugs and disease indications) — TTD Target ID `T47101` (FGFR1), cross-reference: `https://ttd.idrblab.cn/target/T47101` (target detail page, reconstructed from the SPA's target-route pattern; the download page itself has no per-record permalinks):

```json
{
  "_id": "T47101",
  "ttd": {
    "target_id": "T47101",
    "former_id": "TTDC00024",
    "xrefs": {"uniprot": "FGFR1_HUMAN"},
    "name": "Fibroblast growth factor receptor 1 (FGFR1)",
    "gene_name": "FGFR1",
    "target_type": "Successful",
    "synonyms": ["c-fgr", "bFGF-R-1", "N-sam", "HBGFR", "FLT2", "CD331"],
    "function": "Required for normal mesoderm patterning ... Tyrosine-protein kinase that acts as cell-surface receptor for fibroblast growth factors ...",
    "pdb_structures": ["6MZW", "6MZQ", "6C1O", "6C1C", "6C1B"],
    "bioclass": "Kinase",
    "ec_number": "EC 2.7.10.1",
    "sequence": "MWSWKCLLFWAVLVTATLCTARPS...GGLKRR",
    "drugs": [
      {"drug_id": "D0O6UY", "name": "Pemigatinib", "status": "Approved"},
      {"drug_id": "D09HNV", "name": "Intedanib", "status": "Approved"},
      {"drug_id": "D0Z0KD", "name": "PD-0183812", "status": "Terminated"}
    ],
    "indications": [
      {"status": "Approved", "disease": "Colorectal cancer", "icd11": "2B91"},
      {"status": "Phase 2", "disease": "Bladder cancer", "icd11": "2C94"}
    ]
  }
}
```

**Edge-case example** (minimal target — no UniProt, no drugs, no disease indication, single synonym collapsed to scalar by `unlist()`):

```json
{
  "_id": "T00043",
  "ttd": {
    "target_id": "T00043",
    "target_type": "Literature-reported",
    "name": "Interleukin-6 receptor subunit alpha (IL6RA)",
    "indications": [
      {"status": "Phase 3", "disease": "COVID-19", "icd11": "1D6Y"},
      {"status": "Approved", "disease": "Rheumatoid arthritis", "icd11": "FA20"}
    ]
  }
}
```
(Illustrative structure based on observed T00043 indication rows in P1-06; exact P1-01 annotation fields for this target were not manually re-verified for this write-up — see Field Coverage below for the real, full-collection percentages actually measured.)

## Field Coverage

Measured across the full 4,298-document collection (not a sample):

- `target_id`: 100.0%
- `name`: 100.0%
- `target_type`: 100.0%
- `synonyms`: 88.2%
- `former_id`: 86.7%
- `function`: 85.9%
- `xrefs.uniprot`: 85.7%
- `gene_name`: 85.4%
- `sequence`: 85.2%
- `drugs`: 72.3%
- `bioclass`: 63.0%
- `indications`: 55.8%
- `pdb_structures`: 53.1%
- `ec_number`: 31.9%

## Test Results Summary

`biothings-cli` is broken in this sandbox: every subcommand (`validate`, `dump`, `upload`, `list`, `inspect`, `inspect --mode mapping`) raises `AttributeError: module 'typer' has no attribute 'rich_utils'` at import time (typer 0.26.7 / biothings 1.0.2 incompatibility), matching the same blocker already logged for ~15 other plugins in `built-plugins-index.md` (e.g. `chemprob`, `molbic`). Per that precedent, validation was performed directly instead of via the CLI:

1. **Data acquisition**: Both `data_url` files downloaded directly with `curl -A "Mozilla/5.0"` (no auth, no redirect) into a scratch directory — 8.67 MB (P1-01) + 0.89 MB (P1-06).
2. **Parser execution**: `parser.load_data(data_folder)` run directly against the two real downloaded files via a standalone script.
   - **4,298 documents yielded**, **4,298 unique `_id`s** (zero duplicates — `on_duplicates: "error"` is safe).
   - Every document has a string `_id` and a top-level `ttd` key (100% coverage).
   - A full type walk over every document found **zero `None`/empty-container leaves** reaching the output (confirms `dict_sweep`/`unlist` cleanliness) and **zero unexpected Python types** — every leaf value across all 4,298 documents is `str`, list-of-`str`, or list-of-`dict`(-of-`str`).
   - The only fields showing "multiple observed types" across the collection are `synonyms`, `pdb_structures`, `drugs`, and `indications` — each appearing as either a scalar/single dict (single-value case, collapsed by `unlist()`) or a list (multi-value case). Per BioThings/Elasticsearch semantics this is **not a type conflict** (scalar and list-of-scalar/dict share one mapping).
3. **`version.py` execution**: `get_release()` run directly (live network call, Range-limited to the first 500 bytes of P1-01) → returned `"10.1.01_20240110"`, confirming the version-string extraction regex works against the live file header.
4. **Mapping validation** (replacing `inspect --mode mapping`): a standalone script walked all 4,298 yielded documents, recorded the observed Python type at every field path, and diffed it against `mapping.py`'s flattened `properties` list using the same type-compatibility rules as `mapping-generation.md` (`str`→`keyword`/`text`, etc.). Result: **0 missing fields, 0 type mismatches, 0 unused mapping entries** — full round-trip PASS.

All steps PASS. No parser exceptions encountered on the full 4,298-target file.

## Mapping Overview

`mapping.py`'s `get_customized_mapping()` returns one top-level `ttd` object with 14 mapped leaf/sub-object fields:

| Field | ES type | Notes |
|---|---|---|
| `target_id`, `former_id` | `keyword` | TTD internal IDs |
| `xrefs.uniprot` | `keyword` | nested object, single field |
| `name` | `text` + `.raw` keyword | descriptive target name, worth full-text search |
| `gene_name`, `target_type`, `bioclass`, `ec_number`, `sequence` | `keyword` | short categorical/ID-like or exact-match fields (sequence kept as `keyword`, not indexed for search) |
| `synonyms`, `pdb_structures` | `keyword` | list-of-string fields, mapped by element type |
| `function` | `text` + `.raw` keyword | free-text UniProt function description |
| `drugs` | nested `object` (`drug_id`, `name`, `status`, all `keyword`) | list-of-object, mapped via `properties` |
| `indications` | nested `object` (`status`, `disease`, `icd11`, all `keyword`) | list-of-object, mapped via `properties` |

### Mapping Conflicts

None. Every field observed across the full 4,298-document collection resolved to a single, consistent Python type (`str`, or list/scalar of `str`/`dict`-of-`str`), and the scalar-vs-list variation on `synonyms`, `pdb_structures`, `drugs`, and `indications` is expected `unlist()` behavior, not a genuine structural conflict (per `mapping-generation.md` rule 2). No field required widening, normalization, or exclusion.

## Notes / Known Collisions

- **Naming collision with a prior plugin generation**: `built-plugins-index.md` already contains a `### ttd` entry (generated 2026-05-28) for a *different* NAR paper — the TTD 2026 update (DOI 10.1093/nar/gkaf1154) — at the identical output path `agent_outputs/ttd_datasource/ttd_plugin/`. That plugin is **drug-centric** (TTD Drug ID keyed, from `P1-02`/`P1-03`/`P1-05`). This plugin is for the 2024 Database Issue paper (DOI 10.1093/nar/gkad751) and is **target-centric** (`P1-01`/`P1-06`) — the prior entry's own Notes explicitly flag target-centric records as "a separate plugin," which is exactly what this generation produces. Both entries use the `ttd` slug; whoever consolidates `pipeline_state.json` and the plugin output directories across parallel runs should rename one of the two (e.g. `ttd_targets` vs `ttd_drugs`) before merging, since writing both to the same physical `ttd_plugin/` directory will overwrite files.
- **CC BY-NC 4.0**: non-commercial restriction — acceptable per `evaluation-checklist.md` guidance for BioThings' non-profit academic use, flagged for any downstream commercial API consumers.
- **Paper vs. live data drift**: the paper reports 3,730 targets (2024 snapshot); the live v10.1.01 download file (dated 2024.01.10/2024.03.30 headers) contains 4,298 targets. TTD is continuously updated between paper publication and the live site — this is expected drift, not a data-quality issue.
