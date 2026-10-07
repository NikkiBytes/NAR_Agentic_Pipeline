import os
import re

from biothings.utils.dataload import dict_sweep, unlist

ICD11_RE = re.compile(r"\[ICD-11:\s*([^\]]+)\]")


def _iter_data_lines(filepath):
    """Yield (entity_id, field, values) tuples from a TTD flat-file, skipping the header block.

    TTD flat files begin with a title/version/provider header, an "Abbreviations" section,
    and end the preamble with a line of dashes ("---..."). Every data line after the last
    dash-separator line is tab-separated as: <entity_id>\t<FIELD_NAME>\t<value>[\t<value>...]
    """
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    sep_idxs = [i for i, line in enumerate(lines) if line.startswith("---")]
    start = sep_idxs[-1] + 1 if sep_idxs else 0
    for line in lines[start:]:
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        entity_id, field = parts[0], parts[1]
        values = parts[2:]
        yield entity_id, field, values


def _load_target_disease(filepath):
    """Build TARGETID -> list of {status, disease, icd11} indication dicts from P1-06."""
    disease_map = {}
    if not filepath or not os.path.exists(filepath):
        return disease_map
    for entity_id, field, values in _iter_data_lines(filepath):
        if field != "INDICATI" or len(values) < 3:
            continue
        status, disease, icd_raw = values[0], values[1], values[2]
        m = ICD11_RE.search(icd_raw)
        icd11 = m.group(1).strip() if m else None
        entry = {"status": status or None, "disease": disease or None, "icd11": icd11}
        disease_map.setdefault(entity_id, []).append(entry)
    return disease_map


def load_data(data_folder):
    """Parse TTD (Therapeutic Target Database) target-centric records and yield BioThings documents.

    Combines P1-01-TTD_target_download.txt (target identity/annotation + per-target
    associated-drug list) with P1-06-Target_disease.txt (per-target ICD-11-coded disease
    indications) into one document per TTD target, keyed by the TTD Target ID (e.g. T47101).
    """
    target_file = os.path.join(data_folder, "P1-01-TTD_target_download.txt")
    disease_file = os.path.join(data_folder, "P1-06-Target_disease.txt")
    assert os.path.exists(target_file), f"Expected file not found: {target_file}"

    disease_map = _load_target_disease(disease_file)

    current_id = None
    doc = None

    def _finalize(d):
        if not d or not d.get("_id"):
            return None
        indications = disease_map.get(d["_id"])
        if indications:
            d["ttd"]["indications"] = indications
        return dict_sweep(unlist(d), [None])

    for entity_id, field, values in _iter_data_lines(target_file):
        if field == "TARGETID":
            if current_id is not None:
                out = _finalize(doc)
                if out:
                    yield out
            current_id = entity_id
            doc = {"_id": str(entity_id), "ttd": {"target_id": entity_id}}
            continue

        if doc is None or entity_id != current_id:
            # Defensive: a data line appeared with no open TARGETID block (malformed file).
            continue

        value = values[0] if values else None

        if field == "FORMERID":
            doc["ttd"]["former_id"] = value
        elif field == "UNIPROID":
            doc["ttd"].setdefault("xrefs", {})["uniprot"] = value
        elif field == "TARGNAME":
            doc["ttd"]["name"] = value
        elif field == "GENENAME":
            doc["ttd"]["gene_name"] = value
        elif field == "TARGTYPE":
            doc["ttd"]["target_type"] = value
        elif field == "SYNONYMS":
            doc["ttd"]["synonyms"] = [s.strip() for s in value.split(";") if s.strip()] if value else None
        elif field == "FUNCTION":
            doc["ttd"]["function"] = value
        elif field == "PDBSTRUC":
            doc["ttd"]["pdb_structures"] = [s.strip() for s in value.split(";") if s.strip()] if value else None
        elif field == "BIOCLASS":
            doc["ttd"]["bioclass"] = value
        elif field == "ECNUMBER":
            doc["ttd"]["ec_number"] = value
        elif field == "SEQUENCE":
            doc["ttd"]["sequence"] = value
        elif field == "DRUGINFO" and len(values) >= 3:
            drug_id, drug_name, status = values[0], values[1], values[2]
            doc["ttd"].setdefault("drugs", []).append(
                {"drug_id": drug_id or None, "name": drug_name or None, "status": status or None}
            )
        # Unrecognized fields are ignored (forward-compatible with new TTD columns).

    # Finalize the last open block.
    out = _finalize(doc)
    if out:
        yield out
