"""Parser for TarBase v9.0 — experimentally-supported miRNA-gene target interactions.

Source: single CSV blob returned by the TarBase v9.0 web app's internal
`get_all_interactions/` API route (POST, empty JSON filter body `{}` returns
the entire unfiltered aggregated miRNA-gene-pair table). See dumper.py.

CSV columns (no alternate header variants observed):
    gene_name,gene_id,mirna_name,mirna_id,experiments,publications,cell_lines,micro_tscore

Each row is one aggregated miRNA-gene pair with evidence counts:
    - experiments:   number of distinct experiments supporting the interaction
    - publications:  number of distinct publications supporting the interaction
    - cell_lines:    number of distinct cell lines the interaction was observed in
    - micro_tscore:  microT-CDS-2023 computational target-prediction score (-1 .. 1)

7,103 of 1,847,088 raw rows share a duplicate (gene_id, mirna_id) composite key
(alternate gene_name synonyms mapping to the same Ensembl gene ID observed in
the source data) -- the first occurrence encountered is kept, matching the
source file's existing sort order (descending by `experiments`, i.e. the
best-supported synonym row is kept).
"""
import csv
import os

from biothings.utils.dataload import dict_sweep, unlist

_EXPECTED_HEADER = [
    "gene_name",
    "gene_id",
    "mirna_name",
    "mirna_id",
    "experiments",
    "publications",
    "cell_lines",
    "micro_tscore",
]


def _to_int(value):
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _find_infile(data_folder):
    """Locate the downloaded CSV regardless of the exact filename the dumper saved it as."""
    for fname in os.listdir(data_folder):
        if fname.lower().endswith(".csv"):
            return os.path.join(data_folder, fname)
    raise FileNotFoundError(f"No .csv file found in {data_folder}")


def load_data(data_folder):
    """Parse the TarBase v9.0 bulk interaction export and yield BioThings documents."""
    infile = _find_infile(data_folder)
    assert os.path.exists(infile), f"Expected file not found: {infile}"

    seen_ids = set()

    with open(infile, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        # Defensive header check -- the export has no documented API contract.
        missing = [c for c in _EXPECTED_HEADER if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(
                f"TarBase export is missing expected columns {missing}; "
                f"found columns: {reader.fieldnames}"
            )

        for row in reader:
            gene_id = (row.get("gene_id") or "").strip()
            mirna_id = (row.get("mirna_id") or "").strip()
            if not gene_id or not mirna_id:
                continue

            _id = f"{gene_id}_{mirna_id}"
            if _id in seen_ids:
                continue
            seen_ids.add(_id)

            doc = {
                "_id": _id,
                "tarbase": {
                    "gene_name": row.get("gene_name") or None,
                    "gene_id": gene_id,
                    "mirna_name": row.get("mirna_name") or None,
                    "mirna_id": mirna_id,
                    "experiments": _to_int(row.get("experiments")),
                    "publications": _to_int(row.get("publications")),
                    "cell_lines": _to_int(row.get("cell_lines")),
                    "micro_tscore": _to_float(row.get("micro_tscore")),
                },
            }
            doc = dict_sweep(unlist(doc), [None])
            yield doc
