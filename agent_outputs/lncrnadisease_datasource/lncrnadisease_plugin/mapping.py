def get_customized_mapping(cls):
    return {
        "lncrnadisease": {
            "properties": {
                "ncrna_symbol": {"type": "keyword"},
                "ncrna_category": {"type": "keyword"},
                "species": {"type": "keyword"},
                "disease_name": {"type": "keyword"},
                "is_causal": {"type": "boolean"},
                "evidence_count": {"type": "integer"},
                "pubmed_ids": {"type": "keyword"},
                "evidence": {
                    "properties": {
                        "sample": {"type": "keyword"},
                        "dysfunction_pattern": {"type": "keyword"},
                        "validated_method": {"type": "keyword"},
                        "description": {
                            "type": "text",
                            "fields": {"raw": {"type": "keyword"}}
                        },
                        "clinical_application": {"type": "keyword"},
                        "causality": {"type": "keyword"},
                        "causal_description": {
                            "type": "text",
                            "fields": {"raw": {"type": "keyword"}}
                        },
                        "pubmed_id": {"type": "keyword"}
                    }
                }
            }
        }
    }
