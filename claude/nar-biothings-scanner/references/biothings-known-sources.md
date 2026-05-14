# BioThings Known Data Sources

Cross-reference candidates against these lists. Exclude databases already present unless the NAR paper describes a major new data type not yet in BioThings.

## MyChem.info (chemical/drug)
aeolus, chebi, chembl, drugbank, drugcentral, fda_orphan_drug, ginas, gsrs, gtopdb, ndc, pharmgkb, pubchem, sider, umls, unichem, unii

## MyGene.info (gene)
cell_marker, chembl, clingen, cpdb, ensembl, entrez, exac, generif, homologene, orthology_agr, pantherdb, pharmgkb, pharos, reactome, reagent, refseq, ucsc, umls, uniprot

## MyDisease.info (disease)
ctd, disease_ontology, disgenet, hpo, mondo, umls

## MyVariant.info (variant)
cadd, cgi, civic, clinvar, cosmic, dbnsfp, dbsnp, docm, emv, evs, exac, geno2mp, gnomad, grasp, gwassnps, mutdb, snpedia, snpeff, wellderly

## pending.api / staging
ALWAYS fetch the live plugin list before finalizing candidates:
```
curl -sL "https://api.github.com/repos/biothings/pending.api/contents/plugins" | python3 -c "import sys,json; [print(d['name']) for d in json.load(sys.stdin)]" | sort
```
Known plugins as of 2026-04 (non-exhaustive — always fetch live list):
agr, atc, biggim_kp, BindingDB, biomuta, bioplanet_pathway_disease, bioplanet_pathway_gene, BioThings_TTD_Dataplugin, ccle, cell_ontology, chebi, clinical_risk_kp, clinicaltrials_gov, DDInter, denovodb, DGIdb, DISEASES, Disbiome_data, doid, ebi_gene2phenotype, fda_drugs, FIRE, FoodData_parser, foodb_json, geneset1, GMMAD2_data, go, go_bp, go_cc, go_mf, GTRx, gwascatalog, HMDB_data, hpo, iDisk, InnateDB_parser, kaviar, mAbsData, mgi_gene2phenotype, mondo, multiomics_clinicaltrials_kp, multiomics_drug_approvals_kp, multiomics_wellness_kp, nameres, ncit, nodenorm, openfda_drug_events, pfocr, phewas, prot_meta_assc_hmdb, pseudocap_go, pubtator3, rare_source, repoDB, Rhea, semmeddb, SuppKG, tcga_mut_freq_kp, text_mining_targeted_association, TISSUES, uberon, umlschem, upheno_ontology

Also check https://biothings.ci.transltr.io/ for the staging API list.

## NAR databases already in BioThings (common overlaps)
These frequently appear in NAR Database Issues but are ALREADY BioThings sources:
- ClinVar → MyVariant.info
- PubChem → MyChem.info
- dbSNP → MyVariant.info
- COSMIC → MyVariant.info
- PharmGKB → MyChem.info, MyGene.info, MyVariant.info
- ChEMBL → MyChem.info, MyGene.info
- DrugBank → MyChem.info
- KEGG → MyGene.info (pathway annotations)
- Reactome → MyGene.info
- UniProt → MyGene.info
- Ensembl → MyGene.info
- gnomAD → MyVariant.info
- Disease Ontology → MyDisease.info
- MONDO → MyDisease.info
- HPO → MyDisease.info

When a NAR update paper covers one of these, skip it UNLESS the update introduces a new entity type or data layer not yet in BioThings.
