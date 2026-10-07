"""Elasticsearch mapping for TarBase v9.0 documents.

Inferred from the post-parser document shape produced by `parser.load_data()`
against the full live-downloaded bulk export (1,839,985 documents, no
sampling -- see README.md "Mapping Overview" for the validation
methodology and results).
"""


def get_customized_mapping(cls):
    return {
        "tarbase": {
            "properties": {
                "gene_name": {"type": "keyword"},
                "gene_id": {"type": "keyword"},
                "mirna_name": {"type": "keyword"},
                "mirna_id": {"type": "keyword"},
                "experiments": {"type": "integer"},
                "publications": {"type": "integer"},
                "cell_lines": {"type": "integer"},
                "micro_tscore": {"type": "float"},
            }
        }
    }
