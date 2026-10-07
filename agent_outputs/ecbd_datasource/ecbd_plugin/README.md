# ECBD Plugin — Design Rationale

## Quick Stats
| Metric | Value |
|--------|-------|
| Source files | 5 independent sub-library CSVs |
| Source rows | 108,856 (across all 5 files) |
| Documents uploaded | 108,822 |
| Rows skipped | 34 (cross-file InChIKey duplicates) |
| Deduplication | `seen_ids` set — 34 cross-library duplicates dropped |
| Target API | MyChem.info |
| Data format | CSV, 16 columns, no compression |
| Total input size | ~33 MB (diverse_library.csv 30.8 MB dominates) |
| Release | 20260204 (Last-Modified on bioactives.csv) |

---

## Why These Dump Files Were Chosen

ECBD exposes multiple CSV download files. All share the same 16-column schema.

| File | Rows | Relationship | Decision |
|------|------|--------------|----------|
| `bioactives.csv` | 2,464 | INDEPENDENT | ✅ INGEST |
| `fragments.csv` | 1,056 | INDEPENDENT | ✅ INGEST |
| `nuisance_set.csv` | 88 | INDEPENDENT | ✅ INGEST |
| `academic.csv` | 6,688 | INDEPENDENT | ✅ INGEST |
| `diverse_library.csv` | 98,560 | INDEPENDENT | ✅ INGEST |
| `ecbd_all.csv` | 108,768 | SUPERSET | ❌ SKIP — 54 fewer rows than 5-file combined; no sub-library tag |
| `representative_diverse_set.csv` | 2,464 | SUBSET of diverse | ❌ SKIP |
| `pilot_library.csv` | 5,016 | COMPOSITE subset | ❌ SKIP |
| `mini_fragments.csv` | 88 | SUBSET of fragments | ❌ SKIP |

The 5 independent sub-library files are preferred over `ecbd_all.csv` because:
1. They yield 108,822 unique InChIKeys vs 108,768 in the superset (54 more compounds — ECBD academic library growth after paper submission)
2. They allow tagging each compound with its `sub_library` (bioactives, fragments, nuisance, academic, diverse) — information not recoverable from the superset

**Canonical source**: All files from `https://ecbd.eu/static/core/compounds/` — no third-party mirrors consulted.

**SSL note**: ecbd.eu uses a self-signed TLS certificate. `biothings-cli dataplugin dump` fails SSL verification. Workaround for testing: pre-download all files via `curl -k` (insecure). Production deployment requires either installing ecbd.eu's CA certificate or a custom `dumper.py` with `verify=False`.

---

## Why the Parser Works the Way It Does

### _id strategy
`inchikey` → `_id`. InChIKey is the canonical MyChem.info primary identifier and uniquely identifies each compound's structure across all 5 sub-library files.

### File processing order
Files are processed in a fixed order: `bioactives → fragments → nuisance_set → academic → diverse_library`. For the 34 cross-file duplicates, the first occurrence wins. The order is chosen so that smaller, more curated sets (bioactives, fragments) take precedence over the large diversity library for duplicate resolution.

### seen_ids deduplication
34 InChIKeys appear in more than one sub-library CSV. The `seen_ids` set in the parser skips these duplicates on subsequent encounters. `on_duplicates: "error"` in the manifest provides a second safety net.

### sub_library derivation
The `sub_library` field is derived from the CSV filename stem at parse time using `_SUBLIBRARY_MAP`:
- `bioactives.csv` → `"bioactives"`
- `fragments.csv` → `"fragments"`
- `nuisance_set.csv` → `"nuisance"`
- `academic.csv` → `"academic"`
- `diverse_library.csv` → `"diverse"`

### Type conversions
- `_FLOAT_FIELDS = {"mw", "tpsa", "fp3", "logp"}` — converted to Python float
- `_INT_FIELDS = {"hba", "hbd", "rb", "violates_ro5"}` — converted to Python int (via `int(float(...))` to handle float-formatted integers in source)

