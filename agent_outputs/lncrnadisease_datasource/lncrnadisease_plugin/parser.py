import os
import csv
from collections import defaultdict

from biothings.utils.dataload import dict_sweep, unlist


def _norm(s):
    return (s or "").strip()


def _key(symbol, category, species, disease):
    return (
        _norm(symbol).lower(),
        _norm(category).lower(),
        _norm(species).lower(),
        _norm(disease).lower(),
    )


def load_data(data_folder):
    """Parse LncRNADisease v3.0 lncRNA/circRNA-disease association data.

    Two files are used together:
      - website_simple_data.csv: one row per unique (ncRNA, species, disease)
        association, carrying the stable `Database_ID` primary key (e.g. LDA0000001).
      - website_alldata.tsv: one row per piece of experimental evidence for an
        association (method, description, causality, supporting PubMed ID) --
        an association can have multiple evidence rows.

    The parser builds an evidence index from website_alldata.tsv keyed by the
    normalized (ncRNA symbol, category, species, disease) tuple, then walks
    website_simple_data.csv to emit one document per stable Database_ID with
    all matching evidence rows nested underneath.
    """
    simple_file = os.path.join(data_folder, "website_simple_data.csv")
    alldata_file = os.path.join(data_folder, "website_alldata.tsv")
    assert os.path.exists(simple_file), f"Expected file not found: {simple_file}"
    assert os.path.exists(alldata_file), f"Expected file not found: {alldata_file}"

    # Build evidence index from website_alldata.tsv
    evidence_index = defaultdict(list)
    with open(alldata_file, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            symbol = _norm(row.get("ncRNA Symbol"))
            category = _norm(row.get("ncRNA Category"))
            species = _norm(row.get("Species"))
            disease = _norm(row.get("Disease Name"))
            if not symbol or not disease:
                continue

            k = _key(symbol, category, species, disease)
            causality = _norm(row.get("Causality"))
            evidence = {
                "sample": _norm(row.get("Sample")) or None,
                "dysfunction_pattern": _norm(row.get("Dysfunction Pattern")) or None,
                "validated_method": _norm(row.get("Validated Method")) or None,
                "description": _norm(row.get("Description")) or None,
                "clinical_application": _norm(row.get("Clinical Application")) or None,
                "causality": causality or None,
                "causal_description": _norm(row.get("Causal Description")) or None,
                "pubmed_id": _norm(row.get("PubMed ID")) or None,
            }
            evidence_index[k].append(evidence)

    seen_ids = set()
    with open(simple_file, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            db_id = _norm(row.get("Database_ID"))
            if not db_id or db_id in seen_ids:
                continue
            seen_ids.add(db_id)

            symbol = _norm(row.get("ncRNA_Symbol"))
            category = _norm(row.get("ncRNA_Category"))
            species = _norm(row.get("Species"))
            disease = _norm(row.get("Disease_Name"))
            if not symbol or not disease:
                continue

            k = _key(symbol, category, species, disease)
            evidence_list = evidence_index.get(k, [])

            pubmed_ids = sorted({e["pubmed_id"] for e in evidence_list if e["pubmed_id"]})
            has_causal = any(e["causality"] == "Yes" for e in evidence_list)

            doc = {
                "_id": db_id,
                "lncrnadisease": {
                    "ncrna_symbol": symbol,
                    "ncrna_category": category,
                    "species": species,
                    "disease_name": disease,
                    "is_causal": has_causal,
                    "evidence_count": len(evidence_list),
                    "pubmed_ids": pubmed_ids or None,
                    "evidence": evidence_list or None,
                },
            }
            doc = dict_sweep(unlist(doc), [None])
            yield doc
