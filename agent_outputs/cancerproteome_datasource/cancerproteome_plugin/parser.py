"""
Parser for CancerProteome (https://bio-bigdata.hrbmu.edu.cn/CancerProteome/)

Builds one document per protein/microprotein entity (keyed by the site's
composite "protein" identifier, e.g. "HEXB_P07686") aggregating:
  - differential canonical-protein expression (tumor vs. control) per cancer type/dataset
  - differential microprotein expression (tumor vs. control) per cancer type/dataset
  - differential PTM site-level expression (canonical + microprotein) per cancer type/dataset
  - protein expression vs. drug IC50 sensitivity correlations (DepMap/GDSC)

Six TSV files are downloaded via the manifest:
  cancer_names.txt          - abbreviation -> full cancer-type name lookup (not a data file itself)
  protein_inf.txt           - canonical protein differential expression
  microprotein_inf.txt      - microprotein differential expression
  PTM_protein_inf.txt       - canonical protein PTM differential expression
  PTM_microprotein_inf.txt  - microprotein PTM differential expression
  protein_durg_inf.txt      - protein-drug correlation (note: source filename is misspelled "durg")
"""
import csv
import os
import re

from biothings.utils.dataload import dict_sweep, unlist

# Matches a standard UniProt accession, e.g. P07686, Q8WYP5, A0A0B4J2F0
_UNIPROT_RE = re.compile(
    r"^([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})$"
)
# Matches the "[<residue><position>]" PTM site suffix, e.g. "[S1142]"
_PTM_SITE_RE = re.compile(r"\[([A-Za-z]+\d+)\]$")
# Matches a "Name (SOURCE:ID)" drug string, e.g. "AICAR (GDSC1:1001)"
_DRUG_SOURCE_RE = re.compile(r"^(.*?)\s*\(([^:()]+):([^()]+)\)\s*$")


def _to_float(value):
    if value is None:
        return None
    value = str(value).strip()
    if value == "" or value.upper() == "NA":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _to_int(value):
    if value is None:
        return None
    value = str(value).strip()
    if value == "" or value.upper() == "NA":
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _extract_uniprot(protein_id):
    """Pull a UniProt accession out of a composite protein ID like 'HEXB_P07686'."""
    if not protein_id:
        return None
    for token in protein_id.split("_"):
        if _UNIPROT_RE.match(token):
            return token
    return None


def _parse_ptm_site(ptm_in_protein):
    """Extract the residue+position (e.g. 'S1142') from 'AHCTF1_Q8WYP5[S1142]'."""
    if not ptm_in_protein:
        return None
    m = _PTM_SITE_RE.search(ptm_in_protein)
    return m.group(1) if m else None


def _parse_drug(drug_field):
    """Split 'AICAR (GDSC1:1001)' into name='AICAR', source='GDSC1', source_id='1001'."""
    if not drug_field:
        return None, None, None
    m = _DRUG_SOURCE_RE.match(drug_field)
    if m:
        return m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
    return drug_field.strip(), None, None


