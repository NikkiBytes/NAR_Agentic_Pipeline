# SIGNOR 4.0 Plugin — Design Rationale

## Quick Stats
| Metric | Value |
|--------|-------|
| Source | `getData.php?organism=9606` |
| Source rows | 42,441 |
| Documents uploaded | 42,437 |
| Rows skipped | ~4 (no SIGNOR_ID or invalid format) |
| Deduplication | `seen_ids` set (none needed in practice — all IDs unique) |
| Target API | pending.api |
| Data format | TSV, plain text, no compression (~19.5 MB) |
| Release | 202604 (April 2026) |

---

## Why These Dump Files Were Chosen

**Chosen:** `https://signor.uniroma2.it/getData.php?organism=9606`

SIGNOR provides two families of download endpoints:

| Endpoint | Scope | Columns | SIGNOR_SCORE |
|----------|-------|---------|--------------|
| `getData.php?organism=9606` | All human causal interactions (42,441) | 28 (no header) | ✓ |
| `releases/getLatestRelease.php` | All organisms, quarterly snapshot (42,337 data rows) | 27 (with header) | ✗ |
| `PhosphoSIGNOR/apis/v1/…?role=all&format=tsv` | Phosphorylation only, paired rows (26,830) | 9 (with header) | ✓ |

`getData.php?organism=9606` was chosen because:
1. Human-specific — all 42,441 rows are taxid 9606 (or in vitro `-1`), no multi-organism noise.
2. Includes `SIGNOR_SCORE` (column 27), the most important quality signal from SIGNOR — absent from the quarterly release file.
3. Always returns the current live snapshot — no manual release URL update needed between quarters.

**Rejected:** `getLatestRelease.php` — lacks SIGNOR_SCORE; also covers all organisms requiring downstream filtering.

