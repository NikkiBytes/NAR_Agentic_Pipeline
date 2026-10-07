# PersADE Plugin — Design Rationale

## Quick Stats

| Metric | Value |
|--------|-------|
| Source drugs | 8,802 (Global_Drug file) |
| Source ADEs | 4,380 (Global_ADE file) |
| Source associations | 461,848 (Global_associations file) |
| Documents yielded | 8,595 (unique InChIKeys with deduplicated rows) |
| Target API | MyChem.info |
| Data format | XLSX (openpyxl) |
| Key novel fields | ade_associations (list of MeSH ADEs per drug), atc_code, drug_type |

---

## Data Gap Warning

The 2026 NAR paper describes PersADE as containing **4,061,772 personalized drug-ADE associations** with demographic stratification (age, sex, route, dose). This data is NOT available for bulk download. The download page (`persade.idrblab.net/resource.php`) currently serves files dated **2023-06-27** representing the older **mtADENet** dataset with ~461K non-personalized drug-ADE pairs.

This plugin ingests the available 2023 mtADENet data. The full PersADE personalized dataset should be monitored for future availability.

---

## Why These Files Were Chosen

**Included:**
- `Global_Drug_20230627.xlsx` — drug entity table with InChIKey, MeSH drug ID, CASRN, SMILES, xrefs (PubChem/BindingDB/ChEBI/ChEMBL/IUPHAR/KEGG/TTD/ZINC), formula, MW, logP, ATC code, drug type (8,802 drugs)
- `Global_ADE_20230627.xlsx` — ADE metadata with MeSH ID, MeSH tree number, ADE name (4,380 ADEs)
- `Global_associations_20230627.xlsx` — drug-ADE pairs: InChIKey + MeSH ID (461,848 associations); grouped by InChIKey to build `ade_associations` list per drug

**Excluded with justification:**
- `C04_associations_20230627.xlsx` — strict subset of Global_associations (neoplasm category only); not needed since Global_associations is ingested in full

---

## Why the Parser Works the Way It Does

**`_id` strategy**: InChIKey — the `InChI Key` field (note: space) in the Global_Drug file. This maps natively to MyChem.info compound identifiers.

**Document structure**: All data nested under `persade` top-level key.
- `ade_count`: integer count of ADE associations for this drug (useful for faceting)
- `ade_associations`: list of MeSH ADE records (each has `mesh_id`, `tree_number`, `name`)

**Multi-file join strategy**:
1. `ade_index`: MeSH ID → {mesh_id, tree_number, name} from Global_ADE file
2. `assoc_index`: InChIKey → [ade records] from Global_associations file (enriched with ade_index at build time)
3. Main loop: iterate Global_Drug file, join assoc_index by InChIKey

**Cross-reference parsing**: The `Link` column uses pipe-delimited `Source$ID` format (e.g., `PubChem$46943432|ChEBI$95082|ChEMBL$CHEMBL1232461`). The `_parse_xref_links()` helper splits these into a flat dict keyed by lowercase source name.

**CASRN prefix removal**: Some CASRN values have a leading `$` character from the source data formatting (e.g., `$1260907-17-2`). The parser strips this prefix.

---

## Sample Output Document

```json
{
  "_id": "AAAQFGUYHFJNHI-SFHVURJKSA-N",
  "persade": {
    "inchikey": "AAAQFGUYHFJNHI-SFHVURJKSA-N",
    "name": "2-[(4s)-6-(4-Chlorophenyl)...",
    "smiles": "CCNC(=O)C[C@@H]1N=C(...)",
    "properties": {
      "formula": "C22H22ClN5O2",
      "mw": 423.89,
      "logp": 3.48
    },
    "drug_type": "Drug",
    "xrefs": {
      "pubchem": "46943432",
      "chebi": "95082",
      "chembl": "CHEMBL1232461",
      "kegg": "dr:D11326",
      "cas": "1260907-17-2"
    },
    "ade_count": 2,
    "ade_associations": [
      {
        "mesh_id": "D004844",
        "tree_number": "C08.460.261|C09.603.261|C23.550.414.712|C23.888.852.040",
        "name": "Epistaxis|Bleeding, Nasal|..."
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
| dump | PASS | 3 XLSX files downloaded (release 20240621) |
| upload | PASS | 8,595 documents via dump_and_upload |
| list | PASS | Collections populated: persade_plugin (8,595 docs) |
| inspect | PASS (SQLite) | _id: str (27 chars, InChIKey); ade_count 1-100+ per drug; xrefs include pubchem/chembl/chebi/kegg/cas |

**Document count**: 8,595 (from 8,802 Global_Drug rows, deduplicated by InChIKey)
**Release date**: 20240621 (Last-Modified on server files)
**Note**: Available data is from 2023 mtADENet version. Full PersADE 2026 dataset (4M personalized associations with demographics) not yet available for bulk download.
**Wrapper required**: biothings-cli typer.rich_utils incompatibility — use `python3 /tmp/biothings_wrapper.py dataplugin <cmd>` (typer ≥0.26 monkey-patch)
