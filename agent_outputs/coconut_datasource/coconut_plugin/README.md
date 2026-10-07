# COCONUT Plugin — Design Rationale

## 1. Why These Dump Files Were Chosen

COCONUT offers 6 download files on its canonical download page (<https://coconut.naturalproducts.net/download>):

- `coconut_csv-05-2026.zip` (207.9 MB) — **SELECTED** — full CSV with 44 columns: identifiers, molecular properties, chemical classification, NP classifier, organisms, collections, DOIs, synonyms, CAS
- `coconut_csv_lite-05-2026.zip` (191 MB) — REJECTED — lite CSV with only 4 columns (identifier, SMILES, InChI, InChIKey); strict subset of the full CSV
- `coconut_sdf_2d_lite-05-2026.zip` (287.6 MB) — REJECTED — SDF format not needed when CSV is available
- `coconut_sdf_2d-05-2026.zip` (691.7 MB) — REJECTED — SDF redundant with CSV
- `coconut_sdf_3d-05-2026.zip` (305.3 MB) — REJECTED — 3D coordinates not relevant for BioThings ingestion
- `coconut-dump-05-2026.sql` (31.91 GB) — REJECTED — SQL dump far too large; CSV covers the same entity data

**Decision**: Use the full CSV. It contains all identifier, property, classification, and provenance fields in a single flat file at 207.9 MB — manageable for streaming parse.

**v1.0 error corrected**: The original plugin (v1.0, 2026-05-14) used a Zenodo snapshot (`coconut-09-2024.csv.zip`) with only 4 columns and September 2024 data. This was a stale third-party mirror. The canonical COCONUT site (<https://coconut.naturalproducts.net/download>) has the full 44-column CSV with May 2026 data. Per the canonical-source-preference policy, the Zenodo URL was replaced.

## 2. Why the Parser Works the Way It Does

- **`_id` strategy**: InChIKey (`standard_inchi_key` column) — canonical for MyChem.info. Each row has a unique InChIKey.
- **Document structure**: Flat entity pattern with nested sub-objects for properties, classification, np_classifier, and xrefs.
- **Fields extracted**: All 44 columns mapped into structured groups:
  - Identifiers: coconut_id, inchi_key, inchi, smiles, name, iupac_name, molecular_formula
  - Properties: 20 numeric/boolean molecular descriptors (MW, alogp, TPSA, Lipinski, QED, etc.)
  - Classification: chemical class/subclass/superclass/direct_parent
  - NP Classifier: pathway, superclass, class, is_glycoside
  - Provenance: organisms (source species), collections (contributing databases), synonyms
  - Cross-references: CAS numbers, DOIs
- **Fields deliberately skipped**: None — all 44 columns are ingested. The murcko_framework SMILES is included as a string field.
- **Multi-value fields**: organisms, collections, dois, synonyms, cas are pipe-delimited in the CSV; parser splits on `|` into lists.
- **Type conversion**: Numeric fields converted to float/int; boolean fields to Python bool; empty strings to None.
- **Data cleaning**: `dict_sweep` removes None/empty values; `unlist` flattens single-item lists.
- **Filename handling**: Parser globs for `coconut_csv*.csv` since the inner filename changes per release (e.g., `coconut_csv-05-2026.csv`).

## 3. Test Results Summary

biothings-cli validation run: 2026-05-14

| Step | Command | Result |
|------|---------|--------|
| validate | `biothings-cli dataplugin validate` | PASSED — manifest valid, all required fields present |
| dump | `biothings-cli dataplugin dump` | PASSED — version.py returned `202605`, zip downloaded and extracted; inner file `coconut_csv-05-2026.csv` present |
| upload | `biothings-cli dataplugin upload` | PASSED — 728,421 documents ingested |
| list | `biothings-cli dataplugin list` | PASSED — `coconut_plugin` collection present in Dump and Upload state |
| inspect | `biothings-cli dataplugin inspect -s coconut_plugin --limit 1000` | PASSED — 1,001 sample docs: all `_id` are strings (27-char InChIKey), all `coconut.*` fields populated, `_none` = 0 for all fields, correct types (str/float/int/bool/list) |

**Key metrics:**

- CSV rows: 738,827
- Documents yielded: 728,421 (~10,406 rows skipped: missing or invalid InChIKey + 6 confirmed duplicate InChIKeys deduplicated via `seen_ids`)
- Sample `_id`: `VSNMVHSHIKKXDV-MDHKBZONSA-N`
- Top-level document keys: `_id`, `coconut`
- `coconut` sub-keys: `coconut_id`, `inchi_key`, `inchi`, `smiles`, `iupac_name`, `molecular_formula`, `properties`, `murcko_framework`, `classification`, `np_classifier`, `organisms`, `collections`, `synonyms`, `xrefs` (sparse fields absent when empty per `dict_sweep`)

**Parser fixes applied during validation:**

1. `version.py` line 23: regex contained unescaped double-quote inside double-quoted string — fixed to single-quoted raw string
2. `parser.py`: added `seen_ids` set to deduplicate at parser level (3 InChIKeys appear twice in the CSV; biothings SQLite `on_duplicates: error` raises on any duplicate)
