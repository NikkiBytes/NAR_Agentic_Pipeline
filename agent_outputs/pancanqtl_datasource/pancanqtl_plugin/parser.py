"""
Parser for PancanQTLv2.0 (https://hanlaboratory.com/PancanQTLv2/).

PancanQTLv2.0 publishes four independent per-cancer-type bulk download
modules, each a gzipped tab-delimited text file (the site labels three of
them with a ".xls" extension, but the actual content is plain TSV -- NOT a
binary spreadsheet):

  1. Fine-mapping   <CANCER>.cis.susie.txt.gz     -- fine-mapped causal eQTL
                                                     credible sets (SuSiE),
                                                     25 cancer types
  2. eQTL-GWAS      <CANCER>.eQTL-GWAS.xls.gz     -- eQTL/GWAS-risk-locus
                                                     linkage-disequilibrium
                                                     associations, 33 types
  3. Drug-eQTL      <CANCER>.drug-eQTL.xls.gz     -- eQTL/drug-response
                                                     associations, 33 types
  4. Immune-eQTL    <CANCER>.immune-eQTL.xls.gz   -- eQTL/immune-cell-
                                                     infiltration
                                                     associations, 33 types

Each module has its own column schema and its own row-level granularity
(no shared primary key across modules), so this parser treats each row as
one association-type document rather than trying to merge the four
modules into a single per-SNP or per-gene record. Every document carries
an `association_type` field ("fine_mapping" | "gwas" | "drug" | "immune")
plus normalized `cancer_type` / `gene` / `snp` fields so all four types
remain queryable together under the same top-level `pancanqtl` key.
"""
import csv
import gzip
import hashlib
import logging
import os

from biothings.utils.dataload import dict_sweep, unlist

logger = logging.getLogger(__name__)


def _open_tsv(filepath):
    """Open a gzipped TSV file (regardless of .txt.gz / .xls.gz naming) as text."""
    return gzip.open(filepath, "rt", encoding="utf-8", errors="replace")


def _to_float(value):
    if value in (None, "", "NA", "NaN"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value):
    if value in (None, "", "NA", "NaN"):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _make_unique_id(base_id, seen_ids):
    """Append a short counter suffix on the rare occasion a composite key repeats."""
    if base_id not in seen_ids:
        seen_ids[base_id] = 1
        return base_id
    seen_ids[base_id] += 1
    return f"{base_id}-{seen_ids[base_id]}"


def _parse_finemapping(filepath, seen_ids):
    with _open_tsv(filepath) as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            snp = row.get("RS_id")
            cancer_type = row.get("Cancer_type")
            credible_set = row.get("Credible_Set")
            if not snp or not cancer_type or not credible_set:
                continue
            base_id = f"finemap:{credible_set}:{snp}"
            _id = _make_unique_id(base_id, seen_ids)
            doc = {
                "_id": _id,
                "pancanqtl": {
                    "association_type": "fine_mapping",
                    "cancer_type": cancer_type,
                    "gene": row.get("Gene_name"),
                    "snp": snp,
                    "variant": row.get("Variant"),
                    "chr": row.get("Chr"),
                    "position": _to_int(row.get("Position")),
                    "credible_set": credible_set,
                    "credible_set_size": _to_int(row.get("Credible_Set_Size")),
                    "pip": _to_float(row.get("PIP")),
                },
            }
            yield dict_sweep(unlist(doc), [None])


def _parse_gwas(filepath, seen_ids):
    with _open_tsv(filepath) as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            snp = row.get("eQTL_SNP")
            cancer_type = row.get("CancerType")
            gwas_snp = row.get("GWAS_SNP")
            pubmed_id = row.get("PUBMEDID")
            if not snp or not cancer_type:
                continue
            base_id = f"gwas:{cancer_type}:{snp}:{row.get('eGene')}:{gwas_snp}:{pubmed_id}"
            _id = _make_unique_id(base_id, seen_ids)
            doc = {
                "_id": _id,
                "pancanqtl": {
                    "association_type": "gwas",
                    "cancer_type": cancer_type,
                    "gene": row.get("eGene"),
                    "snp": snp,
                    "position": row.get("eQTL_SNP_pos"),
                    "gwas_snp": gwas_snp,
                    "gwas_snp_position": row.get("GWAS_SNP_pos"),
                    "r2": _to_float(row.get("R2")),
                    "risk_allele": row.get("RISK_ALLELE"),
                    "or_or_beta": _to_float(row.get("OR_or_BETA")),
                    "p_value": _to_float(row.get("P_value")),
                    "trait_or_disease": row.get("Trait_or_Disease"),
                    "pubmed_id": pubmed_id,
                },
            }
            yield dict_sweep(unlist(doc), [None])


