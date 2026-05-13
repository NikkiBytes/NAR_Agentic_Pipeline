# Production Plugin Examples

Real plugins from the BioThings GitHub repositories, curated to illustrate each major parser pattern.
Use these as authoritative references — prefer them over abstract guidance when the pattern fits.

Sources:
- https://github.com/biothings/pending.api/tree/master/plugins
- https://github.com/biothings/mydisease.info/tree/master/src/plugins

---

## Pattern 1: Multi-file TSV + groupby aggregation + cross-API ID resolution
**Plugin**: DISEASES (pending.api)
**When to use**: Multiple TSV files share a common grouping key; records must be merged into one document per entity; IDs need cross-API resolution (e.g., DOID → MONDO).

### manifest.json
```json
{
    "version": "0.1",
    "__metadata__": {
        "license_url": "https://creativecommons.org/licenses/by/3.0/",
        "license": "CC BY 3.0",
        "url": "https://diseases.jensenlab.org/"
    },
    "dumper": {
        "data_url": [
            "http://download.jensenlab.org/human_disease_textmining_full.tsv",
            "http://download.jensenlab.org/human_disease_knowledge_full.tsv",
            "http://download.jensenlab.org/human_disease_experiments_full.tsv"
        ],
        "uncompress": false,
        "release": "version:get_release",
        "schedule": "0 2 * * 0"
    },
    "uploader": {
        "parser": "parser:load_data",
        "on_duplicates": "error"
    }
}
```

Key manifest notes:
- `release` references a `version.py` function for scheduled re-dumps
- `schedule` is a cron string for automated re-ingestion — only used in production Hub deployments, omit for prototypes

### parser.py (key pattern — condensed)
```python
import os, csv
from itertools import groupby
from operator import itemgetter
from biothings_client import get_client

def batch_query_mondo_from_doid(doid_list):
    """Convert DOID list to MONDO IDs via mydisease.info client."""
    mapping_dict = {}
    client = get_client('disease')
    for i in range(0, len(doid_list), 1000):   # batch of 1000 max
        batch = doid_list[i:i+1000]
        res = client.querymany(','.join(batch), scopes="mondo.xrefs.doid", fields="_id")
        for doc in res:
            mapping_dict[doc['query']] = doc.get('_id', doc['query'])
    return mapping_dict

def load_ep_kn_data(file_path, category):
    """Load experiments or knowledge file (same schema, different category label)."""
    rows = []
    with open(file_path) as f:
        fieldnames = ['ensembl', 'symbol', 'doid', 'name', 'source', 'evidence', 'confidence']
        reader = csv.DictReader(f, fieldnames=fieldnames, delimiter='\t')
        for row in reader:
            row['confidence'] = float(row['confidence'])
            row['category'] = category
            rows.append(row)
    return rows

def load_data(data_folder):
    # Load and concatenate all three files
    all_rows = (
        load_ep_kn_data(os.path.join(data_folder, "human_disease_knowledge_full.tsv"), 'knowledge') +
        load_ep_kn_data(os.path.join(data_folder, "human_disease_experiments_full.tsv"), 'experiments')
    )
    # Sort by grouping key before groupby — required by itertools.groupby
    all_rows = sorted(all_rows, key=itemgetter('doid'))

    for key, group in groupby(all_rows, key=itemgetter('doid')):
        if not key.startswith("DOID:"):
            continue
        merged = []
        name = None
        for row in group:
            name = row.pop("name")
            row.pop("doid")
            merged.append(row)
        yield {
            "_id": key,
            "DISEASES": {
                "doid": key,
                "name": name,
                "associatedWith": merged   # list of per-evidence records
            }
        }
```

Key parser notes:
- **Must sort before groupby** — `itertools.groupby` only groups consecutive identical keys
- `associatedWith` list pattern: one list entry per source/evidence record, all sharing the same disease `_id`
- Cross-API resolution (`batch_query_mondo_from_doid`) is called separately and used to remap `_id` from DOID to MONDO — currently commented out in production but the pattern is canonical
- `fieldnames` passed explicitly to `DictReader` because the TSV has no header row

---

## Pattern 2: Multi-file gzip TSV + pandas groupby + UMLS→MONDO resolution
**Plugin**: disgenet (mydisease.info)
**When to use**: Large gzip TSV files; multi-level groupby aggregation; mapping from non-standard IDs (UMLS) to MONDO via a bundled OBO file; merging gene and variant association files on a shared disease key.

