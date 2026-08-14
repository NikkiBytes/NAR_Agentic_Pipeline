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

## Mapping Overview

`mapping.py` (`get_customized_mapping`) was generated by running `parser.load_data()` against all 9 live-downloaded files and recursively inferring types from all 1,636 yielded documents (no sampling — full collection). No heterogeneous or conflicting fields were found across probes and competitors combined.

| Field | ES type | Notes |
|-------|---------|-------|
| `probe_id`, `competitor_id` | `keyword` | mutually exclusive by `entity_type` |
| `name`, `probe_type`, `entity_type` | `keyword` | short categorical/ID strings (avg `name` length 7.6 chars) |
| `inchi`, `smiles`, `iupac_name` | `keyword` | exact-match chemical identifiers, not full-text search targets (max `iupac_name` length 279 chars, still keyword — no free-text search requirement) |
| `properties.mw`, `.polar_area`, `.complexity`, `.xlogp` | `float` | |
| `properties.mf` | `keyword` | molecular formula string |
| `properties.heavy_atom_count`, `.hbond_donor`, `.hbond_acceptor`, `.rotatable_bonds` | `integer` | |
| `xrefs.pubchem`, `xrefs.synonyms` | `keyword` | |
| `experiments.*` (method_id, reference_id, criteria, concentrations, methods) | `keyword` | object — `unlist()` collapses single-experiment lists to a scalar object, so mapping uses object `properties`, not an array type |
| `experiments.cell.*` (cell_id, cell_name, model_type, disease, tissue, species, cellosaurus_accession) | `keyword` | nested object under `experiments` |

**Mapping Conflicts**: none. Every field observed across all 1,636 documents (603 probes, 1,033 competitors) had a single consistent Python type; no field required widening or was flagged for review.

**Validation**: `biothings-cli inspect --mode mapping` could not be run directly (see typer/biothings incompatibility below). Validated instead by writing a standalone script that recursively walks all 1,636 parsed documents, collects the observed Python type at every field path, and diffs that against `mapping.py`'s flattened `properties` — 0 missing fields, 0 type mismatches, 0 unused mapping entries (full pass).

---

## Associations / Relationships Represented

This plugin is a single-entity chemical record (probe or competitor compound), not an association-shaped API. The relationships below are the only ones that survived into the shipped documents — nested joins embedded at parse time, not standalone edges. There is no explicit `subject`/`object`/`relation` triple structure in this plugin.

| Subject | Predicate | Object | Source field(s) | Cardinality |
|---------|-----------|--------|------------------|-------------|
| Probe/competitor compound (`ChemicalEntity`, keyed by InChIKey) | tested in — no Biolink predicate mapping (closest: `biolink:related_to`) | Chemoproteomics experiment (not a modeled entity — embedded record, no its own ID exposed at top level) | `chemprob.experiments[]` (joined in-memory from `chemoproteomics_experiment.txt` by `probe_id`/`competitor_id`) | one-to-many (most probes have ≥1 experiment; some have 0) |
| Chemoproteomics experiment (embedded) | assayed in — no Biolink predicate mapping (closest: `biolink:occurs_in`) | Cell line/tissue (`Cell` / `GrossAnatomicalStructure`, via Cellosaurus) | `chemprob.experiments[].cell` (joined in-memory from `general_cell.txt` by `cell_id`) | one-to-one per experiment |
| Probe/competitor compound (`ChemicalEntity`) | has cross-reference — `biolink:same_as` (via PubChem CID) | PubChem compound (`ChemicalEntity`, external) | `chemprob.xrefs.pubchem` | one-to-one |

**Not represented despite being joined during parsing**: target metadata (`target_index`, built in-memory from `general_target_*.txt`, keyed by `target_id`) is used only to support index-building internals and is **not embedded in any shipped document** — so no probe/competitor → protein-target relationship actually exists in this API. Similarly, the excluded `chemoproteomics_enzyme.txt` / `chemoproteomics_other.txt` files (see "Why These Dump Files Were Chosen") would have carried the probe–target binding-ratio relationship, but since those files are not ingested, that edge is not present here — a future `pending.api` plugin keyed by probe-target pairs would be the place to expose it.

---

## Test Results Summary

| Step | Status | Notes |
|------|--------|-------|
| validate | PASS | Valid manifest, all required fields present, `uploader.mapping` wired to `mapping:get_customized_mapping` |
| dump | PASS (manual) | 9 files downloaded directly via `curl -A "Mozilla/5.0"` (biothings-cli blocked, see below); sizes match manifest expectations |
| upload | PASS (direct parser run) | 1,636 documents from `parser.load_data()`, 0 duplicate `_id`s |
| list | PASS (direct parser run) | 1,636 unique InChIKeys (603 probe, 1,033 competitor) |
| inspect | PASS (direct parser run) | _id: str (27 chars, InChIKey), no None values after `dict_sweep`/`unlist` |
| inspect --mode mapping | PASS (manual diff, see Mapping Overview) | 0 missing fields, 0 type mismatches vs `mapping.py` across all 1,636 docs |

**Document count**: 1,636 (603 probes + 1,033 unique-InChIKey competitors)
**biothings-cli blocked in this sandbox**: `AttributeError: module 'typer' has no attribute 'rich_utils'` (typer ≥0.26 / biothings 1.0.2 incompatibility — same known issue logged for other plugins in `built-plugins-index.md`; shared environment not patched). All CLI steps above were instead validated by directly downloading the source files and calling `parser.load_data()` / a standalone mapping-diff script.
**Note**: Quantitative binding ratio files (chemoproteomics_enzyme.txt 924MB, chemoproteomics_other.txt 852MB) NOT ingested in this plugin — they contain 2.1M binding ratio records and are better suited to a separate pending.api plugin keyed by probe-target pair.
