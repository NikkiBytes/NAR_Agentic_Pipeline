# PRIME Plugin — Design Rationale

## Quick Stats

| Metric | Value |
|--------|-------|
| Source rows | 53,449 (one per SRA run) |
| Documents expected | ~53,449 |
| Rows skipped | Rows with empty `Run` field only |
| Target API | pending.api |
| Data format | CSV (38.2 MB) |
| Total files | 1 (`samples_metadata.csv`) |
| Archive source | Zenodo (canonical site download page is JS-rendered) |
| Zenodo record | https://zenodo.org/records/15711237 (v1, 2025-07-18) |

---

## Why These Dump Files Were Chosen

**Chosen: `samples_metadata.csv` (38.2 MB)**

This is the primary entity file — one row per SRA run with all sample-level metadata: sequencing parameters, processing pipeline settings, geographic origin, phenotype category, and sparse clinical/demographic fields. It maps directly to the sample-as-document model (SRA run accession → `_id`).

**Excluded: 24 abundance table files (gg_*/silva_* CSVs, 37 MB – 1.8 GB each)**

Abundance tables are wide matrices (samples × taxa). Including them in this plugin would require a transpose/groupby to pivot from "one row per sample×taxon pair" to "one nested dict per sample." At genus/species level the per-sample abundance dicts would be thousands of entries wide. This is a deliberate scope decision — the abundance data is better served as:
- A companion plugin keyed by sample×taxon pair, OR
- An on-demand API call via `primedb.sjtu.edu.cn/api/v1/abundances`

Phylum-level files (SILVA: 15.7 MB + 23.1 MB; GG2: 14 MB + 22.9 MB) could be joined into this plugin in a future v2 — the groupby logic is straightforward, but adds ~75 MB of download.

**Excluded: `projects_metadata.csv` (108 KB)**

Project-level summaries are aggregate views of sample data (title, introduction, phenotype list, sample count). All project fields that matter for analysis are also present per-row in `samples_metadata.csv` — ingesting this file separately would create a second entity type and require `uploaders` (plural). Out of scope for v1.

**Excluded: `primeDB_0.1.0.tar.gz`, classifier `.qza` files**

R package and QIIME2 classifiers are tooling, not data.

**Canonical site vs Zenodo:**

The PRIME download page (`primedb.sjtu.edu.cn/download`) is JS-rendered — no direct file URLs could be extracted via page fetch, probe URL patterns, or page source scan. The paper's Data Availability section explicitly references `https://doi.org/10.5281/zenodo.15711237` as the permanent archive. Zenodo was used per the JS-rendered fallback protocol (steps 1–4 exhausted). Flagged in `prime_relevancy.json` under `risks`.

---

## Why the Parser Works the Way It Does

**`_id` strategy: SRA run accession (`Run` column)**

The SRA run accession (e.g., `DRR396973`, `ERR...`) is the finest-grained unique identifier in the dataset — one sequencing run, one sample, one row. It's universally recognized across NCBI/ENA/DDBJ databases and is the natural join key for downstream analysis.

**Structured sub-objects**

Fields are grouped into six nested objects under `prime`:
- `project` — `BioProject`, `SRA_Study`, project name
- `sample` — `BioSample`, sample name, participant ID
- `sequencing` — instrument, layout, type, variable region, read stats
- `processing` — PRIME pipeline parameters (primer cut, denoising, taxonomy DB, QC ratings)
- `geography` — country, continent
- `phenotype` — body site, organ system, phenotype category, study group

`flags` (time_series, comparison, matched) are booleans; yes/no → True/False.

**Sparse clinical fields → `host` sub-object**

The CSV contains ~40 additional columns for demographic and clinical data (age, sex, BMI, antibiotic use, tumor staging, fertility metrics, etc.). These are null for the majority of samples. The parser puts any non-known, non-empty column into `host` with its key lowercased. `dict_sweep` then removes all null entries — documents for samples with no clinical data will simply omit the `host` key entirely.

This approach handles the sparse data without hardcoding all 40 column names, and remains forward-compatible if PRIME adds new clinical fields in future releases.

**`on_duplicates: error`**

Each SRA run accession is globally unique — NCBI/ENA enforce uniqueness at the accession registry level. No deduplication is needed.

---

## Sample Output Documents

**Typical sample (healthy gut, Japan):**
```json
{
    "_id": "DRR396973",
    "prime": {
        "run": "DRR396973",
        "experiment": "DRX...",
        "project": {
            "bioproject": "PRJDB13875",
            "sra_study": "DRP...",
            "name": "MUSC-JP-2024"
        },
        "sample": {
            "biosample": "SAMD...",
            "name": "...",
            "participant_id": "..."
        },
        "sequencing": {
            "instrument": "Illumina MiSeq",
            "library_layout": "Paired",
            "type": "2×300",
            "variable_region": "V1-V2",
            "avg_spot_len": 600,
            "bases": 19625797
        },
        "processing": {
            "primer_cut": "Yes",
            "primer_params": "-p -b -d",
            "denoise_params": "-p -F 250 -R 140",
            "taxonomy_db": "Silva and greengenes2",
            "sequencing_quality": "Good",
            "filter_pass": "Excellent"
        },
        "geography": {
            "country": "Japan",
            "continent": "Asia"
        },
        "phenotype": {
            "body_site": "Stool/feces",
            "system": "Digestive System/Gut",
            "phenotype_category": "Healthy",
            "study_group": "Control"
        },
        "flags": {
            "time_series": false,
            "comparison": true,
            "matched": false
        },
        "collection_date": "2020-08-05",
        "release_date": "2024-01-03",
        "create_date": "2024-01-03"
    }
}
```

Source cross-reference: `https://primedb.sjtu.edu.cn/api/v1/samples/DRR396973/stats`

**Sample with clinical host data:**
For disease cohort samples the `prime.host` sub-object will be populated with sparse clinical fields — e.g., for an IBS cohort: `{"age": "34", "sex": "female", "bmi": "22.3"}`. Fields vary by study; `dict_sweep` removes all nulls.

---

## Field Coverage (estimated from API inspection)

Fields present for all samples:
- `prime.run`, `prime.project.bioproject`, `prime.sequencing.instrument`, `prime.phenotype.body_site`, `prime.phenotype.phenotype_category`, `prime.geography.country`, `prime.flags.*`

Fields present for most samples:
- `prime.collection_date`: ~70% (date known for most SRA studies)
- `prime.sequencing.avg_spot_len` / `bases`: ~95% (from SRA metadata)

Fields sparse (sample-dependent):
- `prime.host.*`: ~20–40% of samples (studies with clinical demographic data)
- `prime.sample.participant_id`: ~50%

---

## Test Results Summary

*To be populated after biothings-cli validation.*

Expected flow:
1. `validate` — confirms manifest.json schema
2. `dump` — downloads `samples_metadata.csv` (38.2 MB) from Zenodo
3. `upload` — yields ~53,449 documents
4. `list` — confirms plugin is registered
5. `inspect --sub-source-name prime --limit 1000` — verify field distribution

Known risk: Zenodo download may be rate-limited or require browser cookies; test with `curl -L` first. Use `dump_and_upload` workaround if biothings v1.0.2 `upload` bug manifests.