def _parse_drug(filepath, seen_ids):
    with _open_tsv(filepath) as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            snp = row.get("SNP")
            cancer_type = row.get("cancer_type")
            drug = row.get("drug")
            source = row.get("Drug_source")
            if not snp or not cancer_type:
                continue
            base_id = f"drug:{cancer_type}:{snp}:{row.get('gene')}:{drug}:{source}"
            _id = _make_unique_id(base_id, seen_ids)
            doc = {
                "_id": _id,
                "pancanqtl": {
                    "association_type": "drug",
                    "cancer_type": cancer_type,
                    "gene": row.get("gene"),
                    "snp": snp,
                    "chr": row.get("chr"),
                    "position": _to_int(row.get("position")),
                    "alleles": row.get("alleles"),
                    "drug": drug,
                    "beta": _to_float(row.get("Beta")),
                    "se": _to_float(row.get("SE")),
                    "p_value": _to_float(row.get("P_value")),
                    "fdr": _to_float(row.get("FDR")),
                    "source": source,
                },
            }
            yield dict_sweep(unlist(doc), [None])


def _parse_immune(filepath, seen_ids):
    with _open_tsv(filepath) as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            snp = row.get("SNP")
            cancer_type = row.get("cancer_type")
            cell = row.get("Cell")
            source = row.get("Immune_cell_source")
            if not snp or not cancer_type:
                continue
            base_id = f"immune:{cancer_type}:{snp}:{row.get('gene')}:{cell}:{source}"
            _id = _make_unique_id(base_id, seen_ids)
            doc = {
                "_id": _id,
                "pancanqtl": {
                    "association_type": "immune",
                    "cancer_type": cancer_type,
                    "gene": row.get("gene"),
                    "snp": snp,
                    "chr": row.get("chr"),
                    "position": _to_int(row.get("position")),
                    "alleles": row.get("alleles"),
                    "cell_type": cell,
                    "beta": _to_float(row.get("Beta")),
                    "se": _to_float(row.get("SE")),
                    "p_value": _to_float(row.get("P_value")),
                    "fdr": _to_float(row.get("FDR")),
                    "source": source,
                },
            }
            yield dict_sweep(unlist(doc), [None])


# Dispatch table: filename suffix -> (module label, parse function)
_MODULE_DISPATCH = [
    (".cis.susie.txt.gz", "fine_mapping", _parse_finemapping),
    (".eQTL-GWAS.xls.gz", "gwas", _parse_gwas),
    (".drug-eQTL.xls.gz", "drug", _parse_drug),
    (".immune-eQTL.xls.gz", "immune", _parse_immune),
]


def load_data(data_folder):
    """Parse all PancanQTLv2.0 bulk download files and yield BioThings documents."""
    filenames = sorted(os.listdir(data_folder))
    assert filenames, f"No files found in {data_folder}"

    # One seen_ids counter per module keeps id-collision suffixing local to
    # that module's own composite-key namespace (each module id is already
    # prefixed, e.g. "gwas:", so there is no cross-module collision risk).
    seen_ids_by_module = {"fine_mapping": {}, "gwas": {}, "drug": {}, "immune": {}}

    matched_any = False
    for filename in filenames:
        filepath = os.path.join(data_folder, filename)
        for suffix, module, parse_fn in _MODULE_DISPATCH:
            if filename.endswith(suffix):
                matched_any = True
                logger.info("Parsing %s module file: %s", module, filename)
                yield from parse_fn(filepath, seen_ids_by_module[module])
                break

    assert matched_any, (
        f"No recognized PancanQTLv2.0 files found in {data_folder} "
        f"(expected suffixes: {[s for s, _, _ in _MODULE_DISPATCH]})"
    )
