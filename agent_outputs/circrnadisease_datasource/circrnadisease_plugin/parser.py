import csv
import os

from biothings.utils.dataload import dict_sweep, unlist


def _circ_label(row):
    """circRNADisease does not always populate circrna_id (the circBase-style
    identifier). Fall back to circ_rna_name, then circrna_synonyms, so every
    row that has *some* circRNA label can still be aggregated."""
    for key in ("circrna_id", "circ_rna_name", "circrna_synonyms"):
        val = (row.get(key) or "").strip()
        if val:
            return val, key
    return None, None


def _to_float(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def load_data(data_folder):
    """Parse circRNADisease's bulk circRNA-disease association TSV and yield
    one BioThings document per unique (circRNA label, MONDO disease ID) pair,
    with all supporting evidence rows (one per PMID/detection-method
    combination) nested under `evidence`.
    """
    infile = os.path.join(data_folder, "circRNADisease_V3_circrna_details.txt")
    assert os.path.exists(infile), f"Expected file not found: {infile}"

    # pair_key -> accumulated document dict
    pairs = {}
    skipped_no_label = 0
    skipped_no_mondo = 0
    total_rows = 0

    with open(infile, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            total_rows += 1

            circ_label, circ_label_source = _circ_label(row)
            mondo_id = (row.get("Disease_MONDO_id") or "").strip()

            if not circ_label:
                skipped_no_label += 1
                continue
            if not mondo_id:
                skipped_no_mondo += 1
                continue

            pair_key = f"{circ_label}_{mondo_id}"

            if pair_key not in pairs:
                pairs[pair_key] = {
                    "_id": pair_key,
                    "circrnadisease": {
                        "circrna": {
                            "label": circ_label,
                            "label_source": circ_label_source,
                            "circbase_id": (row.get("circrna_id") or "").strip() or None,
                            "name": (row.get("circ_rna_name") or "").strip() or None,
                            "synonyms": (row.get("circrna_synonyms") or "").strip() or None,
                            "host_gene": (row.get("host_gene") or "").strip() or None,
                            "species": (row.get("species_details") or "").strip() or None,
                        },
                        "disease": {
                            "mondo_id": mondo_id,
                            "mondo_name": (row.get("Disease_MONDO_name") or "").strip() or None,
                            "reported_name": (row.get("Disease_Details") or "").strip() or None,
                        },
                        "evidence": [],
                    },
                }

            evidence_entry = {
                "pmid": (row.get("pmid") or "").strip() or None,
                "journal": (row.get("journal") or "").strip() or None,
                "pub_time": (row.get("pub_time") or "").strip() or None,
                "title": (row.get("title") or "").strip() or None,
                "expression_pattern": (row.get("expression_pattern") or "").strip() or None,
                "detection_method": (row.get("Detection_Method") or "").strip() or None,
                "description": (row.get("description") or "").strip() or None,
                "confidence_score": _to_float(row.get("Confidence Score")),
            }
            pairs[pair_key]["circrnadisease"]["evidence"].append(evidence_entry)

    for doc in pairs.values():
        doc = dict_sweep(unlist(doc), [None, "", [], {}])
        yield doc
