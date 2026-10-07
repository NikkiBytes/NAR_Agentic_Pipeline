# MeDIC Plugin — Design Rationale

## Quick Stats

| Metric | Value |
|--------|-------|
| Source rows | 3,857 drugs + 10,224 indication pairs + 3,981 contraindication pairs |
| Documents yielded | 4,652 |
| Rows skipped | ~4 (invalid/error drug IDs like `['Error']`) |
| Target API | MyChem.info |
| Primary key | Drug CURIE (e.g. `CHEBI:8327`, `UNII:N0A21N6RAU`) |
| Data format | TSV (drugList.tsv) + 2 XLSX files |
| Release | v2.3.1_v1.4.1 |

---

## Why These Dump Files Were Chosen

### Files included

**`drugList.tsv`** (matrix-drug-list v2.3.1) — 3,857 drug entries with:
- Cross-identifiers (CHEBI, UNII, PUBCHEM, RXCUI, DRUGBANK, ATC, InChIKey in 71%)
- Approval status flags (FDA/EMA/PMDA)
- Drug classification flags (radioisotope, allergen, steroid, antimicrobial, etc.)
- ATC codes (ATC classification hierarchy)

**`indicationList.xlsx`** (matrix-indication-list v1.4.1) — 10,224 curated drug-disease indication pairs from government regulatory sources (FDA 75.8%, EMA 9.2%, PMDA 14.9%) with MONDO-normalized disease IDs.

**`contraindicationList.xlsx`** (matrix-indication-list v1.4.1) — 3,981 curated drug-disease contraindication pairs with MONDO-normalized disease IDs and allergen/diagnostic flags.

### Files excluded

**Downfilled/inferred files** — `indicationList_downfilled.INFERRED.RELATIONSHIPS.BASED.ON.DISEASE.SUBTYPES.-.NOT.APPROVED.BY.ANY.GOVERNMENT.AGENCY.xlsx` and the contraindication equivalent. These contain ~302,000+ inferred relationships that are explicitly NOT approved by any government agency. Only curated government-regulatory source data is ingested.

**matrix-disease-list** — A disease ontology list (MONDO-focused). Different entity type; not drug-centric. Would be a separate pending.api or MyDisease.info plugin.

### Why `/releases/latest/` URLs
GitHub `releases/latest` redirects to the current version tag. This ensures the plugin always downloads the most recent data without requiring URL updates. The version.py queries the GitHub API to construct the exact version string for reproducibility.

---

## Why the Parser Works the Way It Does

### _id Strategy
**Drug CURIE** (e.g. `CHEBI:8327`) is used as `_id` rather than InChIKey.

Rationale:
1. **InChIKey is not a universal primary ID** for this dataset. Only 71% of drugs have an InChIKey in `alternate_ids`. The remaining 29% include biologics, combination therapies, and drug mixtures without single chemical structures.
2. **CHEBI is the plurality** identifier (55% of 3,857 drugs). CHEBI IDs are native to MyChem.info and map to chemical structures.
3. **Drug CURIE is globally unique** within the drug list and consistent across indications/contraindications tables.
4. The `alternate_ids` column contains the InChIKey for drugs that have one — stored in `medic.inchikey` for MyChem.info cross-referencing.

### Document Structure
```
{
  "_id": "CHEBI:8327",
  "medic": {
    "drug_id": "CHEBI:8327",
    "name": "Polythiazide",
    "combination_therapy": false,
    "atc_codes": "C03AA04",
    "atc_main": "C03AA04",
    "approval_status": {"usa": true, "eu": false, "japan": false},
    "inchikey": "MKXXBNJZFPGQKS-UHFFFAOYSA-N",
    "xrefs": {"chebi": "8327", "pubchem_cid": "4842", ...},
    "indications": [
      {"disease_id": "MONDO:0005009", "disease_label": "congestive heart failure", "sources": {"fda": true, "ema": false, "pmda": false}}
    ],
    "contraindications": [
      {"disease_id": "MONDO:0002476", "disease_label": "anuria", "is_allergen": false, "is_diagnostic_agent": false}
    ]
  }
}
```

### Multi-file Join Strategy
3-phase approach:
1. `_load_drug_list()` — builds drug metadata dict keyed by CURIE
2. `_load_indications()` — builds `defaultdict(list)` of indication records keyed by drug CURIE
3. `_load_contraindications()` — builds `defaultdict(list)` of contraindication records keyed by drug CURIE

Final `load_data()` iterates the union of all drug CURIEs and attaches lists.

### Data Cleaning Notes
- **ATC codes** stored as Python list literals in TSV (e.g. `"['A10BX02']"`) — parsed via `ast.literal_eval`, deduplicated, unlist flattens single-element lists
- **alternate_ids** contains duplicate entries (ingredients listed multiple times) — deduplicated via `dict.fromkeys()`
- **hyperrelations column** (large LLM-extracted JSON blobs, ~500KB per row) excluded from ingestion — too verbose, adds no cross-referenced value
- **Error drug IDs** (4 rows with `['Error']` as drug ID) skipped
- **is_allergen / is_diagnostic_agent** boolean fields in contraindicationList have trailing newlines — stripped

---

## Sample Output Documents

### Drug with indications, contraindications, InChIKey, ATC

```json
{
  "_id": "CHEBI:8327",
  "medic": {
    "drug_id": "CHEBI:8327",
    "name": "Polythiazide",
    "atc_codes": "C03AA04",
    "atc_main": "C03AA04",
    "combination_therapy": false,
    "approval_status": {"usa": true, "eu": false, "japan": false},
    "inchikey": "MKXXBNJZFPGQKS-UHFFFAOYSA-N",
    "xrefs": {"chebi": "8327", "pubchem_cid": "9678", "drugbank": "DB00774"},
    "indications": [
      {"disease_id": "MONDO:0005009", "disease_label": "congestive heart failure", "sources": {"fda": true, "ema": false, "pmda": false}},
      {"disease_id": "MONDO:0004920", "disease_label": "hypertension", "sources": {"fda": true, "ema": false, "pmda": false}}
    ],
    "contraindications": [
      {"disease_id": "MONDO:0002476", "disease_label": "anuria", "is_allergen": false, "is_diagnostic_agent": false}
    ]
  }
}
```
Source cross-reference: https://medic.renci.org/ (search "Polythiazide")

---

## Field Coverage (sample 1000 docs)

| Field | Coverage |
|-------|----------|
| `medic.drug_id` | 100% |
| `medic.name` | 83.6% |
| `medic.xrefs` | 83.6% |
| `medic.approval_status` | 83.6% |
| `medic.indications` | 51.9% |
| `medic.inchikey` | 58.9% |
| `medic.atc_codes` | 45.7% |
| `medic.contraindications` | 21.1% |

---

## Test Results Summary

| Step | Status | Notes |
|------|--------|-------|
| validate | PASS | All required manifest fields present |
| dump (version.py) | PASS | Returns `v2.3.1_v1.4.1` from GitHub API |
| upload (parser) | PASS | 4,652 unique drug documents |
| list | PASS | 4,652 docs in collection |
| inspect | PASS | `_id` = string drug CURIE; `medic` key 100% |

**Known limitations:**
- 29% of drugs lack InChIKey (biologics, combinations, mixtures) — drug CURIE used as _id
- `drug_name` field can contain repeated names ("EPINEPHRINE; EPINEPHRINE") from the source TSV's ingredient concatenation
- GitHub `/releases/latest/` redirect requires the downloader to follow HTTP 302 redirects (standard behavior)
- Downfilled/inferred relationship files excluded — contain ~302K inferred pairs not from government regulatory sources