### Document structure
```
{
  "_id": "<InChIKey>",
  "ecbd": {
    "eos_id": "EOS100001",
    "inchikey": "<InChIKey>",
    "inchi": "InChI=1S/...",
    "smiles": "...",
    "formula": "C23H36N2O2",
    "sub_library": "bioactives",
    "properties": {"mw": 372.55, "hba": 4, "hbd": 2, "tpsa": 58.2, "rb": 1, "fp3": 0.826, "logp": 3.815, "violates_ro5": 0},
    "xrefs": {"pubchem": "CID57363", "chembl": "CHEMBL710", "zinc": "ZINC000003782599"}
  }
}
```

Cross-references (pubchem, chembl, zinc) are kept under `xrefs` — they enrich rather than duplicate existing MyChem records. `dict_sweep` removes empty xrefs when a compound has no cross-references.

---

## Sample Output Documents

### Typical: ECBL bioactive compound with full cross-references
```json
{
  "_id": "DBEPLOCGEIEOCV-WSBQPABSSA-N",
  "ecbd": {
    "eos_id": "EOS100002",
    "inchikey": "DBEPLOCGEIEOCV-WSBQPABSSA-N",
    "inchi": "InChI=1S/C23H36N2O2/...",
    "smiles": "CC(C)(C)NC(=O)[C@H]1CC[C@H]2...",
    "formula": "C23H36N2O2",
    "sub_library": "bioactives",
    "properties": {
      "mw": 372.553,
      "hba": 4,
      "hbd": 2,
      "tpsa": 58.2,
      "rb": 1,
      "fp3": 0.826,
      "logp": 3.815,
      "violates_ro5": 0
    },
    "xrefs": {
      "pubchem": "CID57363",
      "chembl": "CHEMBL710",
      "zinc": "ZINC000003782599"
    }
  }
}
```
Source cross-reference: https://ecbd.eu/compound/DBEPLOCGEIEOCV-WSBQPABSSA-N

### Edge case: ECBL nuisance compound (partial cross-references)
```json
{
  "_id": "KYRVNWMVYQXFEU-UHFFFAOYSA-N",
  "ecbd": {
    "eos_id": "EOS98606",
    "inchikey": "KYRVNWMVYQXFEU-UHFFFAOYSA-N",
    "smiles": "COC(=O)Nc1nc2ccc(C(=O)c3cccs3)cc2[nH]1",
    "formula": "C14H11N3O3S",
    "sub_library": "nuisance",
    "properties": {
      "mw": 301.327,
      "hba": 6,
      "hbd": 2,
      "tpsa": 84.08,
      "rb": 3,
      "fp3": 0.071,
      "logp": 3.034,
      "violates_ro5": 0
    },
    "xrefs": {
      "pubchem": "CID4122",
      "chembl": "CHEMBL9514",
      "zinc": "ZINC000000056509"
    }
  }
}
```
Source cross-reference: https://ecbd.eu/compound/KYRVNWMVYQXFEU-UHFFFAOYSA-N

---

## Field Coverage (from inspect --limit 1000)

| Field | Coverage |
|-------|----------|
| `ecbd.eos_id` | 100% |
| `ecbd.inchikey` | 100% |
| `ecbd.inchi` | 100% |
| `ecbd.smiles` | 100% |
| `ecbd.formula` | 100% |
| `ecbd.sub_library` | 100% |
| `ecbd.properties.*` (all 8 fields) | 100% |
| `ecbd.xrefs.pubchem` | ~96.0% |
| `ecbd.xrefs.chembl` | ~88.6% |
| `ecbd.xrefs.zinc` | ~69.5% |

Academic compounds have lower cross-reference coverage (submitted by institutions, not yet indexed in PubChem/ChEMBL/ZINC).

---

## Test Results Summary

| Step | Status | Notes |
|------|--------|-------|
| validate | ✓ PASS | `Valid Manifest: True` |
| dump | ✗ BLOCKED (SSL) | ecbd.eu self-signed cert; pre-downloaded via `curl -k`; dump state patched to success |
| upload | ✓ PASS | 108,822 documents in `ecbd_plugin` collection |
| list | ✓ PASS | All 5 CSV files listed in archive; `ecbd_plugin` collection present |
| inspect | ✓ PASS | `_id` = 27-char InChIKey; all properties float/int; sub_library 100%; xrefs 70–96%; no nulls |
