# NAR BioThings Pipeline Run
## Goal
Scan NAR 2025 Database Issue, find 4 verified sources, generate 4 BioThings plugins with reports.
## Already Built (skip)
ecbd, signor, gofcards, harmonizome_achilles, rnacentral, metanetx
## Top Candidates from NAR 2025 Table 1 (BioThings-relevant, not already in ecosystem)
1. **PharmFreq** — Global pharmacogenomic allele frequencies → variant/pharmacogenomics, pending.api
2. **PDCdb** — Peptide-drug conjugates → drug/chemical, MyChem/pending.api
3. **DMRdb** — Mendelian randomization causal relationships → gene-disease, pending.api
4. **COCONUT** (Table 2 update) — Natural products database → chemical, MyChem
5. **PGxDB** — Pharmacogenomics database → variant/drug, pending.api
6. **SV4GD** — Structural variation for genetic diseases → variant/disease, pending.api
7. **CVD Atlas** — Cardiovascular disease multi-omics → disease, pending.api
8. **PTMD** (Table 2 update) — Post-translational modifications linked to disease → protein/disease, pending.api
## Pipeline Stages (per candidate)
### Stage 1: Relevancy Analysis
Evaluate each candidate for relevance (0-5), novelty (0-5), openness (PASS/FAIL + 0-5). Verdict: RECOMMEND_INGEST / NEEDS_REVIEW / DO_NOT_INGEST.
### Stage 2: Site Inspection
For candidates with RECOMMEND_INGEST or NEEDS_REVIEW: verify download URLs, sample schema, assess fields.
### Stage 3: Plugin Generation
For 4 VERIFIED candidates: generate manifest.json, parser.py, version.py, design_rationale.md. Validate with biothings-cli.
## Execution Order
1. Create agent_outputs/ directory and pipeline_state.json
2. Fetch papers for top 8 candidates via PMC
3. Run relevancy analysis on each (batch where possible)
4. Run site inspection on top candidates
5. Generate plugins for 4 verified sources
6. Validate each plugin with biothings-cli
7. Update built-plugins-index.md
