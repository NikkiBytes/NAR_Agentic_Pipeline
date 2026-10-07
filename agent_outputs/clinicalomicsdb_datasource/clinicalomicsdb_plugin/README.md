# ClinicalOmicsDB — Design Rationale

## Quick Stats
| Metric | Value |
|---|---|
| Source records (treatment-arm files) | 64 |
| Source gene-level rows (all files, summed) | 998,257 |
| Documents yielded | 64 (one per treatment arm; gene stats nested per doc) |
| Rows skipped | 0 (all 64 fetched files parsed successfully) |
| Deduplication | None needed — all 64 `study_id` values unique |
| Target API | pending.api |
| Data format | JSON (per-study bulk download via 64 concrete API URLs) |
| Total downloaded size | ~115 MB (64 files, avg ~1.8 MB each) |
| Avg gene-stat rows per document | 15,598 (min 5,110, max 20,324) |

## Why These Dump Files Were Chosen
ClinicalOmicsDB (trials.linkedomics.org) exposes its data exclusively through a
REST API (no static bulk-download page). The verified inspection
(`clinicalomicsdb_inspection.json`) identified three relevant endpoints:
`POST filter/` (study discovery), `GET info/{study}` (per-study clinical
metadata), and `GET table/study/gene/{study}` (per-study gene-level
significance statistics).

**Endpoint selection for `dumper.data_url`:** Only `table/study/gene/{study}`
was used for the manifest's bulk download list, for two reasons:

1. **It carries the datasource's most novel data.** The relevancy report
   (novelty score 3/5) specifically calls out "per-clinical-trial per-gene
   transcriptomic drug-response association statistics (AUROC/p-value/FDR)"
   as the data type not itemized in any core BioThings API. That table is
   exactly what this endpoint returns.
2. **Avoiding a filename collision.** The BioThings Hub's `HTTPDumper` names
   each downloaded file using `os.path.basename(url)`. Because both
   `info/{study}` and `table/study/gene/{study}` end in the same terminal
   path segment (e.g. `.../GSE14764.csv`), declaring both endpoint families
   in the same `data_url` list would silently overwrite one file with the
   other in the shared `data_folder`. Rather than work around this with
   query-string suffixes (fragile and undocumented), only one endpoint
   family was declared as the live bulk download.

