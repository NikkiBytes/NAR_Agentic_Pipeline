def get_customized_mapping(cls):
    """Elasticsearch mapping for HMDD v4.0 documents.

    Inferred by running parser.load_data() against the full, live-downloaded
    alldata_v4.txt (31,533 documents / 53,553 evidence rows) and recursively
    walking every yielded document to record the observed Python type at
    each field path. 0 type conflicts were found across the full collection
    (see README.md, "Mapping Overview").
    """
    return {
        "hmdd": {
            "properties": {
                "mirna": {"type": "keyword"},
                "disease": {"type": "keyword"},
                "evidence_count": {"type": "integer"},
                "evidence": {
                    "properties": {
                        "category": {"type": "keyword"},
                        "code": {"type": "keyword"},
                        "pmid": {"type": "integer"},
                        "description": {"type": "text"},
                    }
                },
            }
        }
    }
