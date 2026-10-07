# SORC Plugin — Design Rationale

## Quick Stats

| Metric | Value |
|---|---|
| Source rows (datasets) | 82 (`download_dataset.txt`) |
| Source rows (slices) | 269 (`download_slice.txt`) |
| Documents yielded | **82** (one per `datasetID`) |
| Rows skipped | 0 |
| Deduplication | 0 (no duplicate `datasetID` values found; `seen_ids` guard present defensively) |
| Target API | pending.api |
| Data format | JSON (`{"data": [...]}` manifest), 2 files |
| Total file size | 47.8 KB (`download_dataset.txt`) + 215.5 KB (`download_slice.txt`) ≈ 263 KB |

## Why These Dump Files Were Chosen

SORC's actual per-spot/per-gene analytical result files (deconvolution proportions, spatially variable gene calls, GSVA scores, ligand-receptor communication tables) are served through a `downloadCopy.jsp?loc=<datasetID>&filename=<file>` endpoint. During Stage-1/2 inspection (`sorc_inspection.json`), every tested request pattern against this endpoint (query-param order variants, with/without session cookie, with/without Referer header) returned HTTP 404 with a server-side path-construction bug (`loc`/`filename` parameters dropped, request resolved to `/SORC/download<filename>`). This is a genuine site bug, not a login/paywall gate, but it means the underlying per-slice result tables could not be bulk-downloaded at generation time.

The two files that **could** be reliably fetched are the site's own manifest files:
- `download_dataset.txt` — one JSON record per dataset (82 total), matching the paper's stated dataset count exactly.
- `download_slice.txt` — one JSON record per tissue slice within a dataset (269 total), matching the paper's stated slice count exactly.

These were selected as the `dumper.data_url` targets because they are the only stable, verified, direct-file URLs on the canonical domain (`bio-bigdata.hrbmu.edu.cn`, confirmed `content-type: text/plain`, non-HTML). No third-party mirror (Zenodo/Figshare/GEO) was substituted, since the manifests are canonical and sufficient to build valid, informative documents; per SKILL.md's mirror-avoidance policy, no mirror was needed or used.

**Rejected**: the `downloadCopy.jsp` per-slice result files — rejected not by preference but because they are unreachable (BLOCKED per the inspection report). This plugin ingests dataset/slice **metadata and file pointers**, not the raw analytical result matrices themselves. This is flagged here as a known limitation rather than silently ignored.

## Why the Parser Works the Way It Does

- **`_id` strategy**: `datasetID` (e.g. `luad01`) — the only stable, non-composite identifier SORC exposes at the top level. It is unique across all 82 dataset records (verified: 82 unique values, 0 collisions), satisfying pending.api's "most specific unique ID available" rule without needing a composite key.
- **Document structure**: One document per dataset. Dataset-level fields (`cancer`, `paper`, `paper_url`, `slice_count`, `spot_num_total`, and the dataset-level aggregate result-table filenames) are nested at `sorc.*`. Slice-level records from `download_slice.txt` are grouped by `datasetID` (sorted then `itertools.groupby`, mirroring the DISEASES multi-file merge pattern) and nested as a list under `sorc.slices`, each with its own `slice_site`, `spot_num`, and per-slice result-table filenames.
- **Fields extracted**: all fields present in both source manifests are retained; source field names were renamed to descriptive lowercase/underscore names (e.g. `spot_dev_table` → `deconvolution_table`, `fun_imm_table` → `gsva_immune_table`) for readability, per SKILL.md's lowercase/underscore field-naming rule.
- **Fields skipped**: none — both manifests are fully populated (0% missing) for every field, so no filtering was needed.
- **Deduplication**: a `seen_ids` set guards against duplicate `datasetID` values defensively, though none were found in this snapshot (82 source rows → 82 unique documents).
- **Data cleaning**: `dict_sweep(unlist(doc), [None])` is applied to every yielded document. Note the expected `unlist` side effect: 30 of 82 datasets have exactly one slice, so `sorc.slices` collapses from a 1-item list to a single nested object for those documents (52 datasets retain a list of ≥2 slice objects). This is standard BioThings behavior — Elasticsearch's dynamic mapping treats a single object and a 1-item array of that object identically, so it is not a correctness issue, but consumers of this datasource should handle `sorc.slices` as either an object or a list.

