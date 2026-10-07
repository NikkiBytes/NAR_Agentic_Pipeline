def get_customized_mapping(cls):
    """Elasticsearch mapping for SLKB documents.

    Inferred from a full run of parser.load_data() against all 280,483
    documents produced from the live Figshare download (SQL_Dumps.zip,
    SLKB-sqlite3_dump.sql). Every leaf field was confirmed to have a single,
    consistent Python type across the entire document set (see
    README.md "Mapping Overview" for the validation script and
    results) -- no type conflicts were found, so no fields required manual
    resolution.
    """
    return {
        "slkb": {
            "properties": {
                "gene_pair_id": {"type": "integer"},
                "gene_1": {"type": "keyword"},
                "gene_2": {"type": "keyword"},
                "study_origin_pmid": {"type": "keyword"},
                "cell_line_origin": {"type": "keyword"},
                "is_sl": {"type": "boolean"},
                "original_result": {
                    "properties": {
                        "sl_score": {"type": "float"},
                        "statistical_score": {"type": "float"},
                        "sl_score_cutoff": {"type": "float"},
                        "statistical_score_cutoff": {"type": "float"},
                    }
                },
                "scores": {
                    "properties": {
                        "horlbeck": {
                            "properties": {
                                "sl_score": {"type": "float"},
                                "standard_error": {"type": "float"},
                            }
                        },
                        "median_b": {
                            "properties": {
                                "sl_score": {"type": "float"},
                                "standard_error": {"type": "float"},
                                "z_sl_score": {"type": "float"},
                            }
                        },
                        "median_nb": {
                            "properties": {
                                "sl_score": {"type": "float"},
                                "standard_error": {"type": "float"},
                                "z_sl_score": {"type": "float"},
                            }
                        },
                        "gemini": {
                            "properties": {
                                "sl_score_strong": {"type": "float"},
                                "sl_score_sensitive_lethality": {"type": "float"},
                                "sl_score_sensitive_recovery": {"type": "float"},
                            }
                        },
                        "mageck": {
                            "properties": {
                                "sl_score": {"type": "float"},
                                "standard_error": {"type": "float"},
                                "z_sl_score": {"type": "float"},
                            }
                        },
                        "sgrna_derived_b": {
                            "properties": {
                                "sl_score": {"type": "float"},
                            }
                        },
                        "sgrna_derived_nb": {
                            "properties": {
                                "sl_score": {"type": "float"},
                            }
                        },
                    }
                },
            }
        }
    }