### manifest.json
```json
{
    "version": "1.0",
    "requires": ["pandas"],
    "__metadata__": {
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "license": "CC BY 4.0",
        "url": "https://www.disgenet.org/static/disgenet_ap1/files/downloads/readme.txt"
    },
    "dumper": {
        "data_url": [
            "http://purl.obolibrary.org/obo/mondo.json",
            "https://www.disgenet.org/static/disgenet_ap1/files/downloads/all_gene_disease_pmid_associations.tsv.gz",
            "https://www.disgenet.org/static/disgenet_ap1/files/downloads/all_variant_disease_pmid_associations.tsv.gz",
            "https://www.disgenet.org/static/disgenet_ap1/files/downloads/disease_mappings.tsv.gz"
        ],
        "uncompress": false,
        "release": "version:get_release",
        "mapping": "mapping:get_customized_mapping"
    },
    "uploader": {
        "parser": "parser:load_data",
        "on_duplicates": "ignore",
        "mapping": "mapping:get_customized_mapping"
    }
}
```

Key manifest notes:
- `uncompress: false` — pandas reads `.gz` natively via `compression="gzip"`; do NOT set `uncompress: true` for gzip
- `mapping` references a `mapping.py` function — only needed for production Hub deployments
- `on_duplicates: "ignore"` because multiple UMLS IDs can map to the same MONDO ID

### parser.py (key pattern — condensed)
```python
import json, os
from collections import defaultdict
import numpy as np
import pandas as pd
from biothings.utils.dataload import dict_sweep, unlist

def process_gene(file_path):
    """Group gene-disease associations by (UMLS disease ID, source, gene ID), merge pubmed sets."""
    df = pd.read_csv(file_path, encoding="ISO-8859-1", sep="\t", comment="#", compression="gzip")
    df = df.where(pd.notnull(df), None)   # replace NaN with None
    d = defaultdict(list)
    for grp, subdf in df.groupby(["diseaseId", "source", "geneId"]):
        doc = {"source": grp[1], "gene_id": int(grp[2]), "pubmed": set()}
        for rec in subdf.to_dict(orient="records"):
            for k, v in rec.items():
                if isinstance(v, np.int64):
                    rec[k] = int(v)       # always convert numpy.int64 → Python int
                if k in ["geneSymbol", "DSI", "DPI", "score", "EI"]:
                    doc[k] = v
                elif k == "pmid" and v:
                    doc["pubmed"].add(int(v))
        doc["pubmed"] = list(doc["pubmed"])
        d[grp[0]].append(doc)            # key by UMLS disease ID
    return d

def construct_umls_to_mondo(mondo_json_path):
    """Build UMLS→MONDO mapping from the bundled mondo.json OBO graph."""
    umls_2_mondo = defaultdict(list)
    with open(mondo_json_path) as f:
        data = json.loads(f.read())
    for node in data["graphs"][0]["nodes"]:
        if not node.get("id", "").startswith("http://purl.obolibrary.org/obo/MONDO_"):
            continue
        for xref in node.get("meta", {}).get("xrefs", []):
            if xref["val"].startswith("UMLS:"):
                mondo_id = "MONDO:" + node["id"].split("_")[-1]
                umls_2_mondo[xref["val"][5:]].append(mondo_id)
    return umls_2_mondo

def load_data(data_folder):
    d_gene = process_gene(os.path.join(data_folder, "all_gene_disease_pmid_associations.tsv.gz"))
    umls_2_mondo = construct_umls_to_mondo(os.path.join(data_folder, "mondo.json"))

    for umls_id in d_gene:
        mondo_ids = umls_2_mondo.get(umls_id, [umls_id])  # fall back to UMLS if no MONDO mapping
        for mondo_id in mondo_ids:
            doc = {
                "_id": mondo_id,
                "disgenet": {
                    "genes_related_to_disease": d_gene.get(umls_id, []),
                }
            }
            yield dict_sweep(unlist(doc), [None])
```

Key parser notes:
- Always `df = df.where(pd.notnull(df), None)` immediately after reading — eliminates NaN in output
- Always convert `numpy.int64` → `int` before yielding — Hub rejects numpy types
- Use `set()` for pubmed deduplication during groupby, convert to `list()` before yield
- Bundle a reference ontology file (here `mondo.json`) in `data_url` to enable ID resolution without network calls at parse time
- `defaultdict(list)` + `d[key].append(doc)` is the idiomatic pattern for building grouped associations

---

## Pattern 3: JSON file + subject/object/relation triple structure + composite _id
**Plugin**: FoodData_parser (pending.api)
**When to use**: Source is JSON (not tabular); records represent relationships between two entity types (food ↔ nutrient); `_id` must be composite because neither entity alone is unique per document.

