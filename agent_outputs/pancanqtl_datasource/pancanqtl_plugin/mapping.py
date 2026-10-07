def get_customized_mapping(cls):
    """Elasticsearch mapping for PancanQTLv2.0 documents.

    Inferred from real documents yielded by parser.load_data() against a
    representative sample of live-downloaded files (one per module:
    ESCA fine-mapping, DLBC eQTL-GWAS, LAML drug-eQTL, GBM immune-eQTL;
    25,462 documents total). See README.md's "Mapping Overview"
    section for the full validation write-up, including the one
    documented type conflict (pancanqtl.position).
    """
    return {
        "pancanqtl": {
            "properties": {
                "association_type": {"type": "keyword"},
                "cancer_type": {"type": "keyword"},
                "gene": {"type": "keyword"},
                "snp": {"type": "keyword"},
                "variant": {"type": "keyword"},
                "chr": {"type": "keyword"},
                # Conflict: fine_mapping/drug/immune docs yield an int
                # (e.g. 39453730); gwas docs yield a combined "chr:pos"
                # string (e.g. "4:39453730") because the eQTL-GWAS source
                # file only provides eQTL_SNP_pos in that combined form.
                # Resolved to keyword (the safe superset for both shapes)
                # rather than silently truncating the gwas string form to
                # fit an integer type. See "Mapping Conflicts" below.
                "position": {"type": "keyword"},
                "credible_set": {"type": "keyword"},
                "credible_set_size": {"type": "integer"},
                "pip": {"type": "float"},
                "gwas_snp": {"type": "keyword"},
                "gwas_snp_position": {"type": "keyword"},
                "r2": {"type": "float"},
                "risk_allele": {"type": "keyword"},
                "or_or_beta": {"type": "float"},
                "p_value": {"type": "float"},
                "trait_or_disease": {
                    "type": "text",
                    "fields": {"raw": {"type": "keyword"}},
                },
                "pubmed_id": {"type": "keyword"},
                "alleles": {"type": "keyword"},
                "drug": {"type": "keyword"},
                "beta": {"type": "float"},
                "se": {"type": "float"},
                "fdr": {"type": "float"},
                "source": {"type": "keyword"},
                "cell_type": {"type": "keyword"},
            }
        }
    }
