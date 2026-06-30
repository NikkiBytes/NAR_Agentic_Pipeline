---
name: nar-biothings-scanner
description: >-
  Scan the NAR (Nucleic Acids Research) Database Issue for 10-20 databases
  suitable for BioThings API ingestion. Use when a user wants to discover new
  biomedical databases from recent NAR issues (2025+) that fit MyChem, MyGene,
  MyDisease, MyVariant, or pending.api. Produces a ranked candidate report with
  structured metadata per database. This skill sits upstream of
  datasource-relevancy-analysis and datasource-site-inspection skills.
  Do not use for non-NAR database discovery or for databases already known to be
  in the BioThings ecosystem.
---

# NAR BioThings Scanner

## When to Use
- User asks to find new BioThings-ingestible databases from NAR
- User references the NAR Database Issue or the NAR online database collection
- Periodic scanning for new datasources to feed the BioThings pipeline

## Instructions

### 1. Identify NAR Issues to Scan
NAR publishes a Database Issue annually in the January D1 volume:
- **2025**: Volume 53, Issue D1 — editorial DOI: 10.1093/nar/gkae1220 — PMC: PMC11701706
- **2026**: Volume 54, Issue D1 — editorial DOI: 10.1093/nar/gkaf1427

The editorial overview lists ALL new databases in Table 1 and updated databases in Table 2.

**Primary data source**: Fetch the editorial overview from PMC (open access). Extract the new-database table, which contains: database name, URL, and short description.

**Secondary data source**: The NAR online database collection at `http://www.oxfordjournals.org/nar/database/a/` (alphabetical) and `/c/` (by category). Each entry links to a summary page with the paper DOI.

**Tertiary**: Individual database papers on academic.oup.com/nar (open access). The Data Availability section of each paper contains download URLs, API endpoints, and license info.

Scan the years requested by the user (default: 2025+). Include both **new** databases and **major updates** that introduce new data types or substantially expand existing ones.

### 2. Extract Candidate Metadata
For each database in the editorial table, extract:
- **Name**: database name
- **URL**: homepage
- **DOI**: paper DOI
- **Description**: one-sentence summary from the editorial table
- **Category**: the NAR section it appears in (nucleic acids, proteins, pathways, genomic variation, etc.)

### 3. Filter for BioThings Relevance
Apply these inclusion criteria (database must meet ≥2):
1. Covers a core BioThings entity type: gene, variant, drug/chemical, disease, pathway, protein target
2. Uses standard biomedical identifiers (HGNC, NCBI Gene, UniProt, ChEMBL, PubChem, InChIKey, dbSNP, MONDO, etc.)
3. Provides relationships between BioThings entity types (gene-disease, drug-target, variant-phenotype)
4. Offers structured/tabular data (not just images, models, or free text)
5. Has open data access (no paywall, no mandatory login for downloads)

Apply these exclusion criteria:
- Plant-only databases with no human/model-organism relevance
- Pure structural biology (PDB entries, 3D models only)
- Imaging-only databases (microscopy, MRI, etc.)
- Metagenomic/microbiome resources with no human gene/disease angle
- Resources that are **already core BioThings sources** (see references/biothings-known-sources.md)

### 4. Cross-Reference Against Existing BioThings Sources
Load [references/biothings-known-sources.md](references/biothings-known-sources.md) for the known core API sources.

