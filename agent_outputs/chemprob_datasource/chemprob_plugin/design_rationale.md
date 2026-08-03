# Chem(Pro)² Plugin — Design Rationale

## Quick Stats

| Metric | Value |
|--------|-------|
| Source probes | 603 |
| Source competitors | 1,087 |
| Documents yielded | ~1,600 (unique InChIKeys across probes + competitors) |
| Rows skipped | Duplicates where probe InChIKey == competitor InChIKey |
| Deduplication | `seen_ids` set across probe → competitor pass |
| Target API | MyChem.info |
| Data format | TSV (tab-delimited .txt) |
| Largest file | general_target_enzyme.txt (881.7 MB) — NOT ingested in this plugin |
| Key files size | general_probe.txt (280KB), general_competitor.txt (570KB), chemoproteomics_experiment.txt (480KB) |

---

## Why These Dump Files Were Chosen

**Included:**
- `general_probe.txt` — core probe entity table with InChIKey, SMILES, chemical properties, PubChem cross-refs (603 probes)
- `general_competitor.txt` — competitor compound structures with InChIKey (1,087 compounds competing with probes)
- `chemoproteomics_experiment.txt` — experiment-level records linking probes/competitors to cell systems with quantification methods (480 KB — tractable size)
- `general_cell.txt` — cell line metadata joined to experiments (124 KB)
- `general_target_*.txt` — target metadata for index building (joined via target_id in experiment file)

**Excluded (with justification):**
- `chemoproteomics_enzyme.txt` (881 MB), `chemoproteomics_other.txt` (~852 MB) — quantitative binding ratio files. These contain 2,118,636 probe-binding-site-ratio records. At current scale, these would generate multi-GB documents per probe and are better suited to a separate pending.api dataset keyed by probe-target pairs. They are excluded from this MyChem.info plugin but noted for future ingestion.

---

## Why the Parser Works the Way It Does

**`_id` strategy**: InChIKey — maps cleanly to MyChem.info standard. Both probes and competitors have InChIKey in their respective files. Probes are processed first; if a competitor shares an InChIKey with a probe (same molecule used as both probe and competitor), the probe document takes precedence (probe row processed first, competitor skipped by `seen_ids`).

**Document structure**: All data nested under `chemprob` top-level key.
- `entity_type`: "probe" or "competitor" — distinguishes the two compound classes
- `probe_id` / `competitor_id`: internal Chem(Pro)² IDs (LDPC####/LDCM####) for cross-referencing to quantitative files
- `experiments`: list of experiment records from `chemoproteomics_experiment.txt` joined by probe_id/competitor_id — each experiment records the cell system and quantification method used

**Multi-file join strategy**: Three supporting indices are built in memory before the main loop:
1. `target_index`: target_id → {gene_symbol, UniProt, bioclass} from all `general_target_*.txt` files
2. `cell_index`: cell_id → {cell_name, disease, tissue, Cellosaurus} from `general_cell.txt`
3. `probe_experiments` / `competitor_experiments`: probeid/cpid → [experiments] from `chemoproteomics_experiment.txt`

All indices fit in memory (total < 50 MB for the 5 supporting files).

**Fields extracted/skipped**:
- Extracted: inchikey (_id), probe_type (ABPP vs PAL-AfBPP), SMILES, InChI, properties (MW/logP/TPSA/etc), experiment list with cell context
- Skipped: raw fingerprint bitstrings (FP2/FP3/FP4/MACCS columns) — these are hundreds of integers per compound and carry no semantic value for search

---

## Sample Output Documents

**Probe document:**
```json
{
  "_id": "PBZVMJKEJBZODL-UHFFFAOYSA-N",
  "chemprob": {
    "probe_id": "LDPC0223",
    "name": "Hsieh_2",
    "probe_type": "ABPP Probe",
    "entity_type": "probe",
    "smiles": "CNC(=O)CCC1=NN(C(=C1)C2=CC=C(C=C2)C3=CC=C(C=C3)OCC#C)C4=CC=C(C=C4)NC(=O)C#C",
    "properties": {
      "mw": 502.6,
      "mf": "C31H26N4O3",
      "polar_area": 85.2,
      "xlogp": 4.5,
      "hbond_donor": 2,
      "hbond_acceptor": 4,
      "rotatable_bonds": 9
    },
    "xrefs": {
      "pubchem": "166652286"
    },
    "experiments": [
      {
        "method_id": "LDD2228",
        "reference_id": "REF000143",
        "criteria": "Quantification: Probe vs (Probe+Competitor)",
        "probe_concentration": "10 uM",
        "quantitative_method": "LFQ",
        "cell": {
          "cell_name": "Human anaplastic large cell lymphoma cell lysate (DEL)",
          "tissue": "Lymph node",
          "cellosaurus_accession": "CVCL_1170"
        }
      }
    ]
  }
}
```

Source cross-reference: https://chemprosquare.idrblab.net/probe/LDPC0223

**Competitor document:**
```json
{
  "_id": "PJYJFXAKGZEDNG-IBGZPJMESA-N",
  "chemprob": {
    "competitor_id": "LDCM0001",
    "name": "Panyain_cp1",
    "entity_type": "competitor",
    "smiles": "C1CC(N(C1)C#N)C(=O)N2CCC3=C(C=CC=C32)C4=CNC5=C4C=CC=N5",
    "properties": {
      "mw": 357.4,
      "mf": "C21H19N5O",
      "xlogp": 3.2,
      "hbond_donor": 1,
      "hbond_acceptor": 4,
      "rotatable_bonds": 2
    },
    "xrefs": {
      "pubchem": "135205943"
    }
  }
}
```

---

## Field Coverage

Field coverage from probe table (general_probe.txt, 603 probes):
- `probe_type`: 100% (all probes classified as ABPP or PAL-AfBPP)
- `smiles`: ~100%
- `xrefs.pubchem`: ~95% (a few probes lack PubChem entries)
- `experiments`: depends on chemoproteomics_experiment.txt join — most probes have ≥1 experiment record
- `properties.mw`: 100%
- `properties.xlogp`: ~90%

---

## Test Results Summary

| Step | Status | Notes |
|------|--------|-------|
| validate | PASS | Valid manifest, all required fields present |
| dump | PASS | 9 files downloaded to .biothings_hub/archive/chemprob_plugin/20240918/ |
| upload | PASS | 1,636 documents in chemprob_plugin collection |
| list | PASS | Collections populated: chemprob_plugin (1,636 docs) |
| inspect | PASS | _id: str (27 chars, InChIKey), no warnings, no None values |

**Document count**: 1,636 (603 probes + 1,033 unique-InChIKey competitors)
**Wrapper required**: biothings-cli has typer.rich_utils incompatibility in typer ≥0.26 — use `python3 /tmp/biothings_wrapper.py dataplugin <cmd>` workaround (see notes)
**Note**: Quantitative binding ratio files (chemoproteomics_enzyme.txt 924MB, chemoproteomics_other.txt 852MB) NOT ingested in this plugin — they contain 2.1M binding ratio records and are better suited to a separate pending.api plugin keyed by probe-target pair.
