# Evaluation Checklist

Reference material for consistent datasource evaluations.
Load this file when performing novelty comparisons or when unsure about scoring.

## Known BioThings API Data Sources (for novelty comparison)

> **Canonical ground truth registries** (always prefer these over the summary below):
> - [existing-biothings-plugins.json](existing-biothings-plugins.json) — complete registry of all sources in core BioThings APIs, with aliases, identifiers, domains, record counts, and versions (sourced from live /metadata endpoints)
> - [pending-api-datasources.json](pending-api-datasources.json) — complete registry of all Translator/pending.api datasources with overlap annotations
>
> The summary lists below are kept for quick reference but may lag behind the JSON registries.

### MyChem.info (chemical/drug)
- DrugBank (Open Data), ChEMBL, PubChem, ChEBI, SIDER, AEOLUS
- UNII, NDC, PharmGKB, UniChem, DrugCentral, GINAS, GSRS, GtoPdb
- FDA Orphan Drug, UMLS

### MyGene.info (gene)
- NCBI Entrez (gene, GO, genomic_pos, accession, refseq, retired)
- Ensembl (gene, genomic_pos, acc, pfam, interpro, prosite), Ensembl Protists
- UniProt, PharmGKB, CPDB (pathways), HomoloGene, AGR Orthology
- Pharos, ClinGen, ChEMBL (gene-level), NetAffx, UCSC

### MyDisease.info (disease)
- MONDO, Disease Ontology, HPO, CTD, UMLS

### MyVariant.info (variant)
- ClinVar, dbSNP, gnomAD (genomes + exomes), dbNSFP
- CADD, COSMIC (v68), CIViC, CGI, SnpEff
- GWAS Catalog, SNPedia, EVS, Geno2MP, GRASP, Wellderly, EMVClass

### pending.api / Translator KP APIs
- See [pending-api-datasources.json](pending-api-datasources.json) for the complete list
- Key deployed APIs: AGR, BindingDB, BioPlanet, DDInter, DGIdb, DISEASES, GO (BP/CC/MF), GTRx, HPO, iDISK, InnateDB, PFOCR, Rhea, SEMMEDDB, SuppKG, TTD, UBERON, repoDB, and more
- Portals: https://biothings.ncats.io, https://biothings.transltr.io, https://pending.biothings.io

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
