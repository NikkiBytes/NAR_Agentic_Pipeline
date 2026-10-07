# TPDdb Plugin — Design Rationale

## Quick Stats

| Metric | Value |
|--------|-------|
| Source rows | ~28,007 (6 main tables after header dedup) |
| Documents yielded | 27,904 |
| Rows skipped | 1 (duplicate header row in PROTAC_main_table mid-file) |
| Activity records joined | ~26,643 across 3 activity files |
| Disease records joined | ~99,900 rows in disease table |
| PDB records joined | ~176 rows |
| Target API | pending.api |
| Primary key | TPD ID (e.g. `TPD-P58QBR`) |
| Data format | TSV (tab-delimited .txt), 11 files total |
| Total download size | ~25 MB |
| Release | 20251020 (Last-Modified from PROTAC_main_table.txt) |

---

## Why These Dump Files Were Chosen

### Files included (all 11)

**6 compound main tables** — each covers one TPD modality:
- `PROTAC_main_table.txt` (21,430 rows) — PROTAC degraders with target + ligase
- `MG_main_table.txt` (6,005 rows) — Molecular glues with Subtype column
- `LYTAC_main_table.txt` (324 rows) — Lysosome-targeting antibody conjugates; 18-column schema with linker/receptor fields
- `ATTEC_main_table.txt` (170 rows) — Autophagosome-tethering compounds
- `AUTAC_main_table.txt` (23 rows) — Autophagy-targeting chimeras
- `AUTOTAC_main_table.txt` (29 rows) — AUTOphagy-TArgeting Chimeras

All 6 are required because each covers a distinct modality that does not appear in any other file.

**3 activity tables** — bioactivity measurements per compound:
- `PROTAC_activity.txt` (23,322 rows)
- `MG_activity.txt` (2,782 rows)
- `Lysosome-based_TPD_activity.txt` (536 rows)

These are the core novel data — IC50, DC50, Dmax, cell viability, residual rate measurements across 201 cell lines. Joined by TPD ID.

**2 supporting tables**:
- `TPD_Related_Diseases.txt` (~99,900 rows) — one row per disease per compound; ICD-11 and OrphaID
- `TPD_PDB.txt` (176 rows) — PDB ternary complex structure IDs

### No files excluded
All available download files are included. Unlike ECBD (which has a superset file), TPDdb's files are all independent by modality.

---

## Why the Parser Works the Way It Does

### _id Strategy
**TPD ID** (e.g. `TPD-P58QBR`) is used as `_id` rather than InChIKey.

Rationale:
1. **InChIKey is absent from bulk download files.** It only appears on per-compound HTML detail pages. Computing it would require RDKit (heavy dependency) or scraping 28K pages.
2. **TPD ID is globally unique** across all 6 modalities and is stable across time.
3. **pending.api** accepts any unique string as `_id`. MyChem.info would require InChIKey.
4. SMILES is present for 99.6% of compounds — a follow-up enrichment step could add InChIKey via RDKit if MyChem.info ingestion is desired.

### Document Structure
```
{
  "_id": "TPD-P58QBR",
  "tpddb": {
    "tpd_id": "TPD-P58QBR",
    "name": "Nvp-dky709",
    "modality": "Molecular Glue",
    "smiles": "...",
    "formula": "C25H27N3O3",
    "subtype": "Degrader",         // MG only
    "synonyms": [...],
    "xrefs": {"chembl": [...], "cas": [...]},
    "target": {"symbols": "IKZF2", "uniprot_ids": "Q9UKS7"},
    "ligase": "CRBN",
    "source": "10.1016/j.chembiol.2023.02.005",
    "activities": [
      {"activity_type": "IC50", "activity": "4nM", "cell_line": "..."}
    ],
    "diseases": [
      {"name": "Multiple myeloma", "icd11": "2A83.1", "source": "Orphanet", "orpha_or_ncit_id": "..."}
    ],
    "pdb_ids": ["6SIP"]
  }
}
```

### Multi-file Join Strategy
The parser uses a 4-phase approach:
1. `_load_main_tables()` — builds compound dict keyed by TPD ID
2. `_load_activities()` — builds `defaultdict(list)` of activity records keyed by TPD ID
3. `_load_diseases()` — builds `defaultdict(list)` of disease records keyed by TPD ID
4. `_load_pdb()` — builds PDB mapping keyed by TPD ID

Final `load_data()` iterates the compound dict, attaches activity/disease/PDB lists, and yields.

### Header Deduplication Fix
`PROTAC_main_table.txt` contains a duplicate header row at line 21,055 (a data quality issue in the source). The parser skips any row where `TPD ID == "TPD ID"`.

