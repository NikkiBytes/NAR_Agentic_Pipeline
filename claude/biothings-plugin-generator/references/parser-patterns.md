# Parser Patterns Reference

Common parser patterns from production BioThings plugins. Load this file when choosing a parser template for a new plugin.

For complete annotated production examples, see [production-plugin-examples.md](production-plugin-examples.md).

---

## Simple CSV/TSV with groupby (DISEASES pattern)
```python
import os, csv
from itertools import groupby
from operator import itemgetter

def load_data(data_folder):
    infile = os.path.join(data_folder, "data.tsv")
    rows = []
    with open(infile) as f:
        for row in csv.DictReader(f, delimiter='\t'):
            rows.append(row)
    rows = sorted(rows, key=itemgetter('disease_id'))
    for key, group in groupby(rows, key=itemgetter('disease_id')):
        merged = [doc for doc in group]
        yield {"_id": key, "source": {"associatedWith": merged}}
```

## Pandas groupby for multi-row aggregation (DisGeNET pattern)
```python
import os
from collections import defaultdict
import pandas as pd
from biothings.utils.dataload import dict_sweep, unlist

def load_data(data_folder):
    df = pd.read_csv(os.path.join(data_folder, "data.tsv.gz"),
                     sep="\t", comment="#", compression="gzip")
    df = df.where(pd.notnull(df), None)
    d = defaultdict(list)
    for grp, subdf in df.groupby(["diseaseId", "source", "geneId"]):
        records = subdf.to_dict(orient="records")
        doc = {"source": grp[1], "gene_id": int(grp[2]), "pubmed": []}
        for rec in records:
            if rec.get("pmid"):
                doc["pubmed"].append(int(rec["pmid"]))
        d[grp[0]].append(doc)
    for _id, records in d.items():
        yield dict_sweep(unlist({"_id": _id, "source": {"genes": records}}), [None])
```

## Variant HGVS ID generation (CCLE/FIRE pattern)
```python
import os, logging
from biothings.utils.common import open_anyfile
import myvariant.src.utils.hgvs as hgvs

def load_data(data_file):
    with open_anyfile(data_file) as f:
        for line in f:
            try:
                parts = line.strip().split("\t")
                _id = hgvs.get_hgvs_from_vcf(parts[0], parts[1], parts[2], parts[3])
                yield {"_id": _id, "source": {"score": float(parts[4])}}
            except Exception as e:
                logging.error("Error with line %s: %s" % (line.strip(), e))
```

## Cross-API ID resolution (DISEASES pattern)
```python
from biothings_client import get_client

def batch_query_mondo_from_doid(doid_list):
    client = get_client('disease')
    mapping = {}
    for i in range(0, len(doid_list), 1000):
        batch = doid_list[i:i+1000]
        res = client.querymany(batch, scopes="mondo.xrefs.doid", fields="_id")
        for doc in res:
            mapping[doc['query']] = doc.get('_id', doc['query'])
    return mapping
```

## Multi-file CSV with deduplication (ECBD pattern)
Use when `data_url` is a list of CSVs with potential ID overlap between files:
```python
import os, csv, glob, logging
from biothings.utils.dataload import dict_sweep, unlist

logger = logging.getLogger(__name__)

def load_data(data_folder):
    csv_files = sorted(glob.glob(os.path.join(data_folder, "*.csv")))
    assert csv_files, f"No CSV files found in {data_folder}"
    seen_ids = set()
    for infile in csv_files:
        logger.info("Parsing %s", os.path.basename(infile))
        for doc in _parse_csv(infile, seen_ids):
            yield doc

def _parse_csv(filepath, seen_ids):
    with open(filepath, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            _id = row.get("id_field")
            if not _id or _id in seen_ids:
                continue
            seen_ids.add(_id)
            doc = {"_id": _id, "source": {"field": row.get("field")}}
            yield dict_sweep(unlist(doc), [None])
```

## JSON with orjson (FoodData pattern)
```python
import os, orjson

def load_data(data_folder):
    with open(os.path.join(data_folder, "data.json"), "rb") as f:
        data = orjson.loads(f.read())
    for record in data:
        yield {"_id": str(record["id"]), "source": record}
```

## Pre-dumped JSON files pattern
Use when the `data_folder` contains one or more JSON files (for example, manually pre-dumped API results staged into the folder by a user). The generator itself still uses manifest-based bulk download — this pattern only covers the parser side:
```python
# parser.py — reads JSON files staged in data_folder
import os, json, glob, logging
from biothings.utils.dataload import dict_sweep, unlist

logger = logging.getLogger(__name__)

def load_data(data_folder):
    json_files = sorted(glob.glob(os.path.join(data_folder, "*.json")))
    assert json_files, f"No JSON files found in {data_folder}"
    for jf in json_files:
        logger.info("Parsing %s", os.path.basename(jf))
        with open(jf, "r") as f:
            records = json.load(f)
        for rec in records:
            _id = rec.get("id") or rec.get("_id")
            if not _id:
                continue
            doc = {
                "_id": str(_id),
                "source": rec  # adapt: nest under datasource key, clean fields
            }
            yield dict_sweep(unlist(doc), [None])
```
Automated API-crawling `dumper.py` support is backlog — see `BACKLOG.md`.

---

## Quick Reference: Pattern Selection

- TSV, multiple files, shared grouping key → Pattern: DISEASES (groupby)
- TSV.gz, pandas-friendly, multi-level groupby → Pattern: disgenet (pandas)
- JSON, relational (entity A ↔ entity B) → Pattern: FoodData (subject/object/relation)
- OBO ontology file → Pattern: go (shared parser, no custom parser.py)
- CSV, single file, no aggregation → Simple row → doc (base template in SKILL.md §3)
- Multiple CSVs, potential ID overlap → Multi-file glob + seen_ids (ECBD pattern)
