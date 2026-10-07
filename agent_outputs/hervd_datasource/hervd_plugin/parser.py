"""
Parser for HervD Atlas — a curated knowledgebase of associations between
human endogenous retroviruses (HERVs) and diseases.

Source: https://ngdc.cncb.ac.cn/hervd/
Paper:  Li et al. 2024, Nucleic Acids Research, DOI: 10.1093/nar/gkad904

Inputs expected in data_folder (produced by dumper.py):
    - "Disease Information.txt"  (tab-delimited; disease name -> ontology xrefs)
    - "herv_term.json"           (bulk JSON; one row per HERV-Term locus)
    - "herv_element.json"        (bulk JSON; one row per HERV-Element/family)

Document model: one document per HERV entity (HERV-Term locus or HERV-Element
family). Each document embeds the list of diseases the source site's own
aggregation reports the HERV as associated with, each disease resolved to its
ontology cross-references via the Disease Information.txt lookup table.

Known granularity limit: the source site's bulk endpoints (herv_term,
herv_element) return a de-duplicated, denormalized list of disease NAMES per
HERV — they do not carry the per-association evidence (PMID, DOI, expression
trend/log2FC, omics level) that the paper's headline "60,726 associations"
figure is built from. That richer evidence table is only exposed via a
per-HERV-ID POST endpoint (/hervd/herv/term/association) requiring one API
call per HERV (~21,790 calls total) and was not crawled for this ingestion
pass — see README.md.
"""

import csv
import json
import os

from biothings.utils.dataload import dict_sweep, unlist


def _load_disease_lookup(data_folder):
    """Build a disease-name -> ontology-xref dict from Disease Information.txt."""
    path = os.path.join(data_folder, "Disease Information.txt")
    assert os.path.exists(path), f"Expected file not found: {path}"

    lookup = {}
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            name = (row.get("Disease Name") or "").strip()
            if not name:
                continue
            xrefs = {}
            for src_col, xref_key in (
                ("EFO", "efo"),
                ("DOID", "doid"),
                ("NCI", "nci"),
                ("OMIM", "omim"),
                ("MESH", "mesh"),
                ("Others", "other"),
            ):
                val = (row.get(src_col) or "").strip()
                if val and val != "-":
                    xrefs[xref_key] = val
            lookup[name] = {
                "name": name,
                "category": (row.get("Disease Category") or "").strip() or None,
                "description": (row.get("Description") or "").strip() or None,
                "xrefs": xrefs or None,
            }
    return lookup


def _split_diseases(raw):
    """Split HervD Atlas's comma-joined 'Associated_disease' string into clean names."""
    if not raw:
        return []
    cleaned = raw.replace("\r", "").replace("\n", "")
    return [d.strip() for d in cleaned.split(",") if d.strip()]


def _resolve_diseases(names, disease_lookup):
    resolved = []
    for name in names:
        entry = disease_lookup.get(name)
        if entry:
            resolved.append(dict(entry))
        else:
            # Name present in the association list but not in the disease
            # reference table -- keep the bare name so no data is silently lost.
            resolved.append({"name": name})
    return resolved


def _load_data_terms(data_folder, disease_lookup):
    path = os.path.join(data_folder, "herv_term.json")
    assert os.path.exists(path), f"Expected file not found: {path}"

    with open(path, "r", encoding="utf-8") as f:
        rows = json.load(f)

    for row in rows:
        herv_id = (row.get("HervID") or "").strip()
        if not herv_id:
            continue

        disease_names = _split_diseases(row.get("Associated_disease"))
        associated_diseases = _resolve_diseases(disease_names, disease_lookup)

        length = row.get("Length")
        try:
            length = int(length) if length not in (None, "", "-") else None
        except ValueError:
            length = None

        doc = {
            "_id": herv_id,
            "hervd": {
                "herv_id": herv_id,
                "herv_name": (row.get("HervName") or "").strip() or None,
                "entity_type": "herv_term",
                "position": (row.get("Position") or "").strip() or None,
                "chromosome": (row.get("Position") or "").split(":")[0] or None,
                "strand": (row.get("Strand") or "").strip() or None,
                "length": length,
                "region_type": (row.get("Region") or "").strip() or None,
                "type": (row.get("Type") or "").strip() or None,
                "group": (row.get("Groups") or "").strip() or None,
                "disease_count": len(associated_diseases),
                "associated_diseases": associated_diseases,
            },
        }
        doc = dict_sweep(unlist(doc), [None, "", "-"])
        yield doc


def _load_data_elements(data_folder, disease_lookup):
    path = os.path.join(data_folder, "herv_element.json")
    assert os.path.exists(path), f"Expected file not found: {path}"

    with open(path, "r", encoding="utf-8") as f:
        rows = json.load(f)

    for row in rows:
        herv_id = (row.get("HERVID") or "").strip()
        if not herv_id:
            continue

        disease_names = _split_diseases(row.get("Associated_disease"))
        associated_diseases = _resolve_diseases(disease_names, disease_lookup)

        alias_raw = (row.get("Alias") or "").strip()
        alias = [a.strip() for a in alias_raw.split(",") if a.strip() and a.strip() != "-"]

        reported_raw = (row.get("Reported_name") or "").strip()
        reported_name = [r.strip() for r in reported_raw.split(",") if r.strip() and r.strip() != "-"]

        doc = {
            "_id": herv_id,
            "hervd": {
                "herv_id": herv_id,
                "herv_name": (row.get("HERVName") or "").strip() or None,
                "entity_type": "herv_element",
                "description": (row.get("Description") or "").strip() or None,
                "alias": alias or None,
                "reported_name": reported_name or None,
                "type": (row.get("Type") or "").strip() or None,
                "group": (row.get("Groups") or "").strip() or None,
                "disease_count": len(associated_diseases),
                "associated_diseases": associated_diseases,
            },
        }
        doc = dict_sweep(unlist(doc), [None, "", "-"])
        yield doc


def load_data(data_folder):
    """Parse HervD Atlas data and yield BioThings-compatible documents.

    Yields one document per HERV-Term locus (from herv_term.json) and one
    document per HERV-Element family (from herv_element.json). HervID
    namespaces do not collide between the two files (e.g.
    'chr10_ERV1_00043' vs 'ERV1_0001'), so both are safely combined under a
    single uploader with on_duplicates="error".
    """
    disease_lookup = _load_disease_lookup(data_folder)

    seen_ids = set()
    for doc in _load_data_terms(data_folder, disease_lookup):
        if doc["_id"] in seen_ids:
            continue
        seen_ids.add(doc["_id"])
        yield doc

    for doc in _load_data_elements(data_folder, disease_lookup):
        if doc["_id"] in seen_ids:
            continue
        seen_ids.add(doc["_id"])
        yield doc
