# Evaluation Checklist

Reference material for consistent datasource evaluations.
Load this file when performing novelty comparisons or when unsure about scoring.

## Known BioThings API Data Sources (for novelty comparison)

### MyChem.info (chemical/drug)
- DrugBank, ChEMBL, PubChem, ChEBI, SIDER, AEOLUS
- UniII (UNII), NDC, PharmGKB, DGIdb
- FDA drug labels, clinical trials annotations

### MyGene.info (gene)
- NCBI Gene (Entrez), Ensembl, UniProt
- GO annotations, InterPro, Reactome, KEGG
- HGNC, MGI, RGD, OMIM (gene-level)

### MyDisease.info (disease)
- MONDO, Disease Ontology, OMIM (disease-level)
- DisGeNET, HPO, CTD (disease-chemical/gene)
- Orphanet, GARD

### MyVariant.info (variant)
- ClinVar, dbSNP, gnomAD, ExAC
- COSMIC, CADD, DANN, dbNSFP
- ClinGen, PharmGKB (variant-level)

### pending.api / All other Biothings API
- Sources in active evaluation or staging
- Check https://biothings.ci.transltr.io/ for current list

## Relevance Scoring Guide

Ask these questions (yes = +1 toward score):
1. Does it map to a core BioThings entity type (gene, chemical, disease, variant)?
2. Does it use standard biomedical identifiers (HGNC, ChEMBL, MONDO, dbSNP, etc.)?
3. Does it provide relationships between BioThings entity types?
4. Is it structured/tabular (not just free-text/PDF)?
5. Is it actively maintained (updated within last 2 years)?

## Novelty Scoring Guide

Ask these questions:
1. Does it cover entity types or relations not in existing BioThings sources?
2. Does it add new annotation fields to existing entities?
3. Does it offer better coverage (more entities) than existing overlapping sources?
4. Does it provide fresher data or more frequent updates?
5. Does it add provenance, evidence codes, or confidence scores missing elsewhere?

## Openness Scoring Guide

Check each item:
1. [ ] Public download URL exists (no login wall)
2. [ ] No API key required for bulk download
3. [ ] License explicitly named and linked
4. [ ] License permits redistribution (CC0, CC-BY, MIT, Apache, etc.)
5. [ ] No click-through agreement or manual request process
6. [ ] Terms do not prohibit derivative works or integration

### Common License Verdicts
- **CC0 / Public Domain**: PASS (5/5)
- **CC-BY 4.0**: PASS (4/5) — attribution required
- **CC-BY-SA**: PASS (3/5) — share-alike may complicate integration
- **CC-BY-NC**: PASS (3/5) — BioThings is an academic/non-profit project (Scripps Research / Su Lab), so non-commercial restriction is generally compatible. Flag as a minor risk if downstream commercial API consumers exist.
- **Custom academic license**: NEEDS_REVIEW — read terms carefully
- **No stated license**: FAIL — assume all rights reserved
- **Login required for download**: FAIL — access gate

### BioThings Use Context
BioThings APIs are developed and maintained by the Su Lab at Scripps Research, a non-profit academic institution. This means CC-BY-NC licensed data is generally ingestible. However, note downstream ambiguity: third-party commercial users of BioThings APIs may technically be consuming NC-licensed data for commercial purposes. When in doubt, recommend confirming acceptable use with the datasource maintainers.
