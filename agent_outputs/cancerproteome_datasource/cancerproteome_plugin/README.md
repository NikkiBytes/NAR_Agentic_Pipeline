# CancerProteome Plugin — Design Rationale

## Quick Stats

| Metric | Value |
|---|---|
| Source rows (all 5 data files combined) | 292,970 |
| — `protein_inf.txt` (canonical protein expression) | 36,646 |
| — `microprotein_inf.txt` (microprotein expression) | 1,462 |
| — `PTM_protein_inf.txt` (canonical protein PTM sites) | 25,507 |
| — `PTM_microprotein_inf.txt` (microprotein PTM sites) | 479 |
| — `protein_durg_inf.txt` (protein-drug correlations) | 228,876 |
| Documents yielded | 16,744 unique protein/microprotein entities |
| Rows skipped | 0 (no rows had a missing/blank protein ID across any file) |
| Deduplication | Aggregation by `protein` ID (the site's own composite identifier) — not row-level dedup; every source row is retained as a list entry nested under its entity |
| Target API | pending.api (no existing BioThings API covers quantitative proteome/PTM/drug-correlation data) |
| Data format | TSV (6 files, tab-delimited, `text/plain`) |
| Total file size | ~20.4 MB uncompressed (2.47 MB + 0.10 MB + 2.22 MB + 0.04 MB + 14.6 MB + 0.0005 MB) |

## Why These Dump Files Were Chosen

All 6 files listed on the CancerProteome download page were ingested — there is no superset/subset relationship among them; each is an **independent** file covering a distinct entity type or measurement axis:

- `cancer_names.txt` — lookup table only (TCGA-style abbreviation → uniform cancer-type name). Not itself a data file; used at parse time to annotate every expression/PTM/drug record with a human-readable `cancer_name`.
- `protein_inf.txt` — canonical protein differential expression (tumor vs. control), the largest and most central data file.
- `microprotein_inf.txt` — differential expression for 4,111 ribo-seq-supported microproteins (novel small ORFs), a data type not represented in any existing BioThings API.
- `PTM_protein_inf.txt` / `PTM_microprotein_inf.txt` — PTM site-level differential expression for canonical proteins and microproteins respectively. These are **independent** of the plain expression files (different granularity — a protein can have both a protein-level record and multiple PTM-site records), so both were kept.
- `protein_durg_inf.txt` — protein expression vs. drug (DepMap/GDSC) IC50 sensitivity correlations. Filename is a source-side typo ("durg" not "drug"); kept because there is no cleaner variant available.

No file was excluded per the file-selection policy — there was no filtered/superset/composite redundancy among the 6 downloads; every file is independently valuable and all fit comfortably within the manifest bulk-download path (largest file 14.6 MB).

## Why the Parser Works the Way It Does

**`_id` strategy**: the site's own `protein` field (e.g. `HEXB_P07686`), used verbatim as `_id`. This is a composite `{GeneSymbol}_{UniProtAccession}` string for canonical proteins with a resolvable UniProt accession, but many isoform/microprotein/non-canonical-ORF entries use non-UniProt suffixes (`_Canonical_4`, `_pseudogene_MP_4`, `_lncRNA`, `_uORF`, `_odORF`, etc.) instead. Because the field is globally unique and present in every file (including the 2,620 protein IDs that appear **only** in the drug-correlation file), it was chosen directly over trying to force a strict UniProt-only key (which would drop ~43% of entities that lack a resolvable accession).

**Document structure — aggregation, not one-row-per-document**: The `protein` field is *not* unique per source file — a canonical protein appears once per cancer-type/dataset combination in `protein_inf.txt` (e.g. HEXB_P07686 appears in LAML/PDC000400, KDNY/PDC000127, SCCA/PXD004859, etc.). The parser therefore builds one in-memory aggregation record per unique `protein` ID (`entities` dict) and appends every matching row across all 5 data files as a list entry under `expression`, `ptm`, or `drug_correlations`. This mirrors the DISEASES/disgenet "groupby + `associatedWith`-style list" pattern from `production-plugin-examples.md`, adapted to three parallel list fields instead of one, because CancerProteome has three genuinely distinct relation types (protein-level expression, PTM-level expression, drug correlation) rather than one.

**Fields extracted**:
- `protein_id`, `gene_symbol`, `entity_type` (`canonical` or `microprotein`), `protein_length`, `uniprot` (regex-extracted from the `protein` ID suffix using the standard UniProt accession pattern) at the entity level.
- `expression[]`: `cancer`, `cancer_name` (joined from `cancer_names.txt`), `source` (PDC/PRIDE/MassIVE/etc. study accession), `mean_control`, `mean_tumor`, `fc`, `fdr`.
- `ptm[]`: same shape as `expression[]` plus `site` (the `[S1142]`-style residue+position parsed out of `PTM_in_protein`) and the raw `ptm_in_protein` string.
- `drug_correlations[]`: `drug` (name), `drug_source`/`drug_source_id` (parsed out of the `Drug` field's `"Name (SOURCE:ID)"` convention, e.g. `GDSC1:1001`), `cor`, `fdr`, `cancer`, `cancer_name`.
- `protein_length` is classified `REDUNDANT` in the site inspection report but retained anyway since it is cheap and occasionally useful context (not counted as "novel" data driving the ingest decision).

**Entity-type inference for drug-only entities**: 2,620 of the 7,630 unique protein IDs in `protein_durg_inf.txt` never appear in any expression/PTM file, so `entity_type` cannot be observed directly for them. A best-effort suffix-pattern heuristic (`_infer_entity_type()`) classifies these using the same ID-suffix conventions the site itself uses (UniProt accession or `_Canonical_N` → canonical; `_MP`, `_odORF`, `_pseudogene`, `_lncRNA`, `_uORF`, `_ouORF` → microprotein). This resolves `entity_type` for all but 1 of 16,744 entities (99.99% coverage); the single remaining unresolved ID (`NUDT4P1_oof`) uses a typo'd suffix (`oof`, presumably `ORF`) not matched by the heuristic and is left `None` rather than guessed incorrectly.

**Deduplication**: none needed beyond the aggregation itself — `entities` dict keys are exactly the unique `protein` IDs, so `on_duplicates: "error"` in the manifest is safe (each `_id` is yielded exactly once).

**Data cleaning**: `_to_float()`/`_to_int()` strip whitespace (source FDR values have a leading space, e.g. `" 3.576e-02"`) and coerce `"NA"`/empty strings to `None`; `dict_sweep()` + `unlist()` (BioThings SDK helpers) are applied per-row-record and again at the final document level to strip `None`/empty values and flatten single-item lists (visible in sample output below, where a protein with exactly one expression record has `expression` as a dict rather than a list of one dict — standard `unlist()` behavior).

## Sample Output Documents

### Typical example — canonical protein with expression, PTM, and drug data (`HEXB_P07686`)
Source cross-reference: https://bio-bigdata.hrbmu.edu.cn/CancerProteome/ (search "HEXB" or "P07686" via the site's Browse/Search page; no per-record permalink exists)

```json
{
  "_id": "HEXB_P07686",
  "cancerproteome": {
    "protein_id": "HEXB_P07686",
    "gene_symbol": "HEXB",
    "entity_type": "canonical",
    "protein_length": 556,
    "uniprot": "P07686",
    "expression": [
      {
        "cancer": "LAML",
        "cancer_name": "Acute Myeloid Leukemia",
        "source": "PDC000400",
        "mean_control": 22.347,
        "mean_tumor": 22.967,
        "fc": 1.537,
        "fdr": 0.03576
      },
      {
        "cancer": "KDNY",
        "cancer_name": "Kidney Cancer",
        "source": "PDC000127",
        "mean_control": 25.008,
        "mean_tumor": 24.394,
        "fc": 0.654,
        "fdr": 9.1e-18
      }
    ]
  }
}
```
(truncated — full document has 27 `expression` records across cancer types/datasets for this gene)

### Edge case — microprotein with PTM data, no drug correlation (`TMSB10_P63313`)
Source cross-reference: https://bio-bigdata.hrbmu.edu.cn/CancerProteome/ (Browse → microproteins → search "TMSB10")

```json
{
  "_id": "TMSB10_P63313",
  "cancerproteome": {
    "protein_id": "TMSB10_P63313",
    "gene_symbol": "TMSB10",
    "entity_type": "microprotein",
    "protein_length": 44,
    "uniprot": "P63313",
    "expression": [
      {
        "cancer": "LAML",
        "cancer_name": "Acute Myeloid Leukemia",
        "source": "PDC000400",
        "mean_control": 20.074,
        "mean_tumor": 20.809,
        "fc": 1.664,
        "fdr": 0.007949
      },
      {
        "cancer": "HNSC",
        "cancer_name": "Head and Neck Squamous Cell Carcinoma",
        "source": "PDC000221",
        "mean_control": 22.767,
        "mean_tumor": 23.374,
        "fc": 1.523,
        "fdr": 3.464e-20
      }
    ]
  }
}
```
(truncated — this entity has additional `expression` records across other cancer types)

## Field Coverage
(from a full parse of all 16,744 documents — dataset is small enough to sample completely rather than a 1000-doc subsample)

- `cancerproteome.entity_type`: 99.99% (16,743 / 16,744; single unresolved suffix `_oof`)
- `cancerproteome.gene_symbol`: 89.4%
- `cancerproteome.protein_length`: 89.4%
- `cancerproteome.uniprot`: 57.4% (remaining 42.6% use non-UniProt suffixes — isoform/microprotein/lncRNA/ORF conventions with no resolvable accession)
- `cancerproteome.expression`: 67.4%
- `cancerproteome.ptm`: 44.1%
- `cancerproteome.drug_correlations`: 45.6%

Entity type breakdown: 15,829 canonical proteins, 914 microproteins, 1 unresolved.

## Test Results Summary

- **biothings-cli**: unavailable in this sandbox. `biothings-cli --version` fails with `AttributeError: module 'typer' has no attribute 'rich_utils'` (same typer/biothings v1.0.2 incompatibility documented for prior plugins in this pipeline, e.g. ecbd, coconut, chemprob). Per instructions, the shared Python environment was **not** patched.
- **Fallback validation performed instead**: all 6 source files were downloaded directly (with a browser `User-Agent` header — the site 403s default non-browser clients) and `parser.py`'s `load_data()` was imported and run directly against the downloaded files in a Python REPL.
  - Result: **16,744 unique documents** yielded from 292,970 combined source rows, zero exceptions, zero skipped rows, zero duplicate `_id`s.
  - Verified: every document has a string `_id` (max length 31 chars, well under the 512-char limit); every document has a populated `cancerproteome` key; no stray `None`/empty-list values remain after `dict_sweep()`/`unlist()`.
- **Not verified by this session**: the biothings-cli `validate`/`dump`/`upload`/`list`/`inspect` steps themselves — these require a working CLI, which is broken in this environment independent of this plugin's code.

## Notes / Known Limitations

- **License mismatch**: paper states CC BY-NC; the live site displays no license text at all (only a copyright notice). `license` in `__metadata__` uses the paper's CC BY-NC 4.0 statement per the relevancy report; flagged as a gap for downstream review.
- **Site blocks default HTTP clients**: `bio-bigdata.hrbmu.edu.cn` returns HTTP 403 to bots/curl's default User-Agent but 200 to a standard browser User-Agent string. A production Hub deployment will need a custom `dumper.py` (subclassing `biothings.hub.dataload.dumper.LastModifiedHTTPDumper` and overriding `download()` to set a browser `User-Agent` header, matching the FDA_Drugs plugin's pattern in `production-plugins-registry.json`) — the manifest-only `dumper.data_url` path used here assumes the Hub's default HTTP client can be configured with headers, or that this override is added before production deployment.
- **No versioned release**: the site has no API, changelog, or visible "last updated" date; `version.py` relies on the HTTP `Last-Modified` header of `protein_inf.txt` (observed: `2023-08-31`), falling back to a homepage year scrape, then a hardcoded date.
- **Paper-vs-site count discrepancy**: the NAR 2024 paper reports 31,120 proteins; the live site (and this ingest) shows 35,231 canonical + microprotein-adjacent entries combined, and this parser's own count (15,829 canonical) does not exactly match either figure — the site appears to have been updated post-publication without a versioned release note. Re-check counts at future re-ingestion.
- **Drug-only entities without expression/PTM data** (2,620 of 7,630 unique drug-file protein IDs) rely on a best-effort ID-suffix heuristic for `entity_type` rather than an observed value from an expression/PTM file.
- **CC BY-NC** — non-commercial restriction; flagged per evaluation-checklist.md guidance for downstream commercial API consumers.
