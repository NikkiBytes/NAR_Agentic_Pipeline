"""Parser for DiSignAtlas (http://www.inbirg.com/disignatlas/).

DiSignAtlas ingests two bulk files:

1. "Disease information of All DiSignAtlas Datasets" (CSV) — one row per
   dataset, with disease name/ontology definition, tissue, GEO/ArrayExpress/
   TCGA accession, platform, organism, library strategy and
   control/case sample counts.
2. "Differentially Expressed Genes of All DiSignAtlas Datasets" (GMT) — one
   line per dataset, second column is a pipe-delimited metadata string,
   remaining tab-delimited columns are the top differentially expressed
   genes (NCBI/Entrez Gene IDs) for that dataset.

Both files are downloaded via manifest.json's dumper.data_url from
inbirg.com's download endpoints, whose URL paths carry no file extension
(e.g. ".../download/dis_info_datasets"). Because the exact filename the
Hub's dumper persists them under is not guaranteed to include an
extension, files are identified by sniffing their first line/row shape
rather than by filename.
"""
import csv
import io
import logging
import os

from biothings.utils.dataload import dict_sweep, unlist

logger = logging.getLogger(__name__)

CSV_HEADER_MARKER = "dsaid"
GMT_ID_PREFIX = "DSA"


def _is_dataset_csv(first_line):
    """The dataset-info file's header row starts with 'dsaid,accession,...'."""
    return first_line.lower().startswith(CSV_HEADER_MARKER + ",")


def _is_deg_gmt(first_line):
    """The DEG GMT file has no header; each line starts 'DSA#####\\t...'."""
    first_field = first_line.split("\t", 1)[0]
    return first_field.startswith(GMT_ID_PREFIX) and first_field[len(GMT_ID_PREFIX):].isdigit()


def _find_input_files(data_folder):
    """Classify every file in data_folder as the dataset CSV or the DEG GMT
    by sniffing its first line, rather than assuming a specific filename."""
    csv_path = None
    gmt_path = None
    for fname in sorted(os.listdir(data_folder)):
        fpath = os.path.join(data_folder, fname)
        if not os.path.isfile(fpath):
            continue
        try:
            with io.open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                first_line = fh.readline()
        except (OSError, UnicodeDecodeError):
            continue
        if not first_line:
            continue
        if csv_path is None and _is_dataset_csv(first_line):
            csv_path = fpath
        elif gmt_path is None and _is_deg_gmt(first_line):
            gmt_path = fpath
    return csv_path, gmt_path


def _parse_sample_count(raw):
    """'1|1' -> {"control": 1, "case": 1}. Returns None if malformed."""
    if not raw:
        return None
    parts = raw.split("|")
    if len(parts) != 2:
        return None
    control, case = (p.strip() for p in parts)
    if not (control.isdigit() and case.isdigit()):
        return None
    return {"control": int(control), "case": int(case)}


def _clean_gene_id(raw):
    """GMT gene columns occasionally carry a stray trailing quote character
    from upstream export (e.g. '381530"'). Strip stray quote/whitespace,
    then coerce to int. Returns None if the value isn't a bare integer."""
    cleaned = raw.strip().strip('"').strip()
    if not cleaned:
        return None
    if cleaned.lstrip("-").isdigit():
        return int(cleaned)
    return None


def _load_deg_index(gmt_path):
    """Build {dsaid: [entrez_gene_id, ...]} from the GMT file.

    Column 1 = DiSignAtlas ID, column 2 = pipe-delimited run metadata
    (redundant with the CSV row and not re-extracted here), columns 3+ =
    top differentially expressed genes for that dataset (Entrez Gene IDs).
    """
    deg_index = {}
    if gmt_path is None:
        return deg_index
    with io.open(gmt_path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n").rstrip("\r")
            if not line:
                continue
            fields = line.split("\t")
            if len(fields) < 3:
                continue
            dsaid = fields[0].strip()
            if not dsaid:
                continue
            genes = []
            for raw_gene in fields[2:]:
                gene_id = _clean_gene_id(raw_gene)
                if gene_id is not None:
                    genes.append(gene_id)
            if genes:
                deg_index[dsaid] = genes
    return deg_index


def load_data(data_folder):
    """Parse DiSignAtlas dataset metadata + DEG signatures and yield one
    BioThings document per DiSignAtlas dataset (_id = DiSignAtlas ID,
    e.g. "DSA00001")."""
    csv_path, gmt_path = _find_input_files(data_folder)
    assert csv_path is not None, (
        f"Could not find the DiSignAtlas dataset-info CSV in {data_folder} "
        f"(expected a file whose header starts with 'dsaid,accession,...')"
    )
    if gmt_path is None:
        logger.warning(
            "Could not find the DiSignAtlas DEG GMT file in %s — "
            "documents will be produced without a `degs` field",
            data_folder,
        )

    deg_index = _load_deg_index(gmt_path)

    seen_ids = set()
    with io.open(csv_path, "r", encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            dsaid = (row.get("dsaid") or "").strip()
            if not dsaid or dsaid in seen_ids:
                continue
            seen_ids.add(dsaid)

            sample_count = _parse_sample_count(row.get("control_case_sample_count"))
            deg_count_raw = (row.get("deg_count") or "").strip()
            deg_count = int(deg_count_raw) if deg_count_raw.isdigit() else None

            disignatlas_doc = {
                "accession": row.get("accession") or None,
                "platform": row.get("platform") or None,
                "disease": row.get("disease") or None,
                "disease_id": row.get("diseaseid") or None,
                "tissue": row.get("tissue") or None,
                "data_source": row.get("data_source") or None,
                "library_strategy": row.get("library_strategy") or None,
                "organism": row.get("organism") or None,
                "sample_count": sample_count,
                "definition": row.get("definition") or None,
                "deg_count": deg_count,
                "degs": deg_index.get(dsaid) or None,
            }

            doc = {
                "_id": dsaid,
                "disignatlas": disignatlas_doc,
            }
            yield dict_sweep(unlist(doc), [None])
