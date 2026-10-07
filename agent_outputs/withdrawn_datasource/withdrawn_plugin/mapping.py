def get_customized_mapping(cls):
    """Elasticsearch mapping for Withdrawn 2.0 documents.

    Inferred from a full run of parser.load_data() against the live
    withdrawns.csv (636 documents, all rows with a usable InChIKey).
    All string fields are exact-match identifiers/codes/short text rather
    than free-text search targets, so they are mapped as `keyword`. List
    fields (tox_type, countries, reference, atc) hold scalar string
    elements in every observed document, so they are mapped using that
    scalar's type -- Elasticsearch has no distinct array type.
    """
    return {
        "withdrawn": {
            "properties": {
                "withdrawn_id": {"type": "keyword"},
                "name": {"type": "keyword"},
                "inchi": {"type": "keyword"},
                "smiles": {"type": "keyword"},
                "formula": {"type": "keyword"},
                "properties": {
                    "properties": {
                        "molwt": {"type": "float"},
                        "tpsa": {"type": "float"},
                        "hbond_acceptor": {"type": "integer"},
                        "hbond_donor": {"type": "integer"},
                        "rotatable_bonds": {"type": "integer"},
                    }
                },
                "toxicity": {
                    "properties": {
                        "ld50": {"type": "float"},
                        "tox_class": {"type": "integer"},
                        "tox_type": {"type": "keyword"},
                        "first_death": {"type": "keyword"},
                    }
                },
                "withdrawal": {
                    "properties": {
                        "dataset": {"type": "keyword"},
                        "first_approval_year": {"type": "integer"},
                        "first_withdrawn_year": {"type": "integer"},
                        "last_withdrawn_year": {"type": "integer"},
                        "countries": {"type": "keyword"},
                        "reference": {"type": "keyword"},
                    }
                },
                "xrefs": {
                    "properties": {
                        "atc": {"type": "keyword"},
                        "pubchem": {"type": "integer"},
                        "chembl": {"type": "keyword"},
                        "drugbank": {"type": "keyword"},
                        "ctd": {"type": "keyword"},
                    }
                },
            }
        }
    }