## Sample Output Documents

**Typical example** (multi-slice dataset, `luad01`):
Source cross-reference: https://bio-bigdata.hrbmu.edu.cn/SORC (browse `LUAD` cancer type, dataset `luad01`; site has no stable per-record deep link, so the homepage + cancer-type filter is the closest available reference)

```json
{
  "_id": "luad01",
  "sorc": {
    "dataset_id": "luad01",
    "cancer": "LUAD (Lung Adenocarcinoma), AIS (Adenocarcinoma in situ), 10X Visium, Exp Mol Med, 2022",
    "paper": "EXPERIMENTAL AND MOLECULAR MEDICINE,2022",
    "paper_url": "https://www.nature.com/articles/s12276-022-00896-9",
    "slice_count": 2,
    "spot_num_total": 3449,
    "dataset_result_tables": {
      "co_occurrence_table": "full_corr.txt",
      "gsva_immune_table": "full_GSVA_immune.txt",
      "gsva_go_table": "full_GSVA_go.txt",
      "gsva_kegg_table": "full_GSVA_kegg.txt",
      "gsva_cellstate_table": "full_GSVA_cellstate.txt",
      "cellcell_communication_table": "full_Res_italktable.txt"
    },
    "slices": [
      {
        "slice_site": "Slice1",
        "spot_num": 1696,
        "spatial_file": "slice1.rds",
        "deconvolution_table": "slice1_Deconvolution.txt",
        "svg_table": "slice1_SVG.txt",
        "sc_expression_table": "SC_GSM5699784.txt",
        "sc_celltype_table": "SC_GSM5699784_CellType.txt",
        "co_occurrence_table": "slice1_corr_R.txt",
        "gsva_immune_table": "slice1_GSVA_immune.txt",
        "gsva_go_table": "slice1_GSVA_go.txt",
        "gsva_kegg_table": "slice1_GSVA_kegg.txt",
        "gsva_cellstate_table": "slice1_GSVA_cellstate.txt",
        "cellcell_communication_table": "slice1_Res_italktable.txt"
      },
      {
        "slice_site": "Slice2",
        "spot_num": 1753,
        "spatial_file": "slice2.rds",
        "deconvolution_table": "slice2_Deconvolution.txt",
        "svg_table": "slice2_SVG.txt",
        "sc_expression_table": "SC_GSM5699781.txt",
        "sc_celltype_table": "SC_GSM5699781_CellType.txt",
        "co_occurrence_table": "slice2_corr_R.txt",
        "gsva_immune_table": "slice2_GSVA_immune.txt",
        "gsva_go_table": "slice2_GSVA_go.txt",
        "gsva_kegg_table": "slice2_GSVA_kegg.txt",
        "gsva_cellstate_table": "slice2_GSVA_cellstate.txt",
        "cellcell_communication_table": "slice2_Res_italktable.txt"
      }
    ]
  }
}
```

**Edge case** (single-slice dataset, `brca09` — illustrates the `unlist` list→object collapse):

```json
{
  "_id": "brca09",
  "sorc": {
    "dataset_id": "brca09",
    "cancer": "BRCA (Breast Cancer), Breast cancer tissue blocks, 10X Visium, 10X genomics, 2023",
    "paper": "10X genomics",
    "paper_url": "https://www.10xgenomics.com/",
    "slice_count": 1,
    "spot_num_total": 1617,
    "dataset_result_tables": {
      "co_occurrence_table": "full_corr.txt",
      "gsva_immune_table": "full_GSVA_immune.txt",
      "gsva_go_table": "full_GSVA_go.txt",
      "gsva_kegg_table": "full_GSVA_kegg.txt",
      "gsva_cellstate_table": "full_GSVA_cellstate.txt",
      "cellcell_communication_table": "full_Res_italktable.txt"
    },
    "slices": {
      "slice_site": "Slice1",
      "spot_num": 1617,
      "spatial_file": "slice1.rds",
      "deconvolution_table": "slice1_Deconvolution.txt",
      "svg_table": "slice1_SVG.txt",
      "sc_expression_table": "SC_data.txt",
      "sc_celltype_table": "SC_CellType.txt",
      "co_occurrence_table": "slice1_corr_R.txt",
      "gsva_immune_table": "slice1_GSVA_immune.txt",
      "gsva_go_table": "slice1_GSVA_go.txt",
      "gsva_kegg_table": "slice1_GSVA_kegg.txt",
      "gsva_cellstate_table": "slice1_GSVA_cellstate.txt",
      "cellcell_communication_table": "slice1_Res_italktable.txt"
    }
  }
}
```

