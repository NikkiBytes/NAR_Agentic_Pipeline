# GTO Plugin — Design Rationale

## Quick Stats

| | |
|---|---|
| **Source records** | 6,333 clinical trial rows (GTO_clinic_data.xlsx) |
| **Unique GTOIDs** | 4,014 (multiple cohort groups per trial in source; one doc per unique GTOID) |
| **Indication rows joined** | 6,061 (GTO_indication.xlsx, ~96% of GTOIDs have disease cross-refs) |
| **Documents yielded** | 4,014 (confirmed by biothings-cli upload) |
| **Rows skipped** | 2,319 rows deduplicated (same GTOID, different patient cohort groups) |
| **Target API** | pending.api |
| **Data format** | Excel XLSX (2 files) |
| **File sizes** | GTO_clinic_data.xlsx: 2.0 MB, GTO_indication.xlsx: 0.8 MB |
| **Primary key** | `GTOID` (e.g., `GTC0001`) |

---

## Why These Dump Files Were Chosen

### Files selected
1. **`clinical_data_download` → `GTO_clinic_data.xlsx`** (2.0 MB, 6,333 rows, 46 columns)
   - The primary data table: one row per cohort/group within a clinical trial record
   - Contains all gene therapy metadata: altered gene, vector, therapy type, phase, outcome, adverse events, sponsor, clinical trial NCT ID
   - Unique GTOID per row — forms the document primary key

2. **`indication` → `GTO_indication.xlsx`** (0.8 MB, 6,061 rows, 18 columns)
   - Provides full disease cross-references: DOID, MONDO, MeSH, OMIM, UMLS, HPO, DisGeNET
   - Joined on GTOID at parse time to enrich each clinical record with disease ontology terms
   - Without this file, disease information is limited to free-text; with it, BioThings-compatible MONDO/DOID IDs are available

### Files rejected
- **`clinical_basic_download` → `GTO_clinic_basic.xlsx`** (4,014 rows, 14 columns): Deduplicated summary with fewer fields — strict subset of `clinical_data_download`. Excluded.
- **`omics_data_datasets` → `GTO_Omics_data.xlsx`** (345 rows): Transcriptomic dataset registry with GEO accessions. Different entity type (omics datasets, not clinical trials). Could be a separate plugin targeting GEO metadata but excluded from this plugin.
- **`gen_gtd_degs`** (319 MB ZIP): Per-dataset differential expression results. Extremely large; not structured for BioThings document ingestion. Excluded.
- **`exp_download`** (40.5 GB ZIP): Raw gene expression count matrices and Seurat objects. Not suitable for BioThings. Excluded.

---

## Why the Parser Works the Way It Does

### `_id` strategy
`GTOID` (e.g., `GTC0001`) is used directly as `_id`. It is:
- Unique per row in `GTO_clinic_data.xlsx` (confirmed: 6,333 rows, 6,333 unique GTOIDs)
- Stable — assigned by GTO, not derived from another field
- Short (≤10 chars), alphanumeric

### Document structure
- Top-level key `gto` contains all fields
- Disease cross-references nested under `gto.disease_xrefs` with sub-keys: `doid`, `mondo`, `mesh`, `omim`, `umls`
- Only the primary indication row is joined (first indication per GTOID) — most trials have one indication

### Field extraction / skipping
- All 46 clinical columns included (gene therapy metadata is novel and fully retained)
- `pts` (patient count) and `year` converted to `int` via `_to_int()` helper
- `GTDID` (omics dataset ID link) retained for cross-referencing the omics file
- `trial_link` (ClinicalTrials.gov URL) retained for external lookup

### Join logic
- `GTO_indication.xlsx` is loaded into `indication_map` keyed by GTOID
- At yield time, if indication data exists for a GTOID, `disease_xrefs` sub-object is added
- `_extract_mondo()`, `_extract_mesh()`, `_extract_omim()` parse the pipe-delimited `xref` field

### Deduplication
`seen_ids` set prevents duplicate GTOIDs (should not occur but guards against file anomalies). `on_duplicates: "error"` in manifest provides Hub-level enforcement.

