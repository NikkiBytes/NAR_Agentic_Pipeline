# TTD Plugin Design Rationale

## Quick Stats

```
Source rows:          ~42,938 drug entries in P1-02 (all clinical status levels)
Documents yielded:    42,938
Target API:           pending.api
Data format:          TXT, key-value row format (3-column: ENTITY_ID FIELD_NAME VALUE)
                      + 2-column blank-separated format (P1-05)
File sizes:           P1-02: 11.9 MB | P1-03: 5.7 MB | P1-05: 2.6 MB
Version (dump):       10.1.01_20240110  (v10.1.01, 2024-01-10)
CLI validation:       validate ✓ | dump ✓ | dump_and_upload ✓ | list ✓ | inspect ✓ (SQLite)
```

---

## Why These Dump Files Were Chosen

**Selected:**
- `P1-02-TTD_drug_download.txt` — Primary drug metadata: drug ID, company, therapeutic class,
  drug type, InChI/InChIKey/SMILES, highest clinical status. The anchor file; every document
  originates here.
- `P1-03-TTD_crossmatching.txt` — Cross-reference identifiers: PubChem CID, ChEBI, CAS number,
  ATC code. Provides machine-linkable IDs to MyChem.info and external registries.
- `P1-05-Drug_disease.txt` — Drug-disease associations with ICD-11 codes and clinical status.
  This is the primary novel value for BioThings: structured disease indications with the
  WHO ICD-11 coding system (absent from all existing BioThings MyChem/MyDisease sources).

**Not selected:**
- `P1-01-TTD_target_download.txt` — Contains target→drug reverse mappings (DRUGINFO field)
  but not a drug-centric format. Target data would require a separate target-keyed plugin.
  Excluded to keep scope clear and avoid parser complexity.
- `P1-04-Drug_synonyms.txt` (11.4 MB) — Drug synonyms already accessible via PubChem CID
  cross-reference. Excluded to reduce download volume; redundant given MyChem.info synonym
  coverage via PubChem.
- `P1-06-Target_disease.txt` — Target-disease associations belong in a target-centric plugin
  (UniProt-keyed). Excluded from this drug-centric plugin.
- `P1-08-Biomarker_disease.txt` — Biomarker-disease data; a separate entity type (biomarkers ≠
  drugs). Could be a standalone plugin.

---

## Why the Parser Works the Way It Does

### `_id` strategy
TTD Drug ID (e.g., `D00UZR`) as `_id`. Rationale:
- InChIKey would be ideal for MyChem.info mapping but is absent for ~41% of drugs (biologics,
  peptides, antibodies, experimental entries without resolved structures).
- TTD Drug ID is present on 100% of records and is the natural join key across all TTD files.
- The `ttd.inchikey` field provides the MyChem cross-reference for structure-resolved compounds.
- `pending.api` is appropriate here: documents span all clinical status levels and the primary
  value is the drug-target-disease relationship network, not just chemical structure data.

### Document structure
One document per drug (`_id = TTD Drug ID`), with:
- Drug metadata from P1-02 under `ttd.*`
- Cross-references under `ttd.xrefs.*`
- Disease indications list under `ttd.indications[]`

This is a denormalized drug-centric view. The target association layer (which protein targets
this drug) was not ingested in this iteration — see notes below.

### File parsing
TTD uses two distinct non-CSV formats:
- **P1-02 / P1-03**: 3-column entity-prefixed rows: `ENTITY_ID\tFIELD_NAME\tVALUE`. Blank lines
  are not required as entity separators because the entity ID (first column) naturally groups
  rows. Parser streams all rows and groups by entity ID using `defaultdict(list)`, then
  collapses single-element lists to scalars.
- **P1-05**: 2-column field-value rows: `FIELD_NAME\tVALUE[...]`, entities separated by blank
  lines. Parser tracks `current_id` from the `TTDDRUID` field and appends `INDICATI` rows as
  structured dicts.

### Company splitting
`DRUGCOMP` uses semicolon-delimited multiple companies (e.g., `"Onyx Pharmaceuticals; Pfizer"`).
Parser splits on `;` and strips whitespace to yield a list.

### `dict_sweep` + `unlist`
Standard BioThings helpers clean out None/empty-string values and flatten single-item lists
before yielding each document.

---

## Sample Output Documents

