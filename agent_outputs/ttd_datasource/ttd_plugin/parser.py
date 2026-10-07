import os
import logging
from collections import defaultdict
from biothings.utils.dataload import dict_sweep, unlist

logger = logging.getLogger(__name__)

# P1-02 and P1-03 use a 3-column entity-prefixed format:
#   ENTITY_ID \t FIELD_NAME \t VALUE
# Blocks are separated by blank lines; lines beginning with non-ID chars are header/metadata.
#
# P1-05 uses a 2-column blank-separated record format:
#   FIELD_NAME \t VALUE [\t more_value_columns...]
# Blocks are separated by blank lines; entity ID is in the TTDDRUID row.

_DRUG_ID_PREFIX = set("D")


def _is_data_row_3col(line):
    parts = line.split("\t")
    if len(parts) < 3:
        return False
    return parts[0][:1] in _DRUG_ID_PREFIX and len(parts[0]) >= 6


def _parse_3col_file(filepath):
    """Parse P1-02/P1-03 3-column entity-prefixed format.
    Returns dict: {drug_id: {field_name: value_or_list}}
    Multi-valued fields (same entity_id + field_name) are collected as lists.
    """
    data = defaultdict(lambda: defaultdict(list))
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            entity_id, field_name, value = parts[0].strip(), parts[1].strip(), parts[2].strip()
            if not entity_id or not entity_id[:1] in _DRUG_ID_PREFIX:
                continue
            if not field_name or not value:
                continue
            data[entity_id][field_name].append(value)
    result = {}
    for entity_id, fields in data.items():
        result[entity_id] = {k: (v[0] if len(v) == 1 else v) for k, v in fields.items()}
    return result


def _parse_disease_file(filepath):
    """Parse P1-05 2-column blank-separated drug-disease format.
    Returns dict: {drug_id: [{"disease": ..., "icd11": ..., "status": ...}]}
    """
    data = defaultdict(list)
    current_id = None
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                current_id = None
                continue
            parts = line.split("\t")
            field = parts[0].strip()
            if field == "TTDDRUID":
                current_id = parts[1].strip() if len(parts) > 1 else None
            elif field == "INDICATI" and current_id and len(parts) >= 3:
                # Format: INDICATI \t disease_name \t ICD-11: CODE \t clinical_status
                disease_name = parts[1].strip()
                icd11_raw = parts[2].strip() if len(parts) > 2 else ""
                status = parts[3].strip() if len(parts) > 3 else ""
                icd11 = icd11_raw.replace("ICD-11: ", "").strip()
                entry = {}
                if disease_name:
                    entry["disease"] = disease_name
                if icd11 and icd11 != "N.A.":
                    entry["icd11"] = icd11
                if status:
                    entry["status"] = status
                if entry:
                    data[current_id].append(entry)
    return dict(data)


def load_data(data_folder):
    """Parse TTD drug records from P1-02, P1-03, and P1-05 files."""
    drug_file = os.path.join(data_folder, "P1-02-TTD_drug_download.txt")
    xref_file = os.path.join(data_folder, "P1-03-TTD_crossmatching.txt")
    disease_file = os.path.join(data_folder, "P1-05-Drug_disease.txt")

    assert os.path.exists(drug_file), f"Expected file not found: {drug_file}"
    assert os.path.exists(xref_file), f"Expected file not found: {xref_file}"
    assert os.path.exists(disease_file), f"Expected file not found: {disease_file}"

    logger.info("Parsing TTD drug metadata from %s", os.path.basename(drug_file))
    drug_data = _parse_3col_file(drug_file)

    logger.info("Parsing TTD cross-references from %s", os.path.basename(xref_file))
    xref_data = _parse_3col_file(xref_file)

    logger.info("Parsing TTD drug-disease associations from %s", os.path.basename(disease_file))
    disease_data = _parse_disease_file(disease_file)

    logger.info("Loaded %d drug records, %d xref records, %d disease records",
                len(drug_data), len(xref_data), len(disease_data))

    yielded = 0
    for drug_id, fields in drug_data.items():
        xrefs_raw = xref_data.get(drug_id, {})
        indications = disease_data.get(drug_id, [])

        xrefs = {}
        if xrefs_raw.get("PUBCHCID"):
            raw_cid = xrefs_raw["PUBCHCID"]
            try:
                xrefs["pubchem_cid"] = int(raw_cid) if isinstance(raw_cid, str) else [int(x) for x in raw_cid]
            except (ValueError, TypeError):
                xrefs["pubchem_cid"] = raw_cid
        if xrefs_raw.get("CHEBI_ID"):
            xrefs["chebi"] = xrefs_raw["CHEBI_ID"]
        if xrefs_raw.get("CASNUMBE"):
            cas = xrefs_raw["CASNUMBE"]
            xrefs["cas"] = cas.replace("CAS ", "").strip() if isinstance(cas, str) else cas
        if xrefs_raw.get("SUPDRATC"):
            xrefs["atc"] = xrefs_raw["SUPDRATC"]

        company_raw = fields.get("DRUGCOMP", "")
        company = [c.strip() for c in company_raw.split(";")] if isinstance(company_raw, str) else company_raw

        ttd_doc = {
            "drug_id": drug_id,
        }
        if fields.get("TRADNAME"):
            ttd_doc["name"] = fields["TRADNAME"]
        if company:
            ttd_doc["company"] = company
        if fields.get("THERCLAS"):
            ttd_doc["therapeutic_class"] = fields["THERCLAS"]
        if fields.get("DRUGTYPE"):
            ttd_doc["drug_type"] = fields["DRUGTYPE"]
        if fields.get("HIGHSTAT"):
            ttd_doc["highest_status"] = fields["HIGHSTAT"]
        if fields.get("DRUGINKE"):
            ttd_doc["inchikey"] = fields["DRUGINKE"]
        if fields.get("DRUGINCH"):
            ttd_doc["inchi"] = fields["DRUGINCH"]
        if fields.get("DRUGSMIL"):
            ttd_doc["smiles"] = fields["DRUGSMIL"]
        if xrefs:
            ttd_doc["xrefs"] = xrefs
        if indications:
            ttd_doc["indications"] = indications

        doc = {
            "_id": drug_id,
            "ttd": ttd_doc,
        }
        doc = dict_sweep(unlist(doc), [None, ""])
        yielded += 1
        yield doc

    logger.info("Yielded %d TTD drug documents", yielded)