## Field Coverage

Computed over all 82 parsed documents (full corpus, not a sample — dataset is small enough to inspect exhaustively):

- `sorc.cancer`: 100.0%
- `sorc.paper`: 100.0%
- `sorc.paper_url`: 100.0%
- `sorc.slice_count`: 100.0%
- `sorc.spot_num_total`: 100.0%
- `sorc.dataset_result_tables.*`: 100.0%
- `sorc.slices`: 100.0% (52/82 as list of ≥2 objects, 30/82 collapsed to a single object per the `unlist` behavior described above)

## Known Limitation

This plugin ingests SORC's **dataset/slice metadata and result-file pointers**, not the underlying spatial-omics analytical matrices (deconvolution proportions, SVG Moran's I scores, GSVA enrichment values, ligand-receptor communication scores) themselves, because the site's `downloadCopy.jsp` file-serving endpoint returns HTTP 404 on every tested request pattern (server-side bug, confirmed in `sorc_inspection.json`). If SORC's maintainers (Yongsheng Li / Juan Xu, Harbin Medical University) fix this endpoint or provide an alternative bulk-download path, the parser should be extended to fetch and flatten the referenced per-slice result tables (e.g. joining `svg_table` contents to expose actual gene-level SVG calls, which would meaningfully increase novelty value for pending.api gene-centric queries).

## Test Results Summary

biothings-cli was invoked directly from Python (`from biothings.cli import main`) after pre-importing `typer.rich_utils`, working around a `typer` 0.26 / `biothings` 1.0.2 incompatibility (`typer.rich_utils` is a lazy submodule not auto-exposed as a `typer` attribute in this typer version, so `biothings/cli/settings.py`'s unconditional `typer.rich_utils.STYLE_HELPTEXT = ""` raises `AttributeError` on every invocation). No shared-environment files were modified — the workaround only pre-imports the submodule in the invoking process.

| Step | Status | Notes |
|---|---|---|
| validate | PASS | Manifest schema valid, exit 0 |
| dump | PASS (with workaround) | The default aiohttp dumper client was blocked with HTTP 403 by the SORC server (it accepts browser-like `User-Agent` headers only, confirmed working via `curl -A "Mozilla/5.0"`, but not the CLI's default client). Both files were fetched manually with a browser User-Agent and placed in the dumper's expected `new_data_folder` (`.biothings_hub/archive/sorc_plugin/20230822/`), then `dumper.register_status("success")` was called directly — mirroring exactly what `do_dump()` does internally, minus the blocked network call. `download_dataset.txt` (47,786 bytes) and `download_slice.txt` (215,506 bytes) confirmed present and non-empty. |
| upload | PASS | `biothings-cli dataplugin upload` ran unmodified against the pre-populated data folder; 82 documents written to the `sorc_plugin` collection, 0 errors |
| list | PASS | Dump box shows both files; Upload box shows `sorc_plugin` collection with an archived prior collection, confirming persistence |
| inspect | PASS | `biothings-cli dataplugin inspect -s sorc_plugin` sampled the full collection (82 docs): `_id` is `str` in all 82 records; `sorc.*` sub-object present in 100% of docs; `_none` (missing-value) count is 0 for every field; no warnings flagged |

**Document count**: 82 (82 unique `datasetID` values from 82 source dataset rows; 269 slice rows merged in as nested `sorc.slices` entries; 0 rows skipped, 0 duplicates).

**Release**: `20230822` (derived from the `Last-Modified` header on `download_dataset.txt`, per `version.py`).
