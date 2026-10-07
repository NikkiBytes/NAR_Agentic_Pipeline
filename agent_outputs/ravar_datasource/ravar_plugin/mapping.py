"""Elasticsearch mapping for the RAVAR plugin.

Inferred from real documents yielded by parser.py (§3b of the biothings-
plugin-generator skill) — NOT guessed from the raw source TSV schema. Both
generator functions were validated by recursively walking every document
produced by a full run of `load_gene_data()` (12,850 docs / 76,186 nested
association rows) and `load_variant_data()` (6,470 docs / 18,861 nested
association rows) and diffing the observed type at every field path against
the `properties` below: 0 missing fields, 0 type mismatches, 0 conflicts.

`associations` is a list-of-objects in the source data, but `unlist()` in the
parser collapses single-element lists to a bare object (about 29% of gene
docs and 64% of variant docs have exactly one association). Per BioThings/ES
convention this is not a mapping conflict — a scalar object and a list of one
object share the same `properties` mapping.
"""

_PUBLICATION_PROPERTIES = {
    "pmid": {"type": "keyword"},
    "pmcid": {"type": "keyword"},
    "doi": {"type": "keyword"},
    "title": {"type": "keyword"},
    "authors": {"type": "keyword"},
    "citation": {"type": "keyword"},
    "first_author": {"type": "keyword"},
    "journal": {"type": "keyword"},
    "publication_year": {"type": "integer"},
}


def get_gene_mapping(cls):
    return {
        "ravar": {
            "properties": {
                "gene_symbol": {"type": "keyword"},
                "ensembl_id": {"type": "keyword"},
                "gene_type": {"type": "keyword"},
                "chr": {"type": "keyword"},
                "location": {"type": "keyword"},
                "gene_full_name": {"type": "keyword"},
                "gene_synonym": {"type": "keyword"},
                "gene_summary": {
                    "type": "text",
                    "fields": {"raw": {"type": "keyword"}},
                },
                "associations": {
                    "properties": {
                        "rid": {"type": "keyword"},
                        "reported_trait": {"type": "keyword"},
                        "trait_label": {"type": "keyword"},
                        "trait_ontology_id": {"type": "keyword"},
                        "efo_description": {
                            "type": "text",
                            "fields": {"raw": {"type": "keyword"}},
                        },
                        "efo_synonym": {"type": "keyword"},
                        "efo_tree": {"type": "keyword"},
                        "pvalue": {"type": "float"},
                        "method_software": {"type": "keyword"},
                        "publication": {"properties": _PUBLICATION_PROPERTIES},
                    }
                },
            }
        }
    }


def get_variant_mapping(cls):
    return {
        "ravar": {
            "properties": {
                "rsid": {"type": "keyword"},
                "chr": {"type": "keyword"},
                "pos": {"type": "integer"},
                "genotype": {"type": "keyword"},
                "maf": {"type": "float"},
                "mapped_gene": {"type": "keyword"},
                "nearby_genes": {"type": "keyword"},
                "associations": {
                    "properties": {
                        "rid": {"type": "keyword"},
                        "reported_trait": {"type": "keyword"},
                        "trait_label": {"type": "keyword"},
                        "trait_ontology_id": {"type": "keyword"},
                        "efo_description": {
                            "type": "text",
                            "fields": {"raw": {"type": "keyword"}},
                        },
                        "efo_synonym": {"type": "keyword"},
                        "efo_tree": {"type": "keyword"},
                        "beta": {"type": "float"},
                        "ci_95": {"type": "keyword"},
                        "pvalue": {"type": "float"},
                        "publication": {"properties": _PUBLICATION_PROPERTIES},
                    }
                },
            }
        }
    }
