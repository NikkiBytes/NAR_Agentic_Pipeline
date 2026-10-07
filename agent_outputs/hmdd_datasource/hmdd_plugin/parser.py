"""Parser for HMDD v4.0 (Human microRNA Disease Database).

Source file: alldata_v4.txt
Columns (tab-delimited, header row): code, PMID, miRNA, disease, description

Each source row is one piece of experimental evidence connecting a single
miRNA to a single disease. The same (miRNA, disease) pair is frequently
supported by many rows (up to 122 for hsa-mir-21 / Breast Neoplasms), so
this parser groups rows into one BioThings document per unique
(miRNA, disease) pair, with all supporting evidence rows nested as a list.
"""

import csv
import os
import re
from collections import defaultdict

from biothings.utils.dataload import dict_sweep, unlist

# Maps HMDD's 23 raw evidence "code" values to the 8 evidence categories
# described in the NAR 2024 paper (Cui et al., HMDD v4.0).
_CATEGORY_MAP = {
    "circulation_biomarker_diagnosis_ns": "circulation",
    "circulation_biomarker_diagnosis_up": "circulation",
    "circulation_biomarker_diagnosis_down": "circulation",
    "circulation_biomarker_prognosis_ns": "circulation",
    "circulation_biomarker_prognosis_up": "circulation",
    "circulation_biomarker_prognosis_down": "circulation",
    "epigenetics": "epigenetics",
    "exosome": "exosome",
    "genetics_GWAS": "genetics",
    "genetics_knock down_promote": "genetics",
    "genetics_knock down_suppress": "genetics",
    "genetics_overexpression_promote": "genetics",
    "genetics_overexpression_suppress": "genetics",
    "target gene": "target",
    "lncRNA target": "target",
    "circRNA target": "target",
    "transcription factor target": "target",
    "therapeutic target": "target",
    "tissue_expression_ns": "tissue",
    "tissue_expression_up": "tissue",
    "tissue_expression_down": "tissue",
    "virus_miRNA": "virus",
    "other": "other",
}


def _slugify(value):
    """Lowercase, alnum-only slug used to build a stable composite _id."""
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def load_data(data_folder):
    """Parse HMDD v4.0 alldata_v4.txt and yield one document per unique
    (miRNA, disease) association pair, with all supporting evidence rows
    nested under `evidence`."""
    infile = os.path.join(data_folder, "alldata_v4.txt")
    assert os.path.exists(infile), f"Expected file not found: {infile}"

    # (mirna, disease) -> list of evidence dicts, in file order
    groups = defaultdict(list)
    # preserve first-seen original casing for mirna/disease display fields
    display_names = {}

    with open(infile, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            mirna = (row.get("miRNA") or "").strip()
            disease = (row.get("disease") or "").strip()
            code = (row.get("code") or "").strip()
            pmid = (row.get("PMID") or "").strip()
            description = (row.get("description") or "").strip()

            if not mirna or not disease:
                continue

            key = (mirna, disease)
            display_names.setdefault(key, (mirna, disease))

            evidence = {
                "category": _CATEGORY_MAP.get(code, "other"),
                "code": code or None,
                "pmid": int(pmid) if pmid.isdigit() else None,
                "description": description or None,
            }
            groups[key].append(evidence)

    seen_ids = set()
    for key, evidence_list in groups.items():
        mirna, disease = display_names[key]
        _id = f"{_slugify(mirna)}_{_slugify(disease)}"

        # Guard against slug collisions between distinct (mirna, disease)
        # pairs (not observed in the source data, but handled defensively).
        if _id in seen_ids:
            suffix = 2
            candidate = f"{_id}_{suffix}"
            while candidate in seen_ids:
                suffix += 1
                candidate = f"{_id}_{suffix}"
            _id = candidate
        seen_ids.add(_id)

        doc = {
            "_id": _id,
            "hmdd": {
                "mirna": mirna,
                "disease": disease,
                "evidence_count": len(evidence_list),
                "evidence": evidence_list,
            },
        }
        doc = dict_sweep(unlist(doc), [None])
        yield doc
