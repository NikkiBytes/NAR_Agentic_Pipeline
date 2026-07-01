# NAR BioThings Pipeline Run

## Goal

Scan NAR 2025 & 2026 Database Issues, identify BioThings-relevant sources, generate plugins with reports.

## Already Built (skip)

ecbd, signor, coconut, ttd, circtarget, gofcards, harmonizome_achilles, rnacentral, metanetx

## Full Candidate List (NAR 2025 & 2026)

Source: `claude/agent_outputs/NAR_BioThings_Ingestion_Report_2025_2026.md`

### Previously Identified (carried over from original scan — not yet built)

1. **PharmFreq** — Global pharmacogenomic allele frequencies → variant/pharmacogenomics, pending.api
2. **PDCdb** — Peptide-drug conjugates → drug/chemical, MyChem/pending.api
3. **DMRdb** — Mendelian randomization causal relationships → gene-disease, pending.api
4. **PGxDB** — Pharmacogenomics database → variant/drug, pending.api
5. **SV4GD** — Structural variation for genetic diseases → variant/disease, pending.api
6. **CVD Atlas** — Cardiovascular disease multi-omics → disease, pending.api
7. **PTMD 2.0** — Post-translational modifications linked to disease → protein/disease, pending.api

### New Discoveries (2025 & 2026 scan)

1. **TPDdb** — Targeted protein degraders (PROTACs, molecular glues, LYTACs) → drug/chemical, MyChem/pending.api
2. **MeDIC** — Drug indications and contraindications (government sources) → drug-disease, MyChem
3. **Chem(Pro)²** — Chemoproteomic probes labelling human proteins → chemical-protein, MyChem/pending.api
4. **RadioPharm** — Radiopharmaceuticals database → drug/chemical, MyChem
5. **MolBiC** — Cell-based landscape of molecular bioactivities → drug-target-cell, MyChem/pending.api
6. **GTO** — Gene therapy omnibus (clinical trials + transcriptomes) → gene-disease-therapy, pending.api
7. **PWAS Hub** — Protein-based GWAS with sex-stratified associations → gene-disease, pending.api/MyGene
8. **scTWAS Atlas** — Single-cell TWAS associations across 34 traits → gene-trait-cell, pending.api
9. **GWAShug** — Shared genetic basis between complex traits → variant-trait, pending.api
10. **sc2GWAS** — GWAS traits linked to individual cell populations → variant-cell-trait, pending.api
11. **PersADE** — Personalized adverse drug events with molecular mechanisms → drug-ADE, MyChem
12. **GENEasso** — Multi-method GWAS gene-disease associations (ancestry-stratified) → gene-disease, pending.api/MyGene

## Pipeline Stages (per candidate)

### Stage 1: Relevancy Analysis

Evaluate each candidate for relevance (0-5), novelty (0-5), openness (PASS/FAIL + 0-5). Verdict: RECOMMEND_INGEST / NEEDS_REVIEW / DO_NOT_INGEST.

### Stage 2: Site Inspection

For candidates with RECOMMEND_INGEST or NEEDS_REVIEW: verify download URLs, sample schema, assess fields.

### Stage 3: Plugin Generation

For VERIFIED candidates: generate manifest.json, parser.py, version.py, design_rationale.md. Validate with biothings-cli.

## Execution Order

1. Start with previously identified candidates (PharmFreq, PDCdb, DMRdb are highest priority)
2. Fetch papers for new discoveries via PMC
3. Run relevancy analysis on each (batch where possible)
4. Run site inspection on top candidates
5. Generate plugins for verified sources
6. Validate each plugin with biothings-cli
7. Update built-plugins-index.md
