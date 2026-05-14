# Example Output

This is a trimmed example of the expected report format. The full example is at:
`/Users/nacosta/Documents/NAR_DB/NAR_BioThings_Ingestion_Report.md`

## Key structural elements

### Per-database entry format
```
### 1. DrugMAP 2.0 — Drug molecular atlas (DRUGS/RELATIONAL)

- **URL**: <https://idrblab.org/drugmap/>
- **DOI**: 10.1093/nar/gkae791
- **Description**: Accumulated 20,831 combinatorial drugs and their interacting atlas involving 1,583 pharmacologically important molecules; 842 repurposed drugs and their interacting atlas with 795 molecules; 3,260 off-targets relevant to the ADRs of 2,731 drugs.
- **Data format**: Drug-target interactions, drug-drug interactions, disease-drug mappings, ADMET properties
- **Identifiers**: PubChem CID, DrugBank, KEGG, WHO ICD disease codes
- **BioThings fit**: Drug-gene-disease relational data; maps to existing BioThings chem/drug schemas
```

### Category tags used in the example
- DRUGS/RELATIONAL — drug-target, drug-disease, pharmacogenomics
- PATHWAYS — signalling, metabolic pathways, protein networks
- PATHWAYS/RELATIONAL — pathway databases with cross-entity links
- RELATIONAL — gene-disease, variant-phenotype associations
- GENOMIC_VARIATION — variant databases, population genetics

### Cross-reference section format
```
**MyChem.info** sources: aeolus, chebi, chembl, drugbank, ...
**MyGene.info** sources: cell_marker, chembl, clingen, ...
**MyDisease.info** sources: ctd, disease_ontology, hpo, ...
**MyVariant.info** sources: cadd, cgi, civic, clinvar, ...

All N sources below have been confirmed **NOT** already in the BioThings ecosystem.
```

### Ingestion strategy section format
Group sources by access pattern:
- **Bulk TSV/CSV download**: DrugMAP, STRING, TTD, SIGNOR, ECBD, PharmFreq, GENEasso
- **REST API**: PGxDB, STRING, KEGG, IGVF Catalog
- **FTP dump**: STRING

Then list key identifier types to normalize across all sources.