**IMPORTANT — also check pending.api plugins:**
Fetch the live plugin list from GitHub:
```
curl -sL "https://api.github.com/repos/biothings/pending.api/contents/plugins" | python3 -c "import sys,json; [print(d['name']) for d in json.load(sys.stdin)]" | sort
```
Cross-reference every candidate against this list. Also check if the candidate is from the **same lab/group** as an existing plugin (e.g., idrblab produces TTD, DrugMAP, DRESIS, NPCDR, MolBiC — if TTD is already a plugin, DrugMAP's drug-target data likely overlaps).

For each candidate:
- Check if the database name or its data is already a core BioThings source OR a pending.api plugin
- If yes, mark as **ALREADY_IN_BIOTHINGS** and exclude unless the NAR paper describes a major new data type not covered by the existing plugin
- If from the same lab as an existing plugin, flag as **NEEDS_REVIEW** with overlap notes
- If partial overlap, note which fields are novel vs redundant

### 5. Deep-Dive the Top Candidates
For the databases that pass the filter (aim for 10-20), fetch the individual paper and extract the details below.

**Important — OUP URL resolution**: Do NOT fetch OUP article URLs directly (`academic.oup.com/nar/article/...`) — they are JS-rendered and will fail. Instead, follow the resolution procedure in [../datasource-evaluation/references/nar-url-resolution.md](../datasource-evaluation/references/nar-url-resolution.md) to resolve each OUP URL to its PMC equivalent via PubMed E-utilities. PMC pages are reliably fetchable.

For each candidate, extract:
- **Data format**: what download formats are available (CSV, TSV, JSON, SDF, REST API, FTP, SQL dump)
- **Identifiers**: which biomedical identifiers are used (map to BioThings ID types)
- **Entity counts**: how many records/entities (from the paper abstract or methods)
- **License**: stated license and URL
- **BioThings fit**: which BioThings API it maps to (MyChem, MyGene, MyDisease, MyVariant, pending.api) and why
- **Category tag**: DRUGS/RELATIONAL, PATHWAYS, GENOMIC_VARIATION, etc.
- **Paper citation**: full citation for the database's own NAR paper (authors, title, journal, year, DOI, PMID/PMC). This is the paper describing the database itself, not the editorial overview.

### 6. Rank Candidates
Score each candidate on three dimensions (same as datasource-relevancy-analysis):
- **Relevance** (0-5): how well it fits BioThings entity types
- **Novelty** (0-5): how much new data it adds beyond existing BioThings sources
- **Openness** (0-5): how easy it is to access and ingest the data

Sort by total score (descending). Include the top 10-20.

### 7. Produce the Report
Save to: `agent_outputs/NAR_BioThings_Ingestion_Report_<YEAR>.md`
(e.g., `NAR_BioThings_Ingestion_Report_2025.md`)

See [references/example-output.md](references/example-output.md) for the exact output structure.

## Output Structure

```
# NAR Database Issue — BioThings Ingestion Analysis

## Overview
<1 paragraph: which NAR issue(s) scanned, how many total papers, how many new databases, how many candidates identified>

## The "Data Availability" Pattern
<Brief note that NAR articles contain a Data Availability section with URLs, downloads, APIs — the ingestion target>

## Cross-Reference: Sources Already in BioThings
<List current BioThings API sources, confirming all candidates below are NOT already included>

## <N> BioThings-Relevant Sources from NAR (<year range>)

### 1. <Database Name> — <short description> (<CATEGORY_TAG>)
- **URL**: <homepage>
- **DOI**: <paper DOI>
- **Paper**: <Authors>. "<Title>." *Nucleic Acids Res.* <year>;<volume>(D1):<pages>. DOI: [<doi>](https://doi.org/<doi>) — PMID: <pmid>
- **Description**: <2-3 sentences from paper>
- **Data format**: <formats available>
- **Identifiers**: <identifiers used, mapped to BioThings types>
- **BioThings fit**: <which API and why>

### 2. ...
(repeat for each candidate)

## Ingestion Strategy for BioThings

### Common data access patterns across these sources
- **Bulk download**: <list of sources>
- **REST API**: <list of sources>
- **FTP dump**: <list of sources>

### Key identifiers to normalize across sources
- **Genes**: NCBI Gene ID, Ensembl, UniProt, HGNC Symbol
- **Chemicals/Drugs**: PubChem CID, DrugBank, ChEMBL, InChI/SMILES
- **Diseases**: MeSH, DOID, OMIM, ICD
- **Variants**: GRCh38 coordinates, rsIDs
- **Pathways**: KEGG, Reactome, GO

## Next Steps
<Recommend running datasource-evaluation on top picks, then biothings-plugin-generator>
```

## Interaction with Other Skills
- **Upstream of**: `datasource-evaluation` → `biothings-plugin-generator`
- The report produced here provides the candidate list. Users then run the downstream skills on individual candidates.
- If a prior report exists in `agent_outputs/`, load it and note which candidates have already been evaluated.

## Decision Rules
- Default to 10-20 candidates. If fewer than 10 pass the filter, relax exclusion criteria slightly and note the relaxation.
- If more than 20 pass, raise the relevance threshold to top 20 only.
- Always confirm that candidates are NOT already in BioThings — false negatives here waste downstream effort.
- When in doubt about relevance, include the candidate with a note rather than excluding it.
- Prefer databases with bulk downloads over API-only resources (easier to ingest).
- Prefer databases with standard identifiers over proprietary ID systems.