### Multi-value Field Handling
- `Target Symbol`: semicolon-delimited → split by `";"`, returns list or string (unlist flattens single-item)
- `Target ID` (UniProt): slash-delimited → split by `"/"`
- `PubChem synonyms`: semicolon-delimited; ChEMBL IDs and CAS numbers extracted to `xrefs`
- Activity `"."` placeholder → `None` → removed by `dict_sweep`
- `Complex_PDB_ID`: slash-delimited → split by `"/"`

### LYTAC-Specific Handling
LYTAC has 18 columns vs 9 in other modalities. The parser detects LYTAC-specific fields (`Lytac_target`, `Lysosome-targeting receptors`, `Linker type`, `Lytac_Linker`) and adds a nested `lytac` sub-object only when present.

---

## Sample Output Documents

### Typical PROTAC with activities and diseases

```json
{
  "_id": "TPD-S8O3RK",
  "tpddb": {
    "tpd_id": "TPD-S8O3RK",
    "name": "EP4023649A1_1",
    "modality": "PROTAC",
    "smiles": "CC1=C(C2=CC=C(CNC(=O)[C@@H]3C[C@H](O)CN3C(=O)...)C=C2)SC=N1",
    "formula": "C45H56F3N9O6S",
    "target": {"symbols": "AR", "uniprot_ids": "P10275"},
    "ligase": "VHL",
    "source": "EP-4023649-A1",
    "activities": [
      {"activity_type": "Cell viability_1", "activity": "+++", "cell_line": "CWR22RV1"},
      {"activity_type": "Residual rate_1", "activity": "+++", "cell_line": "CWR22RV1", "target_symbols": "AR", "target_uniprot_ids": "P10275"}
    ],
    "diseases": [
      {"name": "Kennedy disease", "icd11": "8B61.4", "source": "Orphanet", "orpha_or_ncit_id": "481"},
      {"name": "Partial androgen insensitivity syndrome", "icd11": "LD2A.4", "source": "Orphanet", "orpha_or_ncit_id": "90797"}
    ]
  }
}
```
Source cross-reference: https://tpddb.idrblab.net/data/tpd/details/TPD-S8O3RK

### Molecular Glue with synonyms/xrefs

```json
{
  "_id": "TPD-P58QBR",
  "tpddb": {
    "tpd_id": "TPD-P58QBR",
    "name": "Nvp-dky709",
    "modality": "Molecular Glue",
    "smiles": "O=C1CCC(N2Cc3cc(C4CCN(Cc5ccccc5)CC4)ccc3C2=O)C(=O)N1",
    "formula": "C25H27N3O3",
    "subtype": "Degrader",
    "synonyms": ["NVP-DKY709", "CHEMBL5077506", "HY-144998"],
    "xrefs": {"chembl": ["CHEMBL5077506"]},
    "target": {"symbols": "IKZF2", "uniprot_ids": "Q9UKS7"},
    "ligase": "CRBN",
    "source": "10.1016/j.chembiol.2023.02.005"
  }
}
```
Source cross-reference: https://tpddb.idrblab.net/data/tpd/details/TPD-P58QBR

---

## Field Coverage (sample 1000 docs)

| Field | Coverage |
|-------|----------|
| `tpddb.tpd_id` | 100% |
| `tpddb.name` | 100% |
| `tpddb.modality` | 100% |
| `tpddb.smiles` | 100% |
| `tpddb.formula` | 100% |
| `tpddb.target` | 100% |
| `tpddb.ligase` | 100% |
| `tpddb.source` | 100% |
| `tpddb.synonyms` | 81.4% |
| `tpddb.diseases` | 66.4% |
| `tpddb.activities` | 45.8% |
| `tpddb.xrefs.cas` | 0.4% |
| `tpddb.xrefs.chembl` | 0.1% |
| `tpddb.pdb_ids` | 0.6% |
| `tpddb.subtype` | MG modality only (~21.5%) |

---

## Test Results Summary

| Step | Status | Notes |
|------|--------|-------|
| validate | PASS | All required manifest fields present; schema valid |
| dump (version.py) | PASS | Returns `20251020` from Last-Modified header |
| upload (parser) | PASS | 27,904 unique documents; 1 header row skipped |
| list | PASS | 27,904 docs in collection |
| inspect | PASS | `_id` = string TPD ID; `tpddb` key 100%; no null fields |

**Known issues:**
- `PROTAC_main_table.txt` contains a duplicate header row at line 21,055 — handled in parser
- Activity values are heterogeneous (numeric with units, qualitative `+++/++/+`, range `>10nM`) — not normalized; stored as raw strings for downstream parsing
- XRefs coverage is low (ChEMBL 0.1%, CAS 0.4%) — PubChem synonyms field contains mixed free text; most ChEMBL IDs appear in longer synonym strings not matching the `CHEMBL` prefix pattern