**Approved drug with full data:**
```json
{
  "_id": "D00UZR",
  "ttd": {
    "drug_id": "D00UZR",
    "name": "Ibrance",
    "company": ["Onyx Pharmaceuticals", "Pfizer"],
    "therapeutic_class": "Anticancer Agents",
    "drug_type": "Small molecular drug",
    "highest_status": "Approved",
    "inchikey": "AHJRHEGDXFFMBM-UHFFFAOYSA-N",
    "inchi": "1S/C24H29N7O2/...",
    "smiles": "CC1=C(C(=O)N(C2=NC(=NC=C12)NC3=NC=C(C=C3)N4CCNCC4)C5CCCC5)C(=O)C",
    "xrefs": {
      "pubchem_cid": 5330286,
      "chebi": "CHEBI:85993",
      "cas": "571190-30-2"
    },
    "indications": [
      {"disease": "Breast cancer", "icd11": "2C60-2C65", "status": "Approved"}
    ]
  }
}
```
Source record: https://db.idrblab.net/ttd/data/drug/details/d00uzr

**Approved drug with multiple indications:**
```json
{
  "_id": "DXP04H",
  "ttd": {
    "name": "Pirtobrutinib",
    "drug_type": "Small molecular drug",
    "highest_status": "Approved",
    "inchikey": "...",
    "xrefs": {"pubchem_cid": 130693905},
    "indications": [
      {"disease": "Non-hodgkin lymphoma", "icd11": "2B33.5", "status": "Approved"},
      {"disease": "Chronic lymphocytic leukaemia", "icd11": "2A82.0", "status": "Phase 3"},
      {"disease": "Small lymphocytic lymphoma", "icd11": "2A82.0", "status": "Phase 3"}
    ]
  }
}
```
Source record: https://db.idrblab.net/ttd/data/drug/details/dxp04h

---

## Field Coverage (random sample N=2000)

- `ttd.highest_status`: 100.0%
- `ttd.drug_type`: 69.7%
- `ttd.smiles`: 59.4%
- `ttd.xrefs.pubchem_cid`: 59.4%
- `ttd.inchikey`: 59.1%
- `ttd.inchi`: 59.1%
- `ttd.company`: 55.9%
- `ttd.indications`: 55.5%
- `ttd.xrefs.cas`: 29.3%
- `ttd.xrefs.chebi`: 13.4%
- `ttd.therapeutic_class`: 5.9%
- `ttd.xrefs.atc`: 5.5%
- `ttd.name` (trade name): 0.3%

Coverage notes:
- `smiles/inchikey/inchi` ~59%: the remaining 41% are biologics, antibodies, peptides, and
  experimental entries without resolved chemical structures.
- `name` (trade name) 0.3%: only drugs with officially approved trade names (TRADNAME field);
  the vast majority of 42,938 entries are investigational/experimental compounds.
- `indications` 55.5%: all 3,019 approved drugs have indications; investigational drugs vary.
- `therapeutic_class` 5.9%: sparsely populated in P1-02 — present mainly for approved drugs.

---

## Test Results Summary

| Step | Status | Notes |
|------|--------|-------|
| validate | ✓ PASS | Valid manifest, all required fields present |
| dump | ✓ PASS | Release 10.1.01_20240110; 3 files downloaded (11.9 MB + 5.7 MB + 2.6 MB) |
| dump_and_upload | ✓ PASS | 42,938 documents in 6.19s; no errors; err=None |
| list | ✓ PASS | Collection `ttd_plugin` present; upload status success |
| inspect | ✓ PASS (SQLite) | `_id` strings; `ttd` key in 100% of docs; no stray None values |

**Known issues:**
- `biothings-cli dataplugin inspect -s <name>` has arg-parsing bug in this CLI version —
  inspected via direct SQLite query instead (same data, identical result).
- This plugin ingests drug metadata + disease indications only. Target association data
  (drug→protein target + clinical status) requires a separate target-keyed plugin from P1-01.
- The 2026-paper-specific new data types (CMap/LINCS perturbation profiles, FDA label data,
  cytotoxic/antimicrobial activity landscapes) are NOT yet available in bulk download files.
  Monitor `ttd.idrblab.cn/full-data-download` for future file additions.
- Existing BioThings TTD plugin at `https://biothings.transltr.io/ttd` (v8.1.01, 2023) covers
  similar drug-target data. This plugin updates to v10.1.01 with ICD-11 annotations and uses
  the new canonical download domain (ttd.idrblab.cn).