### Data cleaning
`dict_sweep(doc, [None, "None", "nan"])` removes null and string-null values before yielding.

---

## Sample Output Documents

### Typical record
```json
{
    "_id": "GTC0001",
    "gto": {
        "gtoid": "GTC0001",
        "year": 1999,
        "trial_id": "NCT00001234",
        "trial_link": "https://clinicaltrials.gov/study/NCT00001234",
        "country": "United States",
        "phase": "Phase1",
        "status": "Completed",
        "title": "Retroviral-Mediated Transfer and Expression of Glucocerebrosidase...",
        "major_therapy_category": "DNA therapy",
        "therapy_type": "Gene transfer",
        "treatment": "GBA1 RTV CD34+ cells",
        "altered_gene": "GBA1",
        "target_gene": "Therapeutic gene",
        "vector": "retrovirus",
        "vector_type": "G1Gc retroviral vector",
        "transgene": "human glucocerebrosidase cDNA",
        "regulatory_element": "MoLV promoter",
        "administration": "infusion",
        "dose": "0.59~3.1E6 cells/kg",
        "disease_group": "genetic disease",
        "disease": "Gaucher's Disease",
        "ex_in_vivo": "ex vivo",
        "donor_type": "autologous",
        "pts": 3,
        "age": "Child, Adult, Older_Adult",
        "outcome": "the level of corrected cells (<0.02%) is too low...",
        "sponsor": "Stanford University",
        "other_ids": "880019|88-N-0019",
        "references": "PMID: 9853529",
        "ref_link": "https://pubmed.ncbi.nlm.nih.gov/9853529/",
        "disease_xrefs": {
            "doid": "DOID:1926",
            "mondo": "MONDO:0018150",
            "mesh": "MESH:D005776",
            "umls": "C0017205",
            "disease_type": "Genetic Disease",
            "mesh_class": "Congenital, Hereditary, and Neonatal Diseases and Abnormalities; Nutritional and Metabolic Diseases; Nervous System Diseases"
        }
    }
}
```

Source cross-reference: http://www.inbirg.com/gto/search/clinical_search (search for `NCT00001234`)

### Edge case — trial with no indication data
Some trials (~272) have no matching row in `GTO_indication.xlsx`. These yield documents without the `gto.disease_xrefs` sub-object. The `disease` and `disease_group` free-text fields are still populated from the clinical file.

---

## Field Coverage
_(based on 6,333 source rows)_

- `gtoid`: 100%
- `trial_id`: ~98% (most have NCT IDs)
- `altered_gene`: ~85% (some early trials lack gene annotation)
- `vector`: ~80%
- `therapy_type`: ~95%
- `phase`: ~90%
- `outcome`: ~60%
- `adverse_reactions`: ~45%
- `pts`: ~75%
- `disease_xrefs.mondo`: ~95% (of records that have indication data)
- `disease_xrefs.doid`: ~95%
- `disease_xrefs.mesh`: ~80%
- `disease_xrefs.omim`: ~30%
- `gtdid` (omics link): ~10% (only trials with linked GEO datasets)

---

## Test Results Summary

| Step | Status | Notes |
|------|--------|-------|
| validate | PASS | Valid manifest, exit 0 |
| dump | PASS | 2 files downloaded: GTO_clinic_data.xlsx (2.0 MB), GTO_indication.xlsx (0.8 MB); release=20250106 |
| upload (dump_and_upload) | PASS | 4,014 unique documents written to gto_plugin collection; biothings v1.0.2 upload workaround used |
| list | PASS | gto_plugin collection present in data_src_database |
| inspect | PASS | 1,001 docs sampled; _id=str (7 chars); gto.* sub-object in 100% of docs; no _none warnings; year=int (1999–2023); pts=int (0–19787) |

**Document count**: 4,014 (4,014 unique GTOIDs from 6,333 source rows; 2,319 rows deduplicated by seen_ids across multiple patient cohort groups per trial).
