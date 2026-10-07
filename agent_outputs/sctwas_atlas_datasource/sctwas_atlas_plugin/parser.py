import os
import csv
from biothings.utils.dataload import dict_sweep, unlist


# Column names in Allstudies_sig_eQTL.txt:
# SNP ID, SNP Location, Reference Allele, Alternative Allele, Gene Symbol,
# Ensembl ID, eQTL.beta, eQTL.pval, eQTL.zscore, Cell Type, Cell Condition,
# eQTL Dataset


def _safe_float(value):
    """Convert string to float; return None if conversion fails."""
    if value is None or value == "" or value == "NA":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _make_id(ensembl_id, cell_type, cell_condition, snp_id):
    """
    Construct a composite _id for each eQTL association.
    Format: {ensembl_id}|{cell_type}|{cell_condition}|{snp_id}
    All components normalized: spaces to underscores, lowercase cell type/condition.
    """
    cell_type_norm = cell_type.replace(" ", "_").replace("(", "").replace(")", "").replace("/", "_")
    cell_cond_norm = cell_condition.replace(" ", "_")
    return f"{ensembl_id}|{cell_type_norm}|{cell_cond_norm}|{snp_id}"


def load_data(data_folder):
    """
    Parse scTWAS Atlas sc-eQTL data and yield BioThings-compatible documents.

    Source file: Allstudies_sig_eQTL.txt (TSV, ~127MB, ~1.3M rows)
    Each row = one significant SNP-gene-celltype-condition eQTL association.
    Primary key: composite Ensembl ID + Cell Type + Cell Condition + SNP ID.

    NOTE: This plugin ingests the sc-eQTL INPUT data used by scTWAS Atlas,
    not the 2.7M scTWAS association OUTPUT results (those are not bulk-downloadable).
    """
    infile = os.path.join(data_folder, "Allstudies_sig_eQTL.txt")
    assert os.path.exists(infile), f"Expected file not found: {infile}"

    seen_ids = set()
    n_skipped_missing = 0
    n_skipped_dup = 0

    with open(infile, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            ensembl_id = row.get("Ensembl ID", "").strip()
            snp_id = row.get("SNP ID", "").strip()
            cell_type = row.get("Cell Type", "").strip()
            cell_condition = row.get("Cell Condition", "").strip()

            # Skip rows missing primary key components
            if not ensembl_id or not snp_id or not cell_type:
                n_skipped_missing += 1
                continue

            _id = _make_id(ensembl_id, cell_type, cell_condition, snp_id)

            if _id in seen_ids:
                n_skipped_dup += 1
                continue
            seen_ids.add(_id)

            # Parse SNP location (format: "12:56042145")
            snp_location = row.get("SNP Location", "").strip()
            chrom = None
            position = None
            if ":" in snp_location:
                parts = snp_location.split(":", 1)
                chrom = parts[0]
                try:
                    position = int(parts[1])
                except ValueError:
                    position = None

            doc = {
                "_id": _id,
                "sctwas_atlas": {
                    "snp": {
                        "id": snp_id,
                        "location": snp_location,
                        "chrom": chrom,
                        "position": position,
                        "ref_allele": row.get("Reference Allele", "").strip() or None,
                        "alt_allele": row.get("Alternative Allele", "").strip() or None
                    },
                    "gene": {
                        "ensembl_id": ensembl_id,
                        "symbol": row.get("Gene Symbol", "").strip() or None
                    },
                    "eqtl": {
                        "beta": _safe_float(row.get("eQTL.beta")),
                        "pval": _safe_float(row.get("eQTL.pval")),
                        "zscore": _safe_float(row.get("eQTL.zscore"))
                    },
                    "cell_type": cell_type,
                    "cell_condition": cell_condition,
                    "dataset": row.get("eQTL Dataset", "").strip() or None
                }
            }

            doc = dict_sweep(unlist(doc), [None])
            yield doc

    # Log skipped counts (visible in Hub logs)
    import logging
    logger = logging.getLogger(__name__)
    logger.info(
        f"scTWAS Atlas eQTL parser complete. "
        f"Skipped {n_skipped_missing} rows (missing key fields), "
        f"{n_skipped_dup} duplicate IDs."
    )
