# MolBiC Plugin — Design Rationale

## Quick Stats

| Metric | Value |
|--------|-------|
| Source compounds | 321,086 |
| Source CMBs | 550,093 |
| Documents yielded (production) | ~321,000 (one per unique InChIKey) |
| Documents in test run | 5 (test fixture) |
| Target API | MyChem.info |
| Data format | TSV (tab-delimited .txt) |
| Key novel field | cell-based IC50/EC50/Ki in cellular assay context |

---

## Why These Files Were Chosen

**Included:**
- `1-3. Compound.txt` — compound structures with InChIKey, SMILES, InChI, chemical properties, PubChem/ChEMBL xrefs (321,086 compounds)
- `2-1. CMBs_All.txt` — all 550,093 cell-based molecular bioactivity records, grouped by InChIKey
- `1-1. Cell_Line.txt` — cell line metadata (Cellosaurus accession, tissue, disease, organ, species) — joined to CMBs via Cell Line name
- `5-2. Proteins_with_Uniprot_IDs.txt` — protein → UniProt ID mapping; enriches CMB records with UniProt

**Excluded with justification:**
- `2-1-1. CMBs_High.txt`, `2-1-2. CMBs_Moderate.txt`, `2-1-3. CMBs_Low.txt` — strict subsets of `2-1. CMBs_All.txt`; not needed since we ingest the full set
- `1-2. Protein.txt` — protein general info already captured via UniProt xref from `5-2. Proteins_with_Uniprot_IDs.txt`
- `4-1. All_Compounds_in _SDF.tar.xz` — SDF structures duplicate what's in Compound.txt; 3D structure data not needed for MyChem.info search indexing

---

## Why the Parser Works the Way It Does

**`_id` strategy**: InChIKey — standard MyChem.info compound identifier. The InChIKey is in `1-3. Compound.txt`. CMBs are grouped by InChIKey using a `defaultdict(list)` index built in memory before the main loop.

**Document structure**: All data nested under `molbic` top-level key.
- `compound_id`: MolBiC internal ID (e.g., `CP0122977`)
- `activity_summary`: pre-computed counts of High/Moderate/Low CMBs for fast faceting
- `cmbs`: full list of bioactivity records from CMBs_All.txt, each with protein/cell/value/class/stage

**Multi-file join strategy**:
1. `cell_index`: Cell Line name → {cellosaurus_accession, tissue, disease, organ, species} from Cell_Line.txt
2. `protein_index`: Protein name → UniProt ID from Proteins_with_Uniprot_IDs.txt
3. `cmb_index`: InChIKey → [CMB records] from CMBs_All.txt (with enrichment from cell_index and protein_index)

**Filename handling**: MolBiC files have literal spaces in their names (e.g., `1-3. Compound.txt`). `_find_file()` tries the original spaced name, then underscore-substituted alternative, then a glob fallback. This ensures the parser works regardless of how files were pre-placed.

---

## CRITICAL: Download Blocker

MolBiC files are served via Drupal 8 browser JS click handlers. The files have literal spaces in their filenames, and URL-encoding (%20) does NOT work — the Drupal server returns 404 for all programmatic requests. This means:

- `biothings-cli dataplugin dump` will FAIL with 404 errors
- `dump_and_upload` will FAIL for the same reason

**Required manual step before `upload`:**
1. Open https://molbic.idrblab.net/download in a browser
2. Download these 4 files:
   - `1-3. Compound.txt`
   - `2-1. CMBs_All.txt`
   - `1-1. Cell_Line.txt`
   - `5-2. Proteins_with_Uniprot_IDs.txt`
3. Place them in `.biothings_hub/archive/molbic_plugin/<RELEASE>/` (spaces in names preserved)
4. Patch `.biothings_hub/db/src_dump` to mark download as success (see validation notes)
5. Run `biothings-cli dataplugin upload`

---

## Sample Output Document

```json
{
  "_id": "KTUFNOKKBVMGRW-UHFFFAOYSA-N",
  "molbic": {
    "compound_id": "CP0001",
    "name": "Imatinib",
    "inchikey": "KTUFNOKKBVMGRW-UHFFFAOYSA-N",
    "smiles": "CC1=CC=C(C=C1)...",
    "properties": {
      "formula": "C29H31N7O",
      "logp": 3.5,
      "rotatable_bonds": 7,
      "heavy_atom_count": 36,
      "polar_area": 86.2
    },
    "xrefs": {
      "pubchem": "5291",
      "chembl": "CHEMBL941"
    },
    "activity_summary": {
      "total_cmbs": 3,
      "high_activity": 3
    },
    "cmbs": [
      {
        "compound_id": "CP0001",
        "protein": "ABL1",
        "uniprot_id": "P00519",
        "cell_line": "K562",
        "cell_info": {
          "cellosaurus_accession": "CVCL_0004",
          "tissue": "Lymphoid tissue",
          "disease": "Chronic myelogenous leukemia",
          "organ": "Blood",
          "species": "Homo sapiens"
        },
        "bioactivity_value": 0.025,
        "bioactivity_unit": "uM",
        "activity_type": "IC50",
        "activity_class": "High",
        "drug_development_stage": "Approved",
        "assay_type": "Cell viability",
        "pmid": "15256602"
      }
    ]
  }
}
```

---

## Test Results Summary

| Step | Status | Notes |
|------|--------|-------|
| validate | PASS | Valid manifest, all required fields present |
| dump | FAIL (expected) | 404 on all URLs — Drupal JS-only download with spaces in filenames |
| upload | PASS | 5 test documents from pre-placed fixture files |
| list | PASS | Collections populated: molbic_plugin (5 test docs) |
| inspect | PASS (SQLite) | _id: str (27 chars, InChIKey), nested cmbs list with cell context, 100% field coverage |

**Document count (test fixture)**: 5 (5 compounds, 10 CMBs total)
**Document count (production)**: ~321,086 (one per unique InChIKey from Compound.txt)
**Dump workaround required**: Files must be manually downloaded from browser and pre-placed in archive dir before upload. See CRITICAL section above.
**Wrapper required**: biothings-cli typer.rich_utils incompatibility — use `python3 /tmp/biothings_wrapper.py dataplugin <cmd>` (typer ≥0.26 monkey-patch)
