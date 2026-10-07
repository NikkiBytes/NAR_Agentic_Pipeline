"""
GENEasso parser — disease-gene association database.

716,122 high-confidence disease-gene associations from 8,226 GWAS
summary statistics, detected via 7 gene-based methods.

_id strategy:
    f"{ensg}_{dagena}_{method_key}" where method_key is the
    method name lowercased with spaces and hyphens replaced by underscores.
    E.g. "ENSG00000145335_GA00002_MAGMA" or
         "ENSG00000103811_GA00133_RWAS"

Method-specific field differences (detected from file headers):
  - MAGMA:          core + N(eQTL) + Z-score
  - DEPICT:         core + Top_eQTL
  - PASCAL:         core + N(eQTL)
  - LDAK-GBAT:      core + h2
  - RWAS:           core + PEAK + N(eQTL) + MODEL + R2 + Z-score
  - SMR_*:          core + Top_eQTL + N(eQTL) + Beta
"""

import csv
import glob
import os
import re

from biothings.utils.dataload import dict_sweep


# Files to skip entirely (analysis scripts, not data)
_SKIP_FILES = {"Script.download.txt"}


def _method_key(method_str):
    """Normalise method string into a safe identifier component.

    'LDAK-GBAT'      -> 'ldak_gbat'
    'SMR_GTEx-top1tissue' -> 'smr_gtex_top1tissue'
    'RWAS'           -> 'rwas'
    """
    return re.sub(r"[-\s]+", "_", method_str.strip()).lower()


def _to_float(val):
    """Return float or None.  Infinity/-Infinity are mapped to None (not valid JSON)."""
    if val is None or str(val).strip() in ("", "nan", "NA", "N/A", "skip"):
        return None
    try:
        f = float(val)
        # JSON does not support Infinity — treat as missing
        if f != f or f == float("inf") or f == float("-inf"):
            return None
        return f
    except (ValueError, TypeError):
        return None


def _to_int(val):
    """Return int or None."""
    if val is None or str(val).strip() in ("", "nan", "NA", "N/A", "skip"):
        return None
    try:
        return int(str(val).strip())
    except (ValueError, TypeError):
        return None


def _clean(val):
    """Return stripped string or None for empties."""
    if val is None:
        return None
    s = str(val).strip()
    return None if s in ("", "nan", "NA", "N/A", "skip") else s


def _parse_file(filepath):
    """Yield one document per row from a single GENEasso download TSV."""
    filename = os.path.basename(filepath)
    if filename in _SKIP_FILES:
        return

    with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
        reader = csv.DictReader(fh, delimiter="\t")

        for row in reader:
            ensg = _clean(row.get("ENSG"))
            dagena = _clean(row.get("DAGENA"))
            method = _clean(row.get("Method"))

            if not ensg or not dagena or not method:
                continue

            doc_id = f"{ensg}_{dagena}_{_method_key(method)}"

            # ---- core fields (present in all files) ----
            geneasso = {
                "dagena": dagena,
                "reported_trait": _clean(row.get("Reported Trait")),
                "efo_code": _clean(row.get("EFO Code")),
                "efo_ontology_trait": _clean(row.get("EFO Ontology Trait")),
                "efo_trait_description": _clean(row.get("EFO Trait Description")),
                "efo_trait_synonym": _clean(row.get("EFO Trait Synonym")),
                "efo_trait_tree": _clean(row.get("EFO Trait Tree")),
                "gene_symbol": _clean(row.get("Gene Symbol")),
                "gene_fullname": _clean(row.get("Gene Fullname")),
                "gene_biotype": _clean(row.get("Gene Biotype")),
                "ensg": ensg,
                "gene_synonym": _clean(row.get("Gene Synonym")),
                "gene_summary": _clean(row.get("Gene Summary")),
                "chromosome": _clean(row.get("Chromosome")),
                "start_pos": _to_int(row.get("Start Pos")),
                "end_pos": _to_int(row.get("End Pos")),
                "pvalue": _to_float(row.get("P-value")),
                "method": method,
            }

            # ---- method-specific fields (add only if column present) ----
            if "Z-score" in row:
                geneasso["zscore"] = _to_float(row.get("Z-score"))

            if "N(eQTL)" in row:
                geneasso["n_eqtl"] = _to_int(row.get("N(eQTL)"))

            if "h2" in row:
                geneasso["h2"] = _to_float(row.get("h2"))

            if "Top_eQTL" in row:
                geneasso["top_eqtl"] = _clean(row.get("Top_eQTL"))

            if "Beta" in row:
                geneasso["beta"] = _to_float(row.get("Beta"))

            # RWAS-specific
            if "PEAK" in row:
                geneasso["peak"] = _clean(row.get("PEAK"))
            if "MODEL" in row:
                geneasso["model"] = _clean(row.get("MODEL"))
            if "R2" in row:
                geneasso["r2"] = _to_float(row.get("R2"))

            # SMR top-tissue annotation (present in SMR_GTEx-* files as Top1-Tissue)
            if "Top1-Tissue" in row:
                geneasso["top1_tissue"] = _clean(row.get("Top1-Tissue"))

            doc = dict_sweep({"_id": doc_id, "geneasso": geneasso},
                             vals=[None, "", "nan"])
            yield doc


def load_data(data_folder):
    """Entry point for BioThings Hub uploader.

    Globs all *.download.txt files in data_folder and yields one
    document per row.  Script.download.txt is silently skipped.

    Some source files (LDAK-GBAT, MAGMA, PASCAL, RWAS, SMR_CAGE) contain
    duplicate rows for the same ENSG+DAGENA+Method triplet — a data quality
    issue in the upstream GENEasso release.  A seen_ids set deduplicates at
    parse time; only the first occurrence of each _id is yielded.
    """
    pattern = os.path.join(data_folder, "*.download.txt")
    files = sorted(glob.glob(pattern))

    if not files:
        raise FileNotFoundError(
            f"No *.download.txt files found in {data_folder!r}. "
            "Run 'biothings-cli dataplugin dump' first."
        )

    seen_ids = set()
    for filepath in files:
        for doc in _parse_file(filepath):
            doc_id = doc["_id"]
            if doc_id in seen_ids:
                continue
            seen_ids.add(doc_id)
            yield doc
