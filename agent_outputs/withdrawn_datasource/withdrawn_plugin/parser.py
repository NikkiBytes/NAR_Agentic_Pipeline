import csv
import os

from biothings.utils.dataload import dict_sweep, unlist

NA_VALUES = {"", "N/A", "NA", "NULL", "null", "none", "None"}


def _clean(value):
    """Return None for empty/placeholder values, else the stripped string."""
    if value is None:
        return None
    value = value.strip()
    if value in NA_VALUES:
        return None
    return value


def _to_int(value):
    value = _clean(value)
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _to_float(value):
    value = _clean(value)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _split_list(value, sep):
    value = _clean(value)
    if value is None:
        return None
    parts = [p.strip() for p in value.split(sep) if p.strip()]
    return parts if parts else None


def load_data(data_folder):
    """Parse Withdrawn 2.0's bulk CSV (withdrawns.csv) and yield BioThings-
    compatible documents keyed by InChIKey.

    Source: https://bioinformatics.charite.de/withdrawn_3/downloads/withdrawns.csv
    One row per withdrawn/discontinued drug. Rows without a usable InChIKey
    (no structure to merge on for MyChem.info) are skipped. The `molfile`,
    `maccsfp`, `fp24`, and `inchikey_jchem` columns are intentionally
    excluded from output: `molfile` is an OpenBabel-generated 2D block with
    placeholder (0,0,0) coordinates and no information beyond SMILES/InChI;
    `maccsfp`/`fp24` are raw fingerprint bit strings redundant with
    structure-derived fingerprints computable from SMILES elsewhere in
    BioThings; `inchikey_jchem` is a JChem-recomputed duplicate of
    `inchikey` that occasionally disagrees with it on stereochemistry layers
    for the same compound (noise, not signal).
    """
    infile = os.path.join(data_folder, "withdrawns.csv")
    assert os.path.exists(infile), f"Expected file not found: {infile}"

    seen_ids = set()

    with open(infile, "r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            inchikey = _clean(row.get("inchikey"))
            if not inchikey:
                # No structure identifier to merge into MyChem.info by -- skip.
                continue
            if inchikey in seen_ids:
                # Defensive: source data observed to have unique InChIKeys,
                # but guard against future duplicate rows anyway.
                continue
            seen_ids.add(inchikey)

            doc = {
                "_id": inchikey,
                "withdrawn": {
                    "withdrawn_id": _clean(row.get("withdrawnID")),
                    "name": _clean(row.get("drugname")),
                    "inchi": _clean(row.get("inchi")),
                    "smiles": _clean(row.get("smiles")),
                    "formula": _clean(row.get("formula")),
                    "properties": {
                        "molwt": _to_float(row.get("molwt")),
                        "tpsa": _to_float(row.get("tpsa")),
                        "hbond_acceptor": _to_int(row.get("hba")),
                        "hbond_donor": _to_int(row.get("hbd")),
                        "rotatable_bonds": _to_int(row.get("nrbonds")),
                    },
                    "toxicity": {
                        "ld50": _to_float(row.get("ld50")),
                        "tox_class": _to_int(row.get("toxclass")),
                        "tox_type": _split_list(row.get("toxtype"), ","),
                        "first_death": _clean(row.get("firstdeath")),
                    },
                    "withdrawal": {
                        "dataset": _clean(row.get("dataset")),
                        "first_approval_year": _to_int(row.get("firstapproval")),
                        "first_withdrawn_year": _to_int(row.get("firstwithdrawn")),
                        "last_withdrawn_year": _to_int(row.get("lastwithdrawn")),
                        "countries": _split_list(row.get("withdrawalCountries"), ";"),
                        "reference": _split_list(row.get("reference"), ";"),
                    },
                    "xrefs": {
                        "atc": _split_list(row.get("atc"), ";"),
                        "pubchem": _to_int(row.get("cid")),
                        "chembl": _clean(row.get("chemblid")),
                        "drugbank": _clean(row.get("DrugbankID")),
                        "ctd": _clean(row.get("ctdid")),
                    },
                },
            }

            doc = dict_sweep(unlist(doc), [None])
            yield doc
