def get_customized_mapping(cls):
    return {
        "ttd": {
            "properties": {
                "target_id": {"type": "keyword"},
                "former_id": {"type": "keyword"},
                "xrefs": {
                    "properties": {
                        "uniprot": {"type": "keyword"}
                    }
                },
                "name": {
                    "type": "text",
                    "fields": {"raw": {"type": "keyword"}}
                },
                "gene_name": {"type": "keyword"},
                "target_type": {"type": "keyword"},
                "synonyms": {"type": "keyword"},
                "function": {
                    "type": "text",
                    "fields": {"raw": {"type": "keyword"}}
                },
                "pdb_structures": {"type": "keyword"},
                "bioclass": {"type": "keyword"},
                "ec_number": {"type": "keyword"},
                "sequence": {"type": "keyword"},
                "drugs": {
                    "properties": {
                        "drug_id": {"type": "keyword"},
                        "name": {"type": "keyword"},
                        "status": {"type": "keyword"}
                    }
                },
                "indications": {
                    "properties": {
                        "status": {"type": "keyword"},
                        "disease": {"type": "keyword"},
                        "icd11": {"type": "keyword"}
                    }
                }
            }
        }
    }
