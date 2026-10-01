# Mapping Generation Reference

Detailed reference for SKILL.md §3b. Covers type inference, conflict resolution, and the `mapping.py` convention for generating an Elasticsearch mapping from post-parser BioThings documents.

Conceptual model: this mirrors BioThings' own `inspect --mode mapping` behavior — inspect actual documents, infer field types/structure, generate the mapping, then validate it against the same documents before considering the plugin complete.

## Why post-parser, not source schema

The mapping describes what the **parser yields**, not what the raw source file looks like. A source CSV column typed as text can become a nested object, a list, or a converted numeric/date field after parsing — the mapping must reflect that final shape. Always generate `mapping.py` after `parser.py` can actually run, using real output documents (e.g. from `biothings-cli dataplugin upload` + `inspect`, or a standalone script that calls `load_data()` and collects a sample).

## Type Inference Table

| Observed Python value | Elasticsearch mapping | Notes |
|---|---|---|
| `str` (short, categorical/ID-like: symbols, codes, xrefs) | `{"type": "keyword"}` | Default for strings — exact match, aggregatable, sortable |
| `str` (free text: descriptions, abstracts, names meant for full-text search) | `{"type": "text"}` | Add a `.raw` keyword subfield (`"fields": {"raw": {"type": "keyword"}}`) if both full-text search and exact match/aggregation are needed |
| `int` / `numpy.int64` (fits 32-bit) | `{"type": "integer"}` | |
| `int` / `numpy.int64` (exceeds 32-bit range, e.g. large PubMed/identifier counters) | `{"type": "long"}` | Widen only when an observed value actually requires it |
| `float` / `numpy.float64` | `{"type": "float"}` | Use `{"type": "double"}` only if precision loss is observed/expected to matter |
| `bool` | `{"type": "boolean"}` | |
| ISO 8601 date string, `datetime.date`/`datetime.datetime` | `{"type": "date"}` | Confirm the parser actually normalizes to ISO 8601 — if dates are still loosely-formatted strings, fix the parser rather than mapping the field as `keyword` |
| `dict` | `{"properties": {...}}` (recurse) | Recurse into each key using this same table |
| `list` | mapping of the **element** values, not a separate "array" type | Elasticsearch has no array type — any field can hold zero, one, or many values of its mapped type. Infer from the elements: if elements are scalars, use the scalar's mapping; if elements are dicts, recurse into `properties` as if it were a single object |
| `None` / key missing from all sampled docs | do not map | Never infer a type from null alone; never let an all-null field default to `text`. If the field is expected to appear in a larger production run, note it in `README.md` rather than guessing a type from zero evidence |

## Conflict Resolution

When the same field holds values of different apparent types across the sampled documents:

1. **Numeric-looking strings mixed with real numbers** (e.g. `"123"` and `123`) — the parser should already normalize this; if it doesn't, treat as `keyword` (safe superset) and flag the parser for a fix, since implicit numeric coercion of a `keyword`-typed field silently loses type fidelity on write.
2. **Scalar in some docs, list in others** (e.g. `"xref": "P12345"` vs `"xref": ["P12345", "P67890"]`) — this is NOT a conflict. Elasticsearch scalar and list-of-scalar fields share the same mapping. Map using the scalar's type.
3. **Object in some docs, scalar in others** (e.g. `"source": {"name": "X", "id": 1}` vs `"source": "X"`) — this IS a genuine structural conflict. Do not silently emit a mapping for either shape. Fix the parser to normalize to one shape (preferred), or if the source data is genuinely inconsistent and both shapes must be preserved, flag the field in `README.md` under "Mapping Conflicts" with the resolution chosen (usually: normalize to the more common/expected shape and document the loss for the rarer shape).
4. **Object in some docs, list-of-objects in others** — same object shape, so this is not a type conflict; map the shared object's `properties`.
5. **Empty dict `{}` or empty list `[]` with no populated example anywhere in the sample** — treat like an all-null field: do not map from zero evidence; flag for review if the field is expected to be populated at larger scale.

Always widen towards the mapping that safely represents every observed value rather than picking the mapping that happens to fit the first document sampled.

## `mapping.py` Convention

```python
def get_customized_mapping(cls):
    return {
        "<datasource_name>": {
            "properties": {
                "name": {"type": "keyword"},
                "description": {
                    "type": "text",
                    "fields": {"raw": {"type": "keyword"}}
                },
                "score": {"type": "float"},
                "release_date": {"type": "date"},
                "xrefs": {
                    "properties": {
                        "pubchem": {"type": "keyword"},
                        "chembl": {"type": "keyword"}
                    }
                },
                "associated_with": {
                    "properties": {
                        "pmid": {"type": "long"},
                        "relation": {"type": "keyword"}
                    }
                }
            }
        }
    }
```

- `get_customized_mapping` is the exact function name the BioThings Hub looks up via `uploader.mapping: "mapping:get_customized_mapping"` in `manifest.json` (see [manifest-schema.md](manifest-schema.md)).
- `cls` is passed by the Hub (the uploader class) — accept it even if unused.
- Nest the mapping under the same top-level datasource key the parser uses in `parser.py`, so the mapping's shape lines up 1:1 with real documents.
- `_id` is never included in `properties` — Elasticsearch handles `_id` outside the mapped fields.

## Validation Checklist (before declaring the plugin complete)

- [ ] Every field present in the representative sample documents has a corresponding entry in `mapping.py`'s `properties` (no silently-dropped fields)
- [ ] No field's mapped type contradicts an observed value (run `inspect --mode mapping` per [cli-validation-workflow.json](cli-validation-workflow.json) step 6 and diff against `mapping.py`)
- [ ] Nested objects preserve their full `properties` structure — no flattening of sub-objects into dotted keyword strings
- [ ] Array/list fields are mapped using their element type, not an invalid/nonexistent "array" type
- [ ] Date fields are backed by parser output that's actually ISO 8601 (or another format Elasticsearch's date detection accepts) — not arbitrary strings mapped as `date` on faith
- [ ] Any field flagged as a genuine type conflict is documented in `README.md` under "Mapping Conflicts" with the resolution taken
- [ ] `manifest.json`'s `uploader.mapping` points at `mapping:get_customized_mapping` and the function name/module match exactly