### manifest.json
```json
{
    "version": "0.2",
    "__metadata__": {
        "url": "https://fdc.nal.usda.gov/index.html"
    },
    "author": {
        "name": "Rohan Juneja",
        "url": "https://github.com/rjawesome"
    },
    "dumper": {
        "data_url": [
            "https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_foundation_food_json_2022-04-28.zip",
            "https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_foundation_food_csv_2022-04-28.zip"
        ],
        "uncompress": true
    },
    "uploader": {
        "parser": "parser:load_data",
        "on_duplicates": "error"
    }
}
```

Key manifest notes:
- `uncompress: true` — required for `.zip` files; the Hub will unzip before the parser runs
- `author` is a top-level key alongside `__metadata__` (not nested inside it)
- `version: "0.2"` appears in some older plugins; always use `"1.0"` for new plugins

### parser.py (key pattern — condensed)
```python
import orjson, os

def load_data(data_folder):
    # orjson is faster than stdlib json for large files
    with open(os.path.join(data_folder, "FoodData_Central_foundation_food_json_2022-04-28.json"), "rb") as f:
        foods = orjson.loads(f.read())["FoundationFoods"]

    for food in foods:
        base_subject = {
            "description": food["description"],
            "fdcId": food["fdcId"],
            "foodCategory": food["foodCategory"]["description"]
        }
        for nutrient in food["foodNutrients"]:
            doc = {
                "_id": f"{food['fdcId']}-{nutrient['nutrient']['id']}",   # composite ID
                "subject": base_subject,                                    # the food
                "object": {                                                 # the nutrient
                    "nutrientName": nutrient["nutrient"]["name"],
                    "chebiId": chebi_mappings.get(nutrient["nutrient"]["name"])
                },
                "relation": {                                               # the measurement
                    "amount": nutrient.get("amount"),
                    "unit": nutrient["nutrient"]["unitName"]
                }
            }
            yield doc
```

Key parser notes:
- **subject/object/relation** is the canonical BioThings triple structure for relational data — use it whenever a document represents a *relationship* between two entity types rather than a single entity
- **Composite `_id`**: `f"{entity1_id}-{entity2_id}"` — safe when neither alone is unique per output document
- `orjson` (import as `orjson`) is preferred over `json` for files >100 MB — must add `"requires": ["orjson"]` to manifest
- Open JSON in `"rb"` mode (bytes) when using `orjson.loads()`

---

## Pattern 4: Shared OBO parser via parser_kwargs (no custom parser.py)
**Plugin**: go (pending.api)
**When to use**: Source is an OBO ontology file. The BioThings Hub has a built-in OBO parser — do not write a custom one.

### manifest.json
```json
{
    "version": "0.2",
    "__metadata__": {
        "url": "http://geneontology.org/docs/go-citation-policy/",
        "license_url": "https://creativecommons.org/licenses/by/4.0/legalcode",
        "license": "Creative Commons Attribution 4.0 Unported License",
        "author": {
            "name": "Eric Zhou",
            "url": "https://github.com/ericz1803"
        }
    },
    "dumper": {
        "data_url": "http://purl.obolibrary.org/obo/go.obo",
        "uncompress": false,
        "schedule": "0 1 * * *"
    },
    "uploader": {
        "parser": "hub.dataload.data_parsers:load_obo",
        "parser_kwargs": {
            "obofile": "go.obo"
        },
        "on_duplicates": "error"
    }
}
```

Key manifest notes:
- `parser` references the Hub's shared module path: `"hub.dataload.data_parsers:load_obo"`
- `parser_kwargs` is passed as keyword arguments to the parser function — here, `obofile` names the downloaded file
- No `parser.py` is needed — do not create one
- This pattern applies to any OBO file: GO, HPO, DOID, MONDO, UBERON, etc. Just change `obofile` to match the downloaded filename
- Other shared parsers may exist in `hub.dataload.data_parsers` — check the Hub source before writing a custom OBO/ontology parser

---

## Quick Reference: Pattern Selection

| Data format | Record structure | Use pattern |
|-------------|-----------------|-------------|
| TSV, multiple files, shared grouping key | Merge into one doc per key | Pattern 1 (DISEASES) |
| TSV.gz, pandas-friendly, multi-level groupby | Aggregate with set deduplication | Pattern 2 (disgenet) |
| JSON, relational (entity A ↔ entity B) | subject/object/relation triple | Pattern 3 (FoodData) |
| OBO ontology file | Ontology terms | Pattern 4 (go) — shared parser |
| API available (preferred) | Paginate API, dump JSON, then parse | See SKILL.md Section 1c PGxDB/IGVF pattern |
| CSV, single file, no aggregation | Simple row → doc | See SKILL.md Section 3 base template |
| Multiple CSVs, potential ID overlap | Multi-file glob + seen_ids | See SKILL.md Section 3 ECBD pattern |
