"""
Elasticsearch mapping for HervD Atlas documents.

Inferred by recursively walking all 21,790 documents yielded by
`parser.load_data()` against the full live-downloaded dataset (herv_term.json
+ herv_element.json + Disease Information.txt) and recording the observed
Python type at every field path. 0 type conflicts were found across the
combined herv_term + herv_element document set (see README.md
"Mapping Overview" for the full field-path/type table).

`description` fields (free-text disease/HERV descriptions, avg ~150 chars,
max 826 chars) are mapped as `text` with a `.raw` keyword subfield so both
full-text search and exact-match/aggregation are supported. All other string
fields (IDs, names, categories, ontology codes) are `keyword` since they are
short, low-cardinality-per-doc identifiers/labels, not intended for
full-text search.
"""


def get_customized_mapping(cls):
    return {
        "hervd": {
            "properties": {
                "herv_id": {"type": "keyword"},
                "herv_name": {"type": "keyword"},
                "entity_type": {"type": "keyword"},
                "position": {"type": "keyword"},
                "chromosome": {"type": "keyword"},
                "strand": {"type": "keyword"},
                "length": {"type": "integer"},
                "region_type": {"type": "keyword"},
                "type": {"type": "keyword"},
                "group": {"type": "keyword"},
                "description": {
                    "type": "text",
                    "fields": {"raw": {"type": "keyword"}},
                },
                "alias": {"type": "keyword"},
                "reported_name": {"type": "keyword"},
                "disease_count": {"type": "integer"},
                "associated_diseases": {
                    "properties": {
                        "name": {"type": "keyword"},
                        "category": {"type": "keyword"},
                        "description": {
                            "type": "text",
                            "fields": {"raw": {"type": "keyword"}},
                        },
                        "xrefs": {
                            "properties": {
                                "efo": {"type": "keyword"},
                                "doid": {"type": "keyword"},
                                "nci": {"type": "keyword"},
                                "omim": {"type": "keyword"},
                                "mesh": {"type": "keyword"},
                                "other": {"type": "keyword"},
                            }
                        },
                    }
                },
            }
        }
    }