**Rejected:** PhosphoSIGNOR API (`?role=all&format=tsv`) — already covered by the prior v1.1 plugin; paired-row format would require merge logic; only captures phosphorylation/dephosphorylation (a subset of SIGNOR's causal mechanisms).

**Note on prior plugin:** The v1.1 PhosphoSIGNOR plugin (13,411 documents) is superseded by this plugin (42,437 documents), which includes all causal interaction types.

---

## Why the Parser Works the Way It Does

### _id strategy
`SIGNOR_ID` (column 26, e.g. `SIGNOR-203532`) is used as `_id`. It is:
- Globally unique per interaction within SIGNOR
- Stable across releases (same interaction keeps the same ID)
- Consistent with the prior v1.1 plugin's _id scheme

### No header row
`getData.php` returns plain TSV without a column header. Column positions are hardcoded in the `_COL` dict, derived from the official `Apr2026_release.txt` header row (27 columns) plus `SIGNOR_SCORE` at position 27.

### Document structure
All fields are nested under a top-level `signor` key per BioThings conventions. Entity A and Entity B are sub-objects under `signor.entity_a` and `signor.entity_b` to keep the interaction model clean:

```
{
  "_id": "SIGNOR-203532",
  "signor": {
    "signor_id": "SIGNOR-203532",
    "entity_a": {"name": "CDK9", "type": "protein", "id": "P50750", "database": "UNIPROT"},
    "entity_b": {"name": "POLR2A", "type": "protein", "id": "P24928", "database": "UNIPROT"},
    "effect": "up-regulates",
    "mechanism": "phosphorylation",
    "residue": "Ser1693",
    "sequence": "SPTSPSYsPTSPSYS",
    "tax_id": "9606",
    "pmid": "24385927",
    "direct": true,
    "sentence": "Cyclin-dependent kinase 9 (cdk9) promotes elongation...",
    "annotator": "lperfetto",
    "score": 0.779
  }
}
```

### BTO fields
`CELL_DATA` and `TISSUE_DATA` are semicolon-delimited BTO ontology IDs. The `_split_bto()` helper splits them into a list when multiple values are present, or returns a plain string for single values. `unlist()` then collapses single-item lists back to scalars.

### DIRECT field
Converted from the raw string `"t"/"f"` to Python `bool` for cleaner downstream filtering.

### SIGNOR_SCORE
Cast to `float`. Present in 100% of rows (no empty values observed).

### Rows skipped (~4)
Rows with no SIGNOR_ID or where SIGNOR_ID doesn't match the `SIGNOR-` prefix pattern are skipped. In practice this is < 0.01% of rows.

---

## Sample Output Documents

### Typical: Kinase–substrate phosphorylation with phosphosite
```json
{
  "_id": "SIGNOR-203532",
  "signor": {
    "signor_id": "SIGNOR-203532",
    "entity_a": {
      "name": "CDK9",
      "type": "protein",
      "id": "P50750",
      "database": "UNIPROT"
    },
    "entity_b": {
      "name": "POLR2A",
      "type": "protein",
      "id": "P24928",
      "database": "UNIPROT"
    },
    "effect": "up-regulates",
    "mechanism": "phosphorylation",
    "residue": "Ser1693",
    "sequence": "SPTSPSYsPTSPSYS",
    "tax_id": "9606",
    "pmid": "24385927",
    "direct": true,
    "annotator": "lperfetto",
    "sentence": "Cyclin-dependent kinase 9 (cdk9) promotes elongation by rna polymerase ii...",
    "score": 0.779
  }
}
```
Source cross-reference: https://signor.uniroma2.it/relation_result.php?id=SIGNOR-203532

### Edge case: Protein family → phenotype (no residue, with cell context)
```json
{
  "_id": "SIGNOR-262208",
  "signor": {
    "signor_id": "SIGNOR-262208",
    "entity_a": {
      "name": "ANXA3",
      "type": "protein",
      "id": "P12429",
      "database": "UNIPROT"
    },
    "entity_b": {
      "name": "Apoptosis",
      "type": "phenotype",
      "id": "SIGNOR-PH2",
      "database": "SIGNOR"
    },
    "effect": "down-regulates",
    "mechanism": "binding",
    "tax_id": "9606",
    "cell_data": ["BTO:0001109", "BTO:0000038"],
    "pmid": "30998268",
    "direct": false,
    "annotator": "miannu",
    "sentence": "ANXA3 downregulation evidently increased the apoptosis of HCT116 and SW480 cells...",
    "score": 0.9
  }
}
```
Source cross-reference: https://signor.uniroma2.it/relation_result.php?id=SIGNOR-262208

---

## Field Coverage (from inspect --limit 1000)

| Field | Coverage |
|-------|----------|
| `signor.signor_id` | 100% |
| `signor.entity_a.*` | 100% |
| `signor.entity_b.*` | 100% |
| `signor.effect` | 100% |
| `signor.mechanism` | 100% |
| `signor.score` | 100% |
| `signor.pmid` | 100% |
| `signor.direct` | 100% |
| `signor.sentence` | ~96.2% |
| `signor.annotator` | ~92.5% |
| `signor.residue` | ~32.3% (phospho/PTM interactions only) |
| `signor.sequence` | ~32.3% (paired with residue) |
| `signor.cell_data` | ~1.6% (cell line context where documented) |
| `signor.entity_a.complex_id` | ~0.3% (complex membership) |
| `signor.entity_b.complex_id` | ~0.3% |
| `signor.notes` | ~8.4% |

---

## Test Results Summary

| Step | Status | Notes |
|------|--------|-------|
| validate | ✓ PASS | `Valid Manifest: True` |
| dump | ✓ PASS | Version `202604`, file `getData.php?organism=9606` (19.5 MB) |
| upload | ✓ PASS | 42,437 documents in `signor_plugin` collection |
| list | ✓ PASS | Collection `signor_plugin` present, dump archive populated |
| inspect | ✓ PASS | All fields non-null; `_id` str; `direct` bool; `score` float; `cell_data` list-of-str; no warnings |