def _load_cancer_map(data_folder):
    """abbreviation -> uniform cancer-type name, e.g. 'LAML' -> 'Acute Myeloid Leukemia'."""
    cancer_map = {}
    infile = os.path.join(data_folder, "cancer_names.txt")
    if not os.path.exists(infile):
        return cancer_map
    with open(infile, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            abbrev = (row.get("Abbreviated.name") or "").strip()
            name = (row.get("Uniform.name") or "").strip()
            if abbrev:
                cancer_map[abbrev] = name or None
    return cancer_map


def _infer_entity_type(protein_id):
    """Best-effort entity_type guess from ID suffix conventions for entities that
    only appear in protein_durg_inf.txt (i.e. never seen in an expression/PTM file).
    Canonical proteins carry a UniProt accession or an explicit '_Canonical_N' tag;
    microproteins carry ribo-seq-derived tags like '_MP', '_odORF', '_pseudogene'."""
    if not protein_id:
        return None
    if _extract_uniprot(protein_id):
        return "canonical"
    if re.search(r"_Canonical(_\d+)?$", protein_id):
        return "canonical"
    if re.search(
        r"(_MP(_\d+)?|_odORF(_\d+)?|_pseudogene(_MP)?(_\d+)?|_lncRNA(_\d+)?|_u?ORF(_\d+)?|_ouORF(_\d+)?)$",
        protein_id,
    ):
        return "microprotein"
    return None


def _get_entity(entities, protein_id, entity_type=None, gene_name=None, protein_length=None):
    """Fetch or create the aggregation record for a protein/microprotein entity."""
    entity = entities.get(protein_id)
    if entity is None:
        entity = {
            "protein_id": protein_id,
            "gene_symbol": None,
            "entity_type": None,
            "protein_length": None,
            "uniprot": _extract_uniprot(protein_id),
            "expression": [],
            "ptm": [],
            "drug_correlations": [],
        }
        entities[protein_id] = entity
    if entity["gene_symbol"] is None and gene_name:
        entity["gene_symbol"] = gene_name
    if entity["entity_type"] is None and entity_type:
        entity["entity_type"] = entity_type
    if entity["protein_length"] is None and protein_length is not None:
        entity["protein_length"] = protein_length
    return entity


def _load_expression_file(entities, data_folder, filename, entity_type, length_col, cancer_map):
    infile = os.path.join(data_folder, filename)
    if not os.path.exists(infile):
        return
    with open(infile, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            protein_id = (row.get("protein") or "").strip()
            if not protein_id:
                continue
            gene_name = (row.get("geneName") or "").strip() or None
            protein_length = _to_int(row.get(length_col))
            entity = _get_entity(
                entities, protein_id, entity_type=entity_type,
                gene_name=gene_name, protein_length=protein_length,
            )
            cancer = (row.get("cancer") or "").strip() or None
            entity["expression"].append(dict_sweep({
                "cancer": cancer,
                "cancer_name": cancer_map.get(cancer) if cancer else None,
                "source": (row.get("source") or "").strip() or None,
                "mean_control": _to_float(row.get("Mean expression in control samples")),
                "mean_tumor": _to_float(row.get("Mean expression in tumor samples")),
                "fc": _to_float(row.get("FC")),
                "fdr": _to_float(row.get("FDR")),
            }, [None]))


def _load_ptm_file(entities, data_folder, filename, entity_type, length_col, cancer_map):
    infile = os.path.join(data_folder, filename)
    if not os.path.exists(infile):
        return
    with open(infile, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            protein_id = (row.get("protein") or "").strip()
            if not protein_id:
                continue
            gene_name = (row.get("geneName") or "").strip() or None
            protein_length = _to_int(row.get(length_col))
            entity = _get_entity(
                entities, protein_id, entity_type=entity_type,
                gene_name=gene_name, protein_length=protein_length,
            )
            cancer = (row.get("cancer") or "").strip() or None
            ptm_in_protein = (row.get("PTM_in_protein") or "").strip() or None
            entity["ptm"].append(dict_sweep({
                "site": _parse_ptm_site(ptm_in_protein),
                "ptm_in_protein": ptm_in_protein,
                "cancer": cancer,
                "cancer_name": cancer_map.get(cancer) if cancer else None,
                "source": (row.get("source") or "").strip() or None,
                "mean_control": _to_float(row.get("Mean expression in control samples")),
                "mean_tumor": _to_float(row.get("Mean expression in tumor samples")),
                "fc": _to_float(row.get("FC")),
                "fdr": _to_float(row.get("FDR")),
            }, [None]))


def _load_drug_file(entities, data_folder, cancer_map):
    infile = os.path.join(data_folder, "protein_durg_inf.txt")
    if not os.path.exists(infile):
        return
    with open(infile, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            protein_id = (row.get("Protein") or "").strip()
            if not protein_id:
                continue
            # Entity may not have been seen in the expression/PTM files at all
            # (protein_durg_inf.txt has 2,620 protein IDs not present elsewhere).
            entity = _get_entity(entities, protein_id)
            drug_field = (row.get("Drug") or "").strip() or None
            drug_name, drug_source, drug_source_id = _parse_drug(drug_field)
            drugname_col = (row.get("Drugname") or "").strip() or None
            cancer = (row.get("cancer") or "").strip() or None
            entity["drug_correlations"].append(dict_sweep({
                "drug": drugname_col or drug_name,
                "drug_source": drug_source,
                "drug_source_id": drug_source_id,
                "cor": _to_float(row.get("cor")),
                "fdr": _to_float(row.get("FDR")),
                "cancer": cancer,
                "cancer_name": cancer_map.get(cancer) if cancer else None,
            }, [None]))


def load_data(data_folder):
    """Parse CancerProteome data and yield BioThings-compatible documents."""
    cancer_map = _load_cancer_map(data_folder)
    entities = {}

    _load_expression_file(
        entities, data_folder, "protein_inf.txt",
        entity_type="canonical", length_col="protein_length", cancer_map=cancer_map,
    )
    _load_expression_file(
        entities, data_folder, "microprotein_inf.txt",
        entity_type="microprotein", length_col="microprotein_length", cancer_map=cancer_map,
    )
    _load_ptm_file(
        entities, data_folder, "PTM_protein_inf.txt",
        entity_type="canonical", length_col="protein_length", cancer_map=cancer_map,
    )
    _load_ptm_file(
        entities, data_folder, "PTM_microprotein_inf.txt",
        entity_type="microprotein", length_col="microprotein_length", cancer_map=cancer_map,
    )
    _load_drug_file(entities, data_folder, cancer_map)

    for protein_id, entity in entities.items():
        if entity["entity_type"] is None:
            # Entity only seen in protein_durg_inf.txt — infer from ID suffix conventions
            entity["entity_type"] = _infer_entity_type(protein_id)
        doc = {
            "_id": protein_id,
            "cancerproteome": entity,
        }
        yield dict_sweep(unlist(doc), [None])
