def get_customized_mapping(cls):
    return {
        "circrnadisease": {
            "properties": {
                "circrna": {
                    "properties": {
                        "label": {"type": "keyword"},
                        "label_source": {"type": "keyword"},
                        "circbase_id": {"type": "keyword"},
                        "name": {"type": "keyword"},
                        "synonyms": {"type": "keyword"},
                        "host_gene": {"type": "keyword"},
                        "species": {"type": "keyword"},
                    }
                },
                "disease": {
                    "properties": {
                        "mondo_id": {"type": "keyword"},
                        "mondo_name": {"type": "keyword"},
                        "reported_name": {"type": "keyword"},
                    }
                },
                "evidence": {
                    "properties": {
                        "pmid": {"type": "keyword"},
                        "journal": {"type": "keyword"},
                        "pub_time": {"type": "keyword"},
                        "title": {
                            "type": "text",
                            "fields": {"raw": {"type": "keyword"}},
                        },
                        "expression_pattern": {"type": "keyword"},
                        "detection_method": {"type": "keyword"},
                        "description": {
                            "type": "text",
                            "fields": {"raw": {"type": "keyword"}},
                        },
                        "confidence_score": {"type": "float"},
                    }
                },
            }
        }
    }
