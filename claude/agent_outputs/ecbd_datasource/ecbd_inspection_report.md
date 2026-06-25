# ECBD — Site Inspection Report

**Datasource**: European Chemical Biology Database (ECBD)  
**Inspected**: 2026-05-14 | **Status**: VERIFIED  

---

## Download File Inventory

| File | Rows | Size | Relationship | Decision |
|------|------|------|--------------|----------|
| `bioactives.csv` | 2,464 | 0.87 MB | INDEPENDENT | ✅ INGEST |
| `fragments.csv` | 1,056 | 0.25 MB | INDEPENDENT | ✅ INGEST |
| `nuisance_set.csv` | 88 | 0.05 MB | INDEPENDENT | ✅ INGEST |
| `academic.csv` | 6,688 | 1.1 MB | INDEPENDENT | ✅ INGEST |
| `diverse_library.csv` | 98,560 | 30.8 MB | INDEPENDENT | ✅ INGEST |
| `ecbd_all.csv` | 108,768 | 19.5 MB | SUPERSET | ❌ SKIP (54 fewer rows; no sub-library tagging) |
| `representative_diverse_set.csv` | 2,464 | 0.4 MB | SUBSET of diverse_library | ❌ SKIP |
| `pilot_library.csv` | 5,016 | 0.8 MB | COMPOSITE subset | ❌ SKIP |
| `mini_fragments.csv` | 88 | 0.02 MB | SUBSET of fragments | ❌ SKIP |

**Total unique InChIKeys across 5 selected files**: 108,822  
**Cross-file duplicates**: 34 (handled by `seen_ids` deduplication in parser)

---

## Schema (all 5 files — identical 16-column CSV)

```
eos, smiles, inchi, inchikey, formula, mw, hba, hbd, tpsa, rb, fp3, logp, violates_ro5, pubchem, chembl, zinc
```

| Field | Type | Sample | BioThings Classification |
|-------|------|--------|--------------------------|
| `eos` | string | `EOS100001` | IDENTIFIER — EU-OPENSCREEN persistent ID (novel) |
| `smiles` | string | `CC[C@]1(O)...` | NOVEL |
| `inchi` | string | `InChI=1S/...` | NOVEL |
| `inchikey` | string | `AQTQHPDCURKLKT-PNYVAJAMSA-N` | **_id** (MyChem.info standard) |
| `formula` | string | `C46H58N4O14S` | NOVEL |
| `mw` | float | `923.051` | NOVEL |
| `hba` | int | `18` | NOVEL (hydrogen bond acceptors) |
| `hbd` | int | `5` | NOVEL (hydrogen bond donors) |
| `tpsa` | float | `245.77` | NOVEL (topological polar surface area) |
| `rb` | int | `8` | NOVEL (rotatable bonds) |
| `fp3` | float | `0.565` | NOVEL (FP3 fingerprint — not in other sources) |
| `logp` | float | `2.865` | NOVEL |
| `violates_ro5` | int (0/1) | `1` | NOVEL (Lipinski RO5 flag) |
| `pubchem` | string | `CID5388992` | REDUNDANT (already in MyChem) |
| `chembl` | string | `CHEMBL710` | REDUNDANT (already in MyChem) |
| `zinc` | string | `ZINC000003782599` | REDUNDANT (already in MyChem) |

**Derived field**: `sub_library` — assigned from filename stem (bioactives, fragments, nuisance, academic, diverse)

---

## Paper vs Reality

| Claim (paper, Aug 2024) | Observed (May 2026) | Match |
|-------------------------|----------------------|-------|
| 107,414 total compounds | 108,822 unique InChIKeys | Close — library grown |
| 5,280 academic compounds | 6,688 in academic.csv | Grown by 1,408 |
| CC BY 4.0 license | CC BY 4.0 confirmed | ✅ |
| CSV bulk downloads | 5 CSVs + superset/subsets all HTTP 200 | ✅ |

---

## Ingestion Path

- **Strategy**: Bulk download (5 CSV files)
- **Primary key**: `inchikey` → `_id`
- **Target API**: MyChem.info
- **SSL note**: ecbd.eu uses a self-signed TLS certificate — `biothings-cli dataplugin dump` will fail SSL verification. Files must be pre-downloaded via `curl --insecure` and dump registered manually.
- **File processing order**: bioactives → fragments → nuisance_set → academic → diverse_library

---

## Plugin Inputs Summary

```json
{
  "data_url": [
    "https://ecbd.eu/static/core/compounds/bioactives.csv",
    "https://ecbd.eu/static/core/compounds/fragments.csv",
    "https://ecbd.eu/static/core/compounds/nuisance_set.csv",
    "https://ecbd.eu/static/core/compounds/academic.csv",
    "https://ecbd.eu/static/core/compounds/diverse_library.csv"
  ],
  "primary_key": "inchikey",
  "target_api": "MyChem.info",
  "expected_docs": 108822
}
```
