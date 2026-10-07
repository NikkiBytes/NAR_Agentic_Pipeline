import json
import os
from itertools import groupby
from operator import itemgetter

from biothings.utils.dataload import dict_sweep, unlist

_DATASET_FILE = "download_dataset.txt"
_SLICE_FILE = "download_slice.txt"


def _load_json_records(path):
    """SORC manifest files are plain JSON of the form {"data": [ {...}, ... ]}."""
    with open(path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    return payload.get("data", [])


def _build_slice_record(rec):
    """Build one per-slice sub-record from a download_slice.txt entry.

    These fields are filenames pointing at downstream result tables
    (deconvolution proportions, SVGs, GSVA scores, cell-cell communication);
    the files themselves live behind SORC's downloadCopy.jsp endpoint, which
    was confirmed non-functional during inspection (see README.md).
    They are kept as string references so a future ingestion pass can resolve
    them once the site's download bug is fixed / the maintainers are contacted.
    """
    return dict_sweep({
        "slice_site": rec.get("slice_site"),
        "spot_num": rec.get("spot_num"),
        "spatial_file": rec.get("spatial_file"),
        "deconvolution_table": rec.get("spot_dev_table"),
        "svg_table": rec.get("svg_table"),
        "sc_expression_table": rec.get("sc_table"),
        "sc_celltype_table": rec.get("sc_celltype_table"),
        "co_occurrence_table": rec.get("co_occ_table"),
        "gsva_immune_table": rec.get("fun_imm_table"),
        "gsva_go_table": rec.get("fun_go_table"),
        "gsva_kegg_table": rec.get("fun_kegg_table"),
        "gsva_cellstate_table": rec.get("fun_cellstate_table"),
        "cellcell_communication_table": rec.get("cellcell_table"),
    }, [None])


def load_data(data_folder):
    """Parse SORC dataset + slice manifests and yield one document per datasetID.

    SORC exposes two flat JSON manifests rather than the underlying spatial-omics
    result files: `download_dataset.txt` (one row per dataset, 82 total) and
    `download_slice.txt` (one row per tissue slice within a dataset, 269 total).
    This parser merges them into a single document per datasetID (the site's
    only stable, non-composite identifier), nesting the per-slice rows under
    `sorc.slices`.
    """
    dataset_path = os.path.join(data_folder, _DATASET_FILE)
    slice_path = os.path.join(data_folder, _SLICE_FILE)
    assert os.path.exists(dataset_path), f"Expected file not found: {dataset_path}"
    assert os.path.exists(slice_path), f"Expected file not found: {slice_path}"

    dataset_records = _load_json_records(dataset_path)
    slice_records = _load_json_records(slice_path)

    # groupby requires consecutive identical keys -- sort first.
    slice_records = sorted(slice_records, key=itemgetter("datasetID"))
    slices_by_dataset = {
        did: [_build_slice_record(r) for r in group]
        for did, group in groupby(slice_records, key=itemgetter("datasetID"))
    }

    seen_ids = set()
    for rec in dataset_records:
        raw_id = rec.get("datasetID")
        if not raw_id:
            continue
        _id = str(raw_id).strip()
        if not _id or _id in seen_ids:
            continue
        seen_ids.add(_id)

        doc = {
            "_id": _id,
            "sorc": {
                "dataset_id": _id,
                "cancer": rec.get("cancer"),
                "paper": rec.get("paper"),
                "paper_url": rec.get("paper_html"),
                "slice_count": rec.get("slice_num"),
                "spot_num_total": rec.get("spot_num"),
                "dataset_result_tables": {
                    "co_occurrence_table": rec.get("co_occ_table"),
                    "gsva_immune_table": rec.get("fun_imm_table"),
                    "gsva_go_table": rec.get("fun_go_table"),
                    "gsva_kegg_table": rec.get("fun_kegg_table"),
                    "gsva_cellstate_table": rec.get("fun_cellstate_table"),
                    "cellcell_communication_table": rec.get("cellcell_table"),
                },
                "slices": slices_by_dataset.get(_id, []),
            },
        }
        yield dict_sweep(unlist(doc), [None])
