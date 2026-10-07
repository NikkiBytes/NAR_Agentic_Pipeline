def get_customized_mapping(cls):
    """Elasticsearch mapping for INTEDE documents, inferred from real
    post-parser output (921 documents produced by parser.load_data()
    against all 5 ingested bulk files; see README.md).

    All identifier/label fields use `keyword` (exact match / aggregation).
    Long free-text narrative fields (interaction descriptions/results) use
    `text` for full-text search, with a `.raw` keyword subfield for
    exact-match/aggregation use cases. List-of-object fields (the four
    interaction arrays) are mapped via their element `properties` — there
    is no Elasticsearch array type, so the list itself carries no mapping.
    """
    return {
        "intede": {
            "properties": {
                "dme_id": {"type": "keyword"},
                "name": {"type": "keyword"},
                "species": {"type": "keyword"},
                "uniprot": {"type": "keyword"},
                "gene_id": {"type": "keyword"},
                "ec_number": {"type": "keyword"},
                "xenobiotic_interactions": {
                    "properties": {
                        "xeotic_id": {"type": "keyword"},
                        "name": {"type": "keyword"},
                        "type": {"type": "keyword"},
                        "classification": {"type": "keyword"},
                        "description": {
                            "type": "text",
                            "fields": {"raw": {"type": "keyword"}},
                        },
                        "gene_form": {"type": "keyword"},
                        "modulation_type": {"type": "keyword"},
                    }
                },
                "microbiome_interactions": {
                    "properties": {
                        "drug_id": {"type": "keyword"},
                        "drug_name": {"type": "keyword"},
                        "interacted_species": {"type": "keyword"},
                        "location": {"type": "keyword"},
                        "result": {
                            "type": "text",
                            "fields": {"raw": {"type": "keyword"}},
                        },
                    }
                },
                "host_protein_interactions": {
                    "properties": {
                        "partner_id": {"type": "keyword"},
                        "partner_type": {"type": "keyword"},
                        "partner_name": {"type": "keyword"},
                        "disease": {"type": "keyword"},
                        "mof_classification": {"type": "keyword"},
                        "mof_detail": {"type": "keyword"},
                        "substrate": {"type": "keyword"},
                        "cell_line": {"type": "keyword"},
                        "summary": {"type": "keyword"},
                        "description": {
                            "type": "text",
                            "fields": {"raw": {"type": "keyword"}},
                        },
                    }
                },
                "methylation_interactions": {
                    "properties": {
                        "icd_code": {"type": "keyword"},
                        "disease_name": {"type": "keyword"},
                        "case_vs_health": {
                            "properties": {
                                "status": {"type": "keyword"},
                                "delta_beta": {"type": "float"},
                                "pvalue": {"type": "float"},
                            }
                        },
                        "case_vs_adjacent": {
                            "properties": {
                                "status": {"type": "keyword"},
                                "delta_beta": {"type": "float"},
                                "pvalue": {"type": "float"},
                            }
                        },
                        "case_vs_other": {
                            "properties": {
                                "status": {"type": "keyword"},
                                "delta_beta": {"type": "float"},
                                "pvalue": {"type": "float"},
                            }
                        },
                    }
                },
            }
        }
    }
