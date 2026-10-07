def get_customized_mapping(cls):
    """Elasticsearch mapping for DiSignAtlas documents.

    Inferred by running parser.load_data() against the full, live-downloaded
    dataset-info CSV (10,306 rows) and DEG GMT (8,466 rows) and recursively
    walking every yielded document's field values (no sampling — all 10,306
    documents were inspected). See README.md's "Mapping Overview"
    section for the full validation record.
    """
    return {
        "disignatlas": {
            "properties": {
                "accession": {"type": "keyword"},
                "platform": {"type": "keyword"},
                "disease": {
                    "type": "text",
                    "fields": {"raw": {"type": "keyword"}},
                },
                "disease_id": {"type": "keyword"},
                "tissue": {"type": "keyword"},
                "data_source": {"type": "keyword"},
                "library_strategy": {"type": "keyword"},
                "organism": {"type": "keyword"},
                "sample_count": {
                    "properties": {
                        "control": {"type": "integer"},
                        "case": {"type": "integer"},
                    }
                },
                "definition": {
                    "type": "text",
                    "fields": {"raw": {"type": "keyword"}},
                },
                "deg_count": {"type": "integer"},
                "degs": {"type": "integer"},
            }
        }
    }