**Study identifiers were resolved by hand, once, ahead of time** (not
re-derived from the paper): `POST filter/` requires a non-empty `drugs`
array (an empty array/`"cancers":[]` combination returns zero results
despite the OpenAPI spec's wording suggesting "empty = all"). ~40 drug names
mentioned in the ClinicalOmicsDB paper and R package documentation were
queried against `filter/` and the resulting `study_list` values were
unioned, yielding 64 of the paper's reported 67 treatment arms (40 studies).
The remaining 3 treatment-arm files were not discoverable through the drug
names tried and are omitted; this is a completeness gap flagged below, not a
license or access blocker (both the `filter/` and `table/study/gene/{study}`
endpoints are public, unauthenticated, and directly curl-able).

**Rejected:** `POST filter/` itself (POST-only, no simple GET data_url is
possible, and manifest bulk-download does not support POST bodies) and the
per-study raw expression CSVs on Box.com (`download_url` in `info/{study}`)
— those are per-patient expression matrices, dynamically issued third-party
static links (flagged as a link-stability risk in the inspection report),
and not needed for the gene-level significance-statistics use case this
plugin targets.

**Study-level clinical metadata** (disease, treatment, sample sizes, NCT ID,
PubMed ID, GEO series, Box.com `download_url`) is bundled as a static
reference file, `study_metadata.json`, shipped in the plugin directory
alongside `parser.py` — analogous to how the `disgenet` production plugin
bundles a static `mondo.json` ontology file for ID resolution (see
`references/production-plugin-examples.md`, Pattern 2). This file was built
once via `GET info/{study}` for the same 64 study identifiers used in
`manifest.json`, keeping the parser's runtime fully offline/deterministic and
avoiding a second live-network dependency at parse time. Fields flagged
`REDUNDANT` in the inspection report (`platform`, `normalization_method`,
`study_abstract`, `raw_data_availability`) were dropped from the bundled
file.

## Why the Parser Works the Way It Does
- **`_id` strategy**: `study_id`, the treatment-arm filename stem (e.g.
  `GSE14764`, `GSE194040_Paclitaxel_Trastuzumab`). The inspection report's
  primary key was `study_id (composite with analyte/gene for association
  rows)`. Because this parser nests the full per-gene table inside each
  study document (see below) rather than exploding one document per
  gene-study pair, the composite half of that key (the gene/analyte) is not
  needed in `_id` — it lives as the `gene` field inside each entry of the
  nested `gene_stats` list. This keeps the collection at a manageable 64
  documents (one per real-world treatment arm) instead of ~1M
  single-gene-association documents, while still preserving every row of
  the original per-gene table.
- **Document structure**: one document per treatment arm, `clinicalomicsdb`
  key holding `study_id`, `geo_series`, `disease`, `subtype`, `adjuvant`
  (bool), `treatment` (list, split on comma), `response_eval`,
  `sample_size`/`responder_size`/`non_responder_size` (ints), `download_url`
  (Box.com raw-expression-CSV link, kept as an informational xref — not
  fetched by this plugin), `xrefs` (`geo`, `clinicaltrials_gov`, `pubmed`),
  and `gene_stats` — a list of `{gene, p_value, auroc, fdr, sorted_p,
  sorted_fdr}` records, one per gene tested in that arm's responder vs.
  non-responder comparison.
- **Fields skipped**: `platform`, `normalization_method`, `study_abstract`
  (all flagged `REDUNDANT` in the inspection schema) and the raw per-patient
  expression matrix (not part of the API's gene-stats table).
- **Data cleaning**: `_to_bool`/`_to_int`/`_to_float` coerce the API's
  string-typed fields (`"True"`, `"76"`, etc.) to native JSON/Python types.
  `dict_sweep(unlist(doc), [None, "", []])` removes empty/null fields and
  flattens any accidental single-item lists (note: single-drug `treatment`
  lists collapse to a bare string via `unlist()` — this is expected SDK
  behavior, not a bug).
- **`p_value` / `fdr` sign note**: the API returns these as signed values
  (e.g. `-0.3721`), not the raw `[0,1]` p-values one might expect — this was
  confirmed to be the literal value returned by
  `table/study/gene/{study}` (verified directly via curl against the live
  endpoint, not a parsing artifact) and is preserved as-is; likely a signed
  or directional transform of the underlying statistic used internally by
  ClinicalOmicsDB's differential-analysis pipeline.
- **Deduplication**: a `seen_ids` set guards against a duplicate `study_id`
  appearing twice in `data_folder` (not observed in practice — all 64 IDs
  are unique).

## Sample Output Documents

**Typical document** (abridged — `gene_stats` truncated from 15,032 entries
to 2 for readability):
```json
{
  "_id": "Choueiri_CCR_2016",
  "clinicalomicsdb": {
    "study_id": "Choueiri_CCR_2016",
    "geo_series": "Choueiri_CCR_2016",
    "disease": "Kidney",
    "adjuvant": true,
    "treatment": "nivolumab",
    "response_eval": "clinical",
    "sample_size": 16,
    "responder_size": 8,
    "non_responder_size": 8,
    "download_url": "https://bcm.box.com/shared/static/3zdglbi6o8x3i73oifbbuscq082n814a.csv",
    "xrefs": {
      "geo": "Choueiri_CCR_2016",
      "clinicaltrials_gov": "NCT01358721",
      "pubmed": "27169994"
    },
    "gene_stats": [
      {"gene": "5_8S_rRNA", "p_value": -0.3721, "auroc": 0.359, "fdr": -0.9235, "sorted_p": -0.4294, "sorted_fdr": -0.0346},
      {"gene": "A1BG", "p_value": -0.8749, "auroc": 0.531, "fdr": -0.9898, "sorted_p": -0.0581, "sorted_fdr": -0.0045}
    ]
  }
}
```
Source cross-reference: https://trials.linkedomics.org/api/info/Choueiri_CCR_2016.csv
(no per-record browse page exists on the site; the API endpoint itself is
the canonical reference).

**Edge case — no `clinical_trial_id`** (11/64 arms have no registered NCT
number, e.g. `GSE14764`):
```json
{
  "_id": "GSE14764",
  "clinicalomicsdb": {
    "study_id": "GSE14764",
    "geo_series": "GSE14764",
    "disease": "Ovarian",
    "adjuvant": false,
    "treatment": ["paclitaxel", "carboplatin"],
    "response_eval": "pathologic",
    "sample_size": 76,
    "responder_size": 26,
    "non_responder_size": 50,
    "download_url": "https://bcm.box.com/shared/static/2h4cxsj67cv2pu8awa6id85200yhrwgl.csv",
    "xrefs": {
      "geo": "GSE14764",
      "pubmed": "19294737"
    },
    "gene_stats": ["... 12,257 entries omitted ..."]
  }
}
```
Source cross-reference: https://trials.linkedomics.org/api/info/GSE14764.csv

## Field Coverage
(from a full parse of all 64 fetched documents — no sampling needed at this scale)
- `clinicalomicsdb.xrefs.pubmed`: 100.0%
- `clinicalomicsdb.download_url`: 100.0%
- `clinicalomicsdb.treatment`: 100.0%
- `clinicalomicsdb.adjuvant`: 100.0%
- `clinicalomicsdb.xrefs.clinicaltrials_gov`: 82.8%
- `clinicalomicsdb.subtype`: 60.9%

## Test Results Summary
`biothings-cli` in this sandbox is broken independent of this plugin:
`biothings-cli dataplugin validate` (and every other subcommand) fails
immediately with:
```
AttributeError: module 'typer' has no attribute 'rich_utils'
```
This is a version incompatibility between the installed `biothings` (1.0.2)
CLI's `cli/settings.py` (which references `typer.rich_utils`) and the
installed `typer` (0.26.7), which no longer exposes that submodule. This is
an environment issue, not a defect in this plugin — the same failure occurs
for every other already-generated plugin in this repo (confirmed against
`gto_plugin`, which has a prior *passing* `.biothings_hub` archive from a
session where the CLI worked). Per the task instructions, the shared
environment was not patched.

**Fallback validation performed instead** (direct `parser.py` execution
against real downloaded source data, bypassing the broken CLI wrapper):
1. Downloaded all 64 `data_url` files from `manifest.json` via `curl`
   (~115 MB total) into a scratch `data_folder`.
2. Imported `parser.py` directly and ran `load_data(data_folder)` to
   completion.
3. Result: **64/64 documents yielded**, all with unique string `_id`s, all
   containing the `clinicalomicsdb` top-level key, 998,257 total gene-stat
   rows preserved across all documents, zero exceptions, zero silently
   dropped/zero-doc failure mode.
4. Verified `manifest.json` is syntactically valid JSON and its 64
   `data_url` entries match the 64 files fetched.

| Step | Result |
|---|---|
| validate (CLI) | BLOCKED — CLI environment broken (typer/biothings incompatibility) |
| dump (CLI) | BLOCKED — same |
| upload (CLI) | BLOCKED — same |
| list (CLI) | BLOCKED — same |
| inspect (CLI) | BLOCKED — same |
| Fallback: direct `parser.py` run against real downloaded data | **PASS** — 64/64 docs, 0 errors |

## Known Limitations / Risks
- Only 64 of the paper's reported 67 treatment arms (40 studies) were
  recoverable through the `filter/` endpoint using the drug-name list tried
  during this session; the remaining 3 arms were not found and are not
  included. If ClinicalOmicsDB maintainers publish a full study-ID list (or
  the R package `clinicalomicsdbr` bundles one), the `manifest.json`
  `data_url` list and `study_metadata.json` should be regenerated to close
  this gap.
- `study_metadata.json` is a static snapshot (not re-fetched on schedule).
  If ClinicalOmicsDB adds/renames studies, this file needs manual
  regeneration alongside the `data_url` list.
- License is CC BY-NC 4.0 (non-commercial) — acceptable for Su Lab academic
  use per project policy, but a consideration for any downstream commercial
  Translator consumers.
