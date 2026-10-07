"""
MolBiC parser — cell-based molecular bioactivity database.

Primary entity: compound (small molecule).
_id strategy: InChIKey (MyChem.info standard), from Compound.txt.
Structure: one document per unique InChIKey, with nested compound metadata
and a list of cell-based bioactivity records (CMBs) grouped from CMBs_All.txt.

Files consumed:
  1-3. Compound.txt                — compound structures, InChIKey, PubChem/ChEMBL xrefs
  2-1. CMBs_All.txt                — 550,093 cell-based molecular bioactivity records
  1-1. Cell_Line.txt               — cell line metadata (Cellosaurus accession, tissue, disease)
  5-2. Proteins_with_Uniprot_IDs.txt — protein → UniProt ID mapping

Note: MolBiC files have spaces in their filenames. The biothings-cli dumper will
fail to fetch these via URL-encoded paths (Drupal 8 JS-only download). Files must
be pre-placed in data_folder with their original names OR with spaces replaced by
underscores. This parser handles both naming conventions via _find_file().
"""

import os
import csv
import glob
from collections import defaultdict
from biothings.utils.dataload import dict_sweep, unlist


# ─── helpers ────────────────────────────────────────────────────────────────

def _safe_float(val):
    try:
        return float(val) if val and str(val).strip() not in (".", "", "None", "N/A", "-") else None
    except (ValueError, AttributeError):
        return None


def _safe_int(val):
    try:
        return int(val) if val and str(val).strip() not in (".", "", "None", "N/A", "-") else None
    except (ValueError, AttributeError):
        return None


def _or_none(val):
    if val is None:
        return None
    s = str(val).strip()
    return s if s and s not in (".", "None", "N/A", "-", "") else None


def _find_file(data_folder, *candidates):
    """
    Find a file by trying multiple candidate names.
    MolBiC filenames have spaces (e.g. '1-3. Compound.txt').
    Files may be pre-placed with spaces preserved or replaced by underscores.
    """
    for name in candidates:
        path = os.path.join(data_folder, name)
        if os.path.exists(path):
            return path
        # Try replacing spaces with underscores
        alt = os.path.join(data_folder, name.replace(" ", "_"))
        if os.path.exists(alt):
            return alt
    # Last resort: glob for partial match
    stem = candidates[0].split(".")[-1].strip() if candidates else ""
    for p in glob.glob(os.path.join(data_folder, "*.txt")):
        if stem.lower() in os.path.basename(p).lower():
            return p
    return None


def _read_tsv(path, delimiter="\t"):
    """Yield rows as dicts from a TSV file."""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        reader = csv.DictReader(fh, delimiter=delimiter)
        for row in reader:
            yield row


# ─── index builders ──────────────────────────────────────────────────────────

def _build_cell_index(data_folder):
    """Build cell_id → cell metadata dict from Cell_Line.txt."""
    cell_index = {}
    fpath = _find_file(data_folder, "1-1. Cell_Line.txt", "Cell_Line.txt")
    if not fpath:
        return cell_index
    for row in _read_tsv(fpath):
        # Column names based on MolBiC schema
        cid = _or_none(row.get("Cell Line") or row.get("Cell_Line") or row.get("cell_line_id"))
        if not cid:
            # Try first column as ID
            cid = _or_none(next(iter(row.values()), None))
        if not cid:
            continue
        cell_index[cid] = dict_sweep({
            "cell_line": cid,
            "cellosaurus_accession": _or_none(row.get("Cellosaurus accession") or row.get("Cellosaurus_accession")),
            "tissue": _or_none(row.get("Tissue") or row.get("tissue")),
            "disease": _or_none(row.get("Disease") or row.get("disease")),
            "organ": _or_none(row.get("Organ") or row.get("organ")),
            "species": _or_none(row.get("Species") or row.get("species")),
        }, [None])
    return cell_index


def _build_protein_index(data_folder):
    """Build protein_id → uniprot_id dict from Proteins_with_Uniprot_IDs.txt."""
    protein_index = {}
    fpath = _find_file(
        data_folder,
        "5-2. Proteins_with_Uniprot_IDs.txt",
        "Proteins_with_Uniprot_IDs.txt",
    )
    if not fpath:
        return protein_index
    for row in _read_tsv(fpath):
        protein = _or_none(row.get("Protein") or row.get("protein") or row.get("Target"))
        uniprot = _or_none(row.get("UniProt ID") or row.get("uniprot_id") or row.get("UniProt_ID"))
        if protein and uniprot:
            protein_index[protein] = uniprot
    return protein_index


