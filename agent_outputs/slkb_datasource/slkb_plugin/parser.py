"""Parser for SLKB (synthetic lethality knowledge base).

Source: Figshare deposit https://doi.org/10.6084/m9.figshare.22902839.v1
(SQL_Dumps.zip), which is the canonical bulk export cited in the paper's
Data Availability statement. The zip contains a self-contained sqlite3 SQL
dump (schema + INSERT statements + views) for the SLKB relational database.

This parser loads the sqlite3 dump into an in-memory sqlite3 database,
then joins the per-study original SL classification table
(cdko_original_sl_results) with the 7 independently re-calculated SL
scoring-method tables (all keyed by gene_pair_id) to produce one merged
document per (study, cell line, gene pair) record.
"""
import glob
import os
import sqlite3

from biothings.utils.dataload import dict_sweep, unlist

JOIN_QUERY = """
SELECT
    o.gene_pair_id, o.gene_1, o.gene_2, o.study_origin, o.cell_line_origin,
    o.SL_or_not, o.SL_score, o.statistical_score, o.SL_score_cutoff, o.statistical_score_cutoff,
    h.SL_score AS horlbeck_sl_score, h.standard_error AS horlbeck_standard_error,
    mb.SL_score AS median_b_sl_score, mb.standard_error AS median_b_standard_error, mb.Z_SL_score AS median_b_z_sl_score,
    mn.SL_score AS median_nb_sl_score, mn.standard_error AS median_nb_standard_error, mn.Z_SL_score AS median_nb_z_sl_score,
    g.SL_score_Strong AS gemini_sl_score_strong,
    g.SL_score_SensitiveLethality AS gemini_sl_score_sensitive_lethality,
    g.SL_score_SensitiveRecovery AS gemini_sl_score_sensitive_recovery,
    mk.SL_score AS mageck_sl_score, mk.standard_error AS mageck_standard_error, mk.Z_SL_score AS mageck_z_sl_score,
    sb.SL_score AS sgrna_derived_b_sl_score,
    sn.SL_score AS sgrna_derived_nb_sl_score
FROM cdko_original_sl_results o
LEFT JOIN horlbeck_score h ON o.gene_pair_id = h.gene_pair_id
LEFT JOIN median_b_score mb ON o.gene_pair_id = mb.gene_pair_id
LEFT JOIN median_nb_score mn ON o.gene_pair_id = mn.gene_pair_id
LEFT JOIN gemini_score g ON o.gene_pair_id = g.gene_pair_id
LEFT JOIN mageck_score mk ON o.gene_pair_id = mk.gene_pair_id
LEFT JOIN sgrna_derived_b_score sb ON o.gene_pair_id = sb.gene_pair_id
LEFT JOIN sgrna_derived_nb_score sn ON o.gene_pair_id = sn.gene_pair_id
"""


def _find_sqlite_dump(data_folder):
    matches = glob.glob(os.path.join(data_folder, "**", "SLKB-sqlite3_dump.sql"), recursive=True)
    assert matches, f"SLKB-sqlite3_dump.sql not found under {data_folder}"
    return matches[0]


def load_data(data_folder):
    """Parse SLKB data and yield BioThings-compatible documents.

    Each document represents one (study, cell line, gene pair) synthetic
    lethality record: the original study's SL classification/score plus
    every re-calculated SL scoring method available for that gene pair.
    """
    sql_path = _find_sqlite_dump(data_folder)

    conn = sqlite3.connect(":memory:")
    with open(sql_path, "r", encoding="utf-8", errors="replace") as f:
        conn.executescript(f.read())
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(JOIN_QUERY)

    seen_ids = set()
    for row in cur:
        d = dict(row)

        gene_pair_id = d.get("gene_pair_id")
        study_origin = d.get("study_origin")
        cell_line_origin = d.get("cell_line_origin")
        if gene_pair_id is None or not study_origin or not cell_line_origin:
            continue

        _id = f"{study_origin}_{cell_line_origin}_{gene_pair_id}"
        if _id in seen_ids:
            # (study_origin, cell_line_origin, gene_pair_id) is unique in the
            # source data, but guard against any unexpected join fan-out.
            continue
        seen_ids.add(_id)

        doc = {
            "_id": _id,
            "slkb": {
                "gene_pair_id": gene_pair_id,
                "gene_1": d.get("gene_1"),
                "gene_2": d.get("gene_2"),
                "study_origin_pmid": study_origin,
                "cell_line_origin": cell_line_origin,
                "is_sl": d.get("SL_or_not") == "SL",
                "original_result": {
                    "sl_score": d.get("SL_score"),
                    "statistical_score": d.get("statistical_score"),
                    "sl_score_cutoff": d.get("SL_score_cutoff"),
                    "statistical_score_cutoff": d.get("statistical_score_cutoff"),
                },
                "scores": {
                    "horlbeck": {
                        "sl_score": d.get("horlbeck_sl_score"),
                        "standard_error": d.get("horlbeck_standard_error"),
                    },
                    "median_b": {
                        "sl_score": d.get("median_b_sl_score"),
                        "standard_error": d.get("median_b_standard_error"),
                        "z_sl_score": d.get("median_b_z_sl_score"),
                    },
                    "median_nb": {
                        "sl_score": d.get("median_nb_sl_score"),
                        "standard_error": d.get("median_nb_standard_error"),
                        "z_sl_score": d.get("median_nb_z_sl_score"),
                    },
                    "gemini": {
                        "sl_score_strong": d.get("gemini_sl_score_strong"),
                        "sl_score_sensitive_lethality": d.get("gemini_sl_score_sensitive_lethality"),
                        "sl_score_sensitive_recovery": d.get("gemini_sl_score_sensitive_recovery"),
                    },
                    "mageck": {
                        "sl_score": d.get("mageck_sl_score"),
                        "standard_error": d.get("mageck_standard_error"),
                        "z_sl_score": d.get("mageck_z_sl_score"),
                    },
                    "sgrna_derived_b": {
                        "sl_score": d.get("sgrna_derived_b_sl_score"),
                    },
                    "sgrna_derived_nb": {
                        "sl_score": d.get("sgrna_derived_nb_sl_score"),
                    },
                },
            },
        }
        doc = dict_sweep(unlist(doc), [None])
        yield doc

    conn.close()
