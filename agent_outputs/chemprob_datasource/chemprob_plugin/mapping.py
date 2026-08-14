"""
Elasticsearch mapping for Chem(Pro)2, inferred from representative documents
yielded by parser.py (1,636 docs: 603 probes + 1,033 competitors, sampled
against all 1,636 uploaded documents — no type conflicts observed).
"""


def get_customized_mapping(cls):
    return {
        "chemprob": {
            "properties": {
                "probe_id": {"type": "keyword"},
                "competitor_id": {"type": "keyword"},
                "name": {"type": "keyword"},
                "probe_type": {"type": "keyword"},
                "entity_type": {"type": "keyword"},
                "inchi": {"type": "keyword"},
                "smiles": {"type": "keyword"},
                "iupac_name": {"type": "keyword"},
                "properties": {
                    "properties": {
                        "mw": {"type": "float"},
                        "mf": {"type": "keyword"},
                        "polar_area": {"type": "float"},
                        "complexity": {"type": "float"},
                        "xlogp": {"type": "float"},
                        "heavy_atom_count": {"type": "integer"},
                        "hbond_donor": {"type": "integer"},
                        "hbond_acceptor": {"type": "integer"},
                        "rotatable_bonds": {"type": "integer"},
                    }
                },
                "xrefs": {
                    "properties": {
                        "pubchem": {"type": "keyword"},
                        "synonyms": {"type": "keyword"},
                    }
                },
                "experiments": {
                    "properties": {
                        "method_id": {"type": "keyword"},
                        "reference_id": {"type": "keyword"},
                        "criteria": {"type": "keyword"},
                        "probe_concentration": {"type": "keyword"},
                        "cp_concentration": {"type": "keyword"},
                        "experiment_method": {"type": "keyword"},
                        "quantitative_method": {"type": "keyword"},
                        "cell": {
                            "properties": {
                                "cell_id": {"type": "keyword"},
                                "cell_name": {"type": "keyword"},
                                "model_type": {"type": "keyword"},
                                "disease": {"type": "keyword"},
                                "tissue": {"type": "keyword"},
                                "species": {"type": "keyword"},
                                "cellosaurus_accession": {"type": "keyword"},
                            }
                        },
                    }
                },
            }
        }
    }
