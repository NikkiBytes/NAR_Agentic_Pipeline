# ECBD — Relevancy Analysis Report

**Datasource**: European Chemical Biology Database (ECBD)  
**Homepage**: https://ecbd.eu  
**Article**: "ECBD: European chemical biology database." — *Nucleic Acids Research* 2025, Vol 53 D1, D1383–D1392  
**DOI**: [10.1093/nar/gkae904](https://doi.org/10.1093/nar/gkae904) | **PMID**: 39441065 | **PMC**: PMC11701612  
**Evaluated**: 2026-05-14  

---

## Verdict: RECOMMEND_INGEST

| Dimension | Score | Status |
|-----------|-------|--------|
| Relevance | 5 / 5 | ✓ Directly aligned |
| Novelty   | 3 / 5 | ✓ Meaningful new data |
| Openness  | 4 / 5 | PASS — CC BY 4.0 |

---

## What ECBD Is

According to PubMed ([DOI: 10.1093/nar/gkae904](https://doi.org/10.1093/nar/gkae904)), the European Chemical Biology Database (ECBD) is the central repository for the EU-OPENSCREEN research infrastructure — a 31-partner-site European consortium providing molecular screening and chemistry support. It houses:

- **107,414 small molecule compounds** across three libraries:
  - ECBL (European Chemical Biology Library): 98,560 diversity + 2,464 bioactives + 88 nuisance compounds
  - EFSL (European Fragment Screening Library): 1,056 fragments
  - EACL (European Academic Compound Library): 5,280 academic compounds
- **89 bioassay datasets** (48 public as of Aug 2024), ~4.3 million experimental data points
- All data under **CC BY 4.0 license**

---

## BioThings Sphere Relevance (5/5)

ECBD is directly aligned with **MyChem.info**:

- **Primary identifier**: InChIKey (MyChem standard `_id`)
- **Compound fields available**: SMILES, InChI, molecular formula, MW, HBA, HBD, TPSA, rotatable bonds, FP3 fingerprint value, LogP, Lipinski RO5 flag
- **Cross-references**: PubChem CID, ChEMBL ID, ZINC ID
- **Additional identifiers**: EU-OPENSCREEN EOS persistent IDs (unique to ECBD)

---

## Novelty vs Existing BioThings (3/5)

| Component | Status | Notes |
|-----------|--------|-------|
| Compound structures (ECBL diversity) | REDUNDANT | Commercially sourced — high overlap with ChEMBL/PubChem/ZINC |
| Compound structures (EACL academic) | NOVEL | European academic compounds not in major public databases |
| EOS persistent identifiers | NOVEL | EU-OPENSCREEN internal IDs not in any BioThings API |
| Sub-library membership flags | NOVEL | Diversity/bioactives/nuisance/fragments/academic classification |
| FP3 fingerprint + violates_ro5 | NOVEL | Not standardly in existing MyChem sources |
| QC data (purity, identity) | NOVEL | Available via compound detail pages (not in bulk CSV) |
| Bioassay activity data | OUT OF SCOPE | Bioassay data → pending.api, not MyChem; not in bulk compound CSV |

---

## Openness Assessment (PASS, 4/5)

- ✅ CC BY 4.0 license (stated in paper and site)
- ✅ Direct CSV download URLs — no login, no API key required
- ✅ Five sub-library files publicly accessible (HTTP 200 confirmed)
- ⚠️ ecbd.eu uses a **self-signed TLS certificate** — `curl -k` / `verify=False` required

**Verified download URLs:**

| File | Size | Content |
|------|------|---------|
| `bioactives.csv` | 875 KB | 2,464 bioactive compounds |
| `fragments.csv` | 254 KB | 1,056 fragment compounds |
| `nuisance_set.csv` | ~50 KB | 88 nuisance compounds |
| `academic.csv` | ~1 MB | 5,280 academic compounds |
| `diverse_library.csv` | 30.8 MB | 98,560 diversity compounds |

---

## Risks

1. Self-signed TLS certificate on ecbd.eu — requires workaround for biothings-cli dump
2. Structural overlap with ChEMBL/PubChem/ZINC for diversity library compounds
3. No versioning in download URL filenames — version detection requires homepage scrape

---

## Recommended Next Steps

1. **Stage 2 — Site Inspection**: Confirm all 5 CSV column schemas, sample data, verify file relationships (independent vs subset)
2. **Stage 3 — Plugin Generation**: Write MyChem.info plugin with InChIKey `_id`, targeting 5 independent sub-library CSV files
