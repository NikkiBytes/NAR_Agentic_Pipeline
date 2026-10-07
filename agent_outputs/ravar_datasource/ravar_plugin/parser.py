"""Parser for RAVAR (a curated repository for rare variant-trait associations).

Source: http://www.ravar.bio
Bulk files (TSV, denormalized one-row-per-association):
  - gene_fulltable.txt : gene-level rare variant-trait associations
  - snp_fulltable.txt  : variant-level rare variant-trait associations

Both files repeat gene/variant metadata on every association row (one row per
gene-trait or variant-trait pair from one source publication). This parser
groups rows by the entity's natural identifier (Ensembl Gene ID for genes,
dbSNP rsID for variants) and nests the per-publication association evidence
(trait, p-value, method, xrefs) into an `associations` list on each document.

trait_allinfo.txt and publication_allinfo.txt are NOT ingested: every column
they contain (trait ontology label/description/synonym/tree; publication
title/authors/citation/journal/PMCID/DOI) is already denormalized into each
row of gene_fulltable.txt and snp_fulltable.txt, so a separate join would only
duplicate information already captured per-association.
"""
import csv
import os

from biothings.utils.dataload import dict_sweep, unlist


def _split_list(value):
    """Split a semicolon-delimited source field into a clean list of strings."""
    if not value:
        return None
    parts = [p.strip() for p in value.split(";") if p.strip() and p.strip().upper() != "NA"]
    return parts or None


def _split_efo_tree(value):
    """Split the '; '-delimited multi-path EFO/HPO Tree field into a list of path strings."""
    if not value:
        return None
    parts = [p.strip() for p in value.split(";") if p.strip() and p.strip().upper() != "NA"]
    return parts or None


def _to_float(value):
    if value is None:
        return None
    value = value.strip()
    if not value or value.upper() == "NA":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _to_int(value):
    if value is None:
        return None
    value = value.strip()
    if not value or value.upper() == "NA":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _clean(value):
    if value is None:
        return None
    value = value.strip()
    if not value or value.upper() == "NA":
        return None
    return value


def _publication_block(row):
    pub = {
        "pmid": _clean(row.get("PMID")),
        "pmcid": _clean(row.get("PMCID")),
        "doi": _clean(row.get("DOI")),
        "title": _clean(row.get("Title")),
        "authors": _clean(row.get("Authors")),
        "citation": _clean(row.get("Citation")),
        "first_author": _clean(row.get("First Author")),
        "journal": _clean(row.get("Journal/Book")),
        "publication_year": _to_int(row.get("Publication Year")),
    }
    return dict_sweep(pub, [None])


def load_gene_data(data_folder):
    """Parse gene_fulltable.txt and yield one document per unique Ensembl Gene ID."""
    infile = os.path.join(data_folder, "gene_fulltable.txt")
    assert os.path.exists(infile), f"Expected file not found: {infile}"

    genes = {}
    with open(infile, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            ensembl_id = _clean(row.get("Ensembl ID"))
            gene_symbol = _clean(row.get("Gene Symbol"))
            _id = ensembl_id or gene_symbol
            if not _id:
                continue

            if _id not in genes:
                genes[_id] = {
                    "_id": _id,
                    "gene_symbol": gene_symbol,
                    "ensembl_id": ensembl_id,
                    "gene_type": _clean(row.get("Gene Type")),
                    "chr": _clean(row.get("CHR")),
                    "location": _clean(row.get("Location")),
                    "gene_full_name": _clean(row.get("Gene full name")),
                    "gene_synonym": _split_list(row.get("Gene synonym")),
                    "gene_summary": _clean(row.get("Gene summary")),
                    "associations": [],
                }

            assoc = {
                "rid": _clean(row.get("RID")),
                "reported_trait": _clean(row.get("Reported Trait")),
                "trait_label": _clean(row.get("Trait Label")),
                "trait_ontology_id": _clean(row.get("Trait Ontology id")),
                "efo_description": _clean(row.get("EFO description")),
                "efo_synonym": _split_list(row.get("EFO synonym")),
                "efo_tree": _split_efo_tree(row.get("EFO Tree")),
                "pvalue": _to_float(row.get("P-value")),
                "method_software": _clean(row.get("Method/Software")),
                "publication": _publication_block(row),
            }
            genes[_id]["associations"].append(dict_sweep(assoc, [None]))

    for _id, doc in genes.items():
        out = {
            "_id": _id,
            "ravar": dict_sweep(doc, [None]),
        }
        # _id was nested inside "ravar" above by construction; strip the duplicate key
        out["ravar"].pop("_id", None)
        out = dict_sweep(unlist(out), [None])
        yield out


def load_variant_data(data_folder):
    """Parse snp_fulltable.txt and yield one document per unique dbSNP rsID."""
    infile = os.path.join(data_folder, "snp_fulltable.txt")
    assert os.path.exists(infile), f"Expected file not found: {infile}"

    variants = {}
    with open(infile, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            rsid = _clean(row.get("RSID"))
            if not rsid:
                continue

            if rsid not in variants:
                variants[rsid] = {
                    "_id": rsid,
                    "rsid": rsid,
                    "chr": _clean(row.get("CHR")),
                    "pos": _to_int(row.get("POS")),
                    "genotype": _clean(row.get("Genotype")),
                    "maf": _to_float(row.get("MAF")),
                    "mapped_gene": _clean(row.get("Mapped Gene")),
                    "nearby_genes": _split_list(row.get("Nearby Genes(+-100K)")),
                    "associations": [],
                }

            assoc = {
                "rid": _clean(row.get("RID")),
                "reported_trait": _clean(row.get("Reported Trait")),
                "trait_label": _clean(row.get("Trait Label")),
                "trait_ontology_id": _clean(row.get("Trait Ontology ID")),
                "efo_description": _clean(row.get("EFO description")),
                "efo_synonym": _split_list(row.get("EFO synonym")),
                "efo_tree": _split_efo_tree(row.get("EFO Tree")),
                "beta": _to_float(row.get("Beta")),
                "ci_95": _clean(row.get("95%CI")),
                "pvalue": _to_float(row.get("P-value")),
                "publication": _publication_block(row),
            }
            variants[rsid]["associations"].append(dict_sweep(assoc, [None]))

    for rsid, doc in variants.items():
        out = {
            "_id": rsid,
            "ravar": dict_sweep(doc, [None]),
        }
        out["ravar"].pop("_id", None)
        out = dict_sweep(unlist(out), [None])
        yield out