def _build_cmb_index(data_folder, cell_index, protein_index):
    """
    Build InChIKey → list of CMB records from CMBs_All.txt.
    Each CMB record: protein target, cell line, bioactivity value, activity class, etc.
    """
    cmb_index = defaultdict(list)
    fpath = _find_file(data_folder, "2-1. CMBs_All.txt", "CMBs_All.txt")
    if not fpath:
        return cmb_index

    for row in _read_tsv(fpath):
        inchikey = _or_none(
            row.get("InChIKey") or row.get("inchikey") or row.get("InChI Key")
        )
        if not inchikey:
            continue

        protein = _or_none(row.get("Protein") or row.get("protein") or row.get("Target"))
        cell_line = _or_none(
            row.get("Cell Line") or row.get("cell_line") or row.get("Cell_Line")
        )
        bio_value = _safe_float(
            row.get("Bioactivity Value (IC50/EC50/Ki)")
            or row.get("Bioactivity_Value")
            or row.get("Value")
        )
        bio_unit = _or_none(row.get("Unit") or row.get("unit"))
        activity_type = _or_none(
            row.get("Bioactivity Type") or row.get("Activity Type") or row.get("bioactivity_type")
        )
        activity_class = _or_none(
            row.get("Activity Class") or row.get("activity_class") or row.get("Class")
        )
        drug_stage = _or_none(
            row.get("Drug Development Stage")
            or row.get("drug_development_stage")
            or row.get("Stage")
        )
        assay_type = _or_none(row.get("Assay Type") or row.get("assay_type"))
        pmid = _or_none(row.get("PMID") or row.get("pmid") or row.get("PubMed ID"))
        compound_id = _or_none(
            row.get("Compound ID") or row.get("compound_id") or row.get("Compound_ID")
        )

        # Enrich with cell metadata
        cell_data = None
        if cell_line and cell_line in cell_index:
            cell_data = cell_index[cell_line]

        # Enrich with UniProt
        uniprot = protein_index.get(protein) if protein else None

        cmb_record = dict_sweep({
            "compound_id": compound_id,
            "protein": protein,
            "uniprot_id": uniprot,
            "cell_line": cell_line,
            "cell_info": cell_data,
            "bioactivity_value": bio_value,
            "bioactivity_unit": bio_unit,
            "activity_type": activity_type,
            "activity_class": activity_class,
            "drug_development_stage": drug_stage,
            "assay_type": assay_type,
            "pmid": pmid,
        }, [None])

        cmb_index[inchikey].append(cmb_record)

    return cmb_index


# ─── main loader ─────────────────────────────────────────────────────────────

def load_data(data_folder):
    """
    Parse MolBiC data and yield BioThings-compatible documents.

    One document per unique InChIKey from Compound.txt.
    Each document has compound metadata + list of CMB bioactivity records.

    IMPORTANT: MolBiC files have spaces in filenames and cannot be downloaded
    programmatically via biothings-cli dump. Files must be pre-placed in
    data_folder before running upload. This parser handles both original
    space-containing names and underscore-substituted alternatives.
    """
    # Load supporting indices first
    cell_index = _build_cell_index(data_folder)
    protein_index = _build_protein_index(data_folder)
    cmb_index = _build_cmb_index(data_folder, cell_index, protein_index)

    # Main loop: iterate Compound.txt
    compound_path = _find_file(data_folder, "1-3. Compound.txt", "Compound.txt")
    assert compound_path, (
        "Compound.txt not found in data_folder. MolBiC files have spaces in their names "
        "and cannot be downloaded via biothings-cli dump. Pre-place files manually in: "
        + data_folder
    )

    seen_ids = set()

    for row in _read_tsv(compound_path):
        inchikey = _or_none(
            row.get("InChIKey") or row.get("inchikey") or row.get("InChI Key")
        )
        if not inchikey:
            continue
        if inchikey in seen_ids:
            continue
        seen_ids.add(inchikey)

        compound_id = _or_none(
            row.get("Compound ID") or row.get("compound_id") or row.get("Compound_ID")
        )
        name = _or_none(row.get("Compound Name") or row.get("compound_name") or row.get("Name"))
        formula = _or_none(row.get("Formula") or row.get("formula"))
        smiles = _or_none(row.get("Canonical SMILES") or row.get("SMILES") or row.get("smiles"))
        inchi = _or_none(row.get("InChI") or row.get("inchi"))
        pubchem = _or_none(row.get("PubChem ID") or row.get("pubchem_id") or row.get("PubChem_ID"))
        chembl = _or_none(row.get("ChEMBL ID") or row.get("chembl_id") or row.get("ChEMBL_ID"))

        props = dict_sweep({
            "formula": formula,
            "logp": _safe_float(row.get("logP") or row.get("logp")),
            "rotatable_bonds": _safe_int(row.get("Rotatable Bonds") or row.get("rotatable_bonds")),
            "heavy_atom_count": _safe_int(row.get("Heavy Atom Count") or row.get("heavy_atom_count")),
            "polar_area": _safe_float(row.get("Polar Areas") or row.get("polar_area") or row.get("tpsa")),
        }, [None])

        xrefs = dict_sweep({
            "pubchem": pubchem,
            "chembl": chembl,
        }, [None])

        # Get all CMBs for this compound
        cmbs = cmb_index.get(inchikey, []) or None

        # Summarize activity classes if CMBs exist
        activity_summary = None
        if cmbs:
            classes = [c.get("activity_class") for c in cmbs if c.get("activity_class")]
            high = sum(1 for c in classes if c and c.lower() == "high")
            moderate = sum(1 for c in classes if c and c.lower() == "moderate")
            low = sum(1 for c in classes if c and c.lower() == "low")
            activity_summary = dict_sweep({
                "total_cmbs": len(cmbs),
                "high_activity": high if high else None,
                "moderate_activity": moderate if moderate else None,
                "low_activity": low if low else None,
            }, [None])

        doc = {
            "_id": inchikey,
            "molbic": dict_sweep({
                "compound_id": compound_id,
                "name": name,
                "inchikey": inchikey,
                "inchi": inchi,
                "smiles": smiles,
                "properties": props if props else None,
                "xrefs": xrefs if xrefs else None,
                "activity_summary": activity_summary,
                "cmbs": cmbs,
            }, [None])
        }
        doc = dict_sweep(unlist(doc), [None])
        yield doc
