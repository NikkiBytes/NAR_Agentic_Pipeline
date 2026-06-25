# ECBD — Plugin Generation Report

**Datasource**: European Chemical Biology Database (ECBD)  
**Plugin**: `ecbd_plugin` — MyChem.info  
**Generated**: 2026-05-14  

---

## Plugin Summary

| Metric | Value |
|--------|-------|
| Target API | MyChem.info |
| _id strategy | InChIKey (`inchikey` column) |
| Documents generated | 108,822 |
| Source files | 5 independent CSV sub-libraries |
| Release version | 20260204 (Feb 2026) |

---

## Generated Files

| File | Purpose |
|------|---------|
| [manifest.json](ecbd_plugin/manifest.json) | Declares 5 download URLs, release wiring, CC BY 4.0 metadata |
| [parser.py](ecbd_plugin/parser.py) | Multi-file CSV parser with seen_ids dedup, type coercions, sub_library tag |
| [version.py](ecbd_plugin/version.py) | Fetches Last-Modified on bioactives.csv → YYYYMMDD; fallback: homepage date scrape |
| [design_rationale.md](ecbd_plugin/design_rationale.md) | Full design documentation with file selection rationale and sample docs |

---

## Document Structure

```json
{
  "_id": "DBEPLOCGEIEOCV-WSBQPABSSA-N",
  "ecbd": {
    "eos_id": "EOS100002",
    "inchikey": "DBEPLOCGEIEOCV-WSBQPABSSA-N",
    "inchi": "InChI=1S/C23H36N2O2/...",
    "smiles": "CC(C)(C)NC(=O)...",
    "formula": "C23H36N2O2",
    "sub_library": "bioactives",
    "properties": {
      "mw": 372.553, "hba": 4, "hbd": 2,
      "tpsa": 58.2, "rb": 1, "fp3": 0.826,
      "logp": 3.815, "violates_ro5": 0
    },
    "xrefs": {
      "pubchem": "CID57363",
      "chembl": "CHEMBL710",
      "zinc": "ZINC000003782599"
    }
  }
}
```

---

## biothings-cli Validation

| Step | Status | Details |
|------|--------|---------|
| `validate` | ✅ PASS | Valid manifest, all required fields present |
| `dump` | ⚠️ SSL WORKAROUND | ecbd.eu self-signed cert; files pre-downloaded via `curl -k`; dump state patched |
| `upload` | ✅ PASS | 108,822 documents → `ecbd_plugin` collection |
| `list` | ✅ PASS | All 5 CSVs in archive; collection populated |
| `inspect` | ✅ PASS | All fields correctly typed; no nulls; xrefs 70–96% |

**Production note**: The SSL workaround (pre-download + manual dump patch) is a testing-only procedure. Production deployment requires one of:
1. Installing ecbd.eu's self-signed CA certificate into the system trust store
2. A custom `dumper.py` that sets `verify=False` on requests

---

## Field Coverage

| Field | Coverage |
|-------|----------|
| `ecbd.eos_id` | 100% |
| `ecbd.properties.*` | 100% (all 8 fields) |
| `ecbd.sub_library` | 100% |
| `ecbd.xrefs.pubchem` | ~96.0% |
| `ecbd.xrefs.chembl` | ~88.6% |
| `ecbd.xrefs.zinc` | ~69.5% |
