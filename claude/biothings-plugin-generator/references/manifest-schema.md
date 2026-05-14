# manifest.json Schema Reference

Complete field reference for BioThings data plugin manifests.
Validated against production plugins in pending.api and mydisease.info.

---

## Top-level Structure

```
{
    "version":       <string>       REQUIRED
    "requires":      <list|omit>    OPTIONAL
    "__metadata__":  <object>       REQUIRED
    "author":        <object|omit>  OPTIONAL
    "dumper":        <object>       REQUIRED
    "uploader":      <object>       REQUIRED (singular)
    "uploaders":     <list|omit>    OPTIONAL — only for multi-entity plugins; mutually exclusive with "uploader"
}
```

---

## Field Reference

### `version`
- **Type**: string
- **Required**: yes
- **Valid values**: `"1.0"` for all new plugins
  - Note: `"0.1"` and `"0.2"` appear in older production plugins — do not use for new work
- **Example**: `"version": "1.0"`

---

### `requires`
- **Type**: list of strings
- **Required**: no — omit entirely if only stdlib + biothings SDK are needed
- **Purpose**: Python packages pip-installed by the Hub before running the parser
- **Common values**: `"pandas"`, `"orjson"`, `"requests"`, `"biothings_client"`
- **Do NOT include**: `"biothings"`, `"os"`, `"csv"`, `"json"` — these are always available
- **Example**: `"requires": ["pandas", "orjson"]`

---

### `__metadata__`
- **Type**: object
- **Required**: yes — always include, even for prototypes
- **Sub-fields**:

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `name` | yes | string | Display name of the datasource, e.g. `"European Chemical Biology Database"` |
| `description` | yes | string | One sentence describing what the datasource contains |
| `license` | yes | string | Short license name, e.g. `"CC BY 4.0"`, `"CC0 1.0"`, `"MIT"` |
| `license_url` | yes | string | Direct URL to license text |
| `url` | yes | string | Datasource homepage (not download URL) |
| `author` | no | object | Nested `{"name": "...", "url": "..."}` — see note below |

> **Note on `author`**: In older plugins (FoodData, go) `author` appears as a top-level key alongside `__metadata__`. In newer plugins it may be nested inside `__metadata__`. Either placement is accepted by the Hub. Prefer top-level for consistency with older plugins; nested is fine too. Do not put it in both places.

- **Example**:
```json
"__metadata__": {
    "name": "Example Datasource",
    "description": "A curated database of biomedical associations between genes and diseases.",
    "license": "CC BY 4.0",
    "license_url": "https://creativecommons.org/licenses/by/4.0/",
    "url": "https://datasource-homepage.org"
}
```

---

### `dumper`
- **Type**: object
- **Required**: yes
- **Sub-fields**:

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `data_url` | yes* | string or list | Direct download URL(s). Use list for multiple files. |
| `uncompress` | yes | boolean | `true` for `.zip`; `false` for `.gz`, `.tsv`, `.csv`, `.json` |
| `release` | yes | string | Always `"version:get_release"` — references the `get_release` function in `version.py` |
| `schedule` | no | string | Cron expression for Hub auto-re-dump. Omit for prototypes. |

> *`data_url` may be omitted when a custom `dumper.py` handles fetching (API-only sources). In that case the Hub calls the custom dumper class directly.

**`data_url` rules:**
- Must be a direct-download link (no redirect, no login required)
- Single file: plain string — `"data_url": "https://example.org/data.tsv.gz"`
- Multiple files: list — `"data_url": ["https://example.org/a.csv", "https://example.org/b.csv"]`
- All files land in the same `data_folder`; the parser must handle all of them
- Only list files the parser actually reads — do not include supplementary or documentation files

**`uncompress` decision table:**

| File type | `uncompress` value | Why |
|-----------|-------------------|-----|
| `.zip` | `true` | Hub unzips before parser runs |
| `.tar.gz` | `true` | Hub untars before parser runs |
| `.gz` (pandas) | `false` | pandas reads gzip natively |
| `.gz` (open_anyfile) | `false` | `biothings.utils.common.open_anyfile` handles gzip |
| `.csv`, `.tsv`, `.json` | `false` | No compression |

- **Example (single file)**:
```json
"dumper": {
    "data_url": "https://example.org/data.tsv.gz",
    "uncompress": false,
    "release": "version:get_release"
}
```

- **Example (multi-file)**:
```json
"dumper": {
    "data_url": [
        "https://example.org/compounds.csv",
        "https://example.org/fragments.csv"
    ],
    "uncompress": false,
    "release": "version:get_release"
}
```

---

### `uploader` (singular)
- **Type**: object
- **Required**: yes (use this for the vast majority of plugins)
- **Use when**: One parser handles all downloaded files and produces one document type
- **Sub-fields**:

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `parser` | yes | string | `"module:function"` — e.g. `"parser:load_data"` |
| `on_duplicates` | yes | string | `"error"` or `"ignore"` — see below |
| `mapping` | no | string | `"mapping:get_customized_mapping"` — only for production with `mapping.py` |
| `parser_kwargs` | no | object | Dict passed as kwargs to parser function — used with shared parsers |

**`on_duplicates` decision:**
- `"error"` — default; the Hub raises an error if two documents share the same `_id`. Use this unless you explicitly expect duplicates.
- `"ignore"` — silently skips duplicate `_id`s, keeping the first. Use when:
  - Multiple source files can contain the same entity (multi-file with `seen_ids` pattern)
  - Multiple source IDs map to the same target `_id` (e.g., multiple UMLS CUIs → same MONDO ID)

**`parser` format**: `"<module_name>:<function_name>"`
- Local parser: `"parser:load_data"` — refers to `parser.py` → `load_data()` in the same directory
- Shared Hub parser: `"hub.dataload.data_parsers:load_obo"` — built-in OBO parser
- The function must accept `data_folder` as its first argument (plus any `parser_kwargs`)

- **Example (standard)**:
```json
"uploader": {
    "parser": "parser:load_data",
    "on_duplicates": "error"
}
```

- **Example (shared OBO parser)**:
```json
"uploader": {
    "parser": "hub.dataload.data_parsers:load_obo",
    "parser_kwargs": {
        "obofile": "go.obo"
    },
    "on_duplicates": "error"
}
```

---

### `uploaders` (plural)
- **Type**: list of uploader objects
- **Required**: no
- **Use when**: The same dump produces multiple distinct entity types that need separate parsers (rare)
- **Each entry adds**: a `"name"` field to distinguish uploaders

- **Example**:
```json
"uploaders": [
    {
        "name": "gene_associations",
        "parser": "parser:load_gene_data",
        "on_duplicates": "error"
    },
    {
        "name": "variant_associations",
        "parser": "parser:load_variant_data",
        "on_duplicates": "error"
    }
]
```

> Do NOT use `uploaders` just because there are multiple input files. Use `uploader` (singular) and have the single parser iterate all files. Use `uploaders` only when the output document types are fundamentally different (e.g., genes AND variants from the same dump).

---

## Complete Validated Examples

### Minimal — single CSV, no optional fields
```json
{
    "version": "1.0",
    "__metadata__": {
        "name": "Example Datasource",
        "description": "A curated database of example biomedical data.",
        "license": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "url": "https://datasource-homepage.org"
    },
    "dumper": {
        "data_url": "https://datasource.org/download/data.csv",
        "uncompress": false,
        "release": "version:get_release"
    },
    "uploader": {
        "parser": "parser:load_data",
        "on_duplicates": "error"
    }
}
```

### Standard — multi-file gzip, pandas required, on_duplicates ignore
```json
{
    "version": "1.0",
    "requires": ["pandas"],
    "__metadata__": {
        "name": "Example Datasource",
        "description": "Gene-disease and variant-disease associations with evidence scores.",
        "license": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "url": "https://datasource-homepage.org"
    },
    "dumper": {
        "data_url": [
            "https://datasource.org/download/associations.tsv.gz",
            "https://datasource.org/download/mappings.tsv.gz"
        ],
        "uncompress": false
    },
    "uploader": {
        "parser": "parser:load_data",
        "on_duplicates": "ignore"
    }
}
```

### ZIP file — uncompressed before parsing
```json
{
    "version": "1.0",
    "__metadata__": {
        "name": "Example Datasource",
        "description": "Comprehensive food nutrient composition data from USDA.",
        "license": "CC0 1.0",
        "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "url": "https://datasource-homepage.org"
    },
    "dumper": {
        "data_url": "https://datasource.org/download/fulldb.zip",
        "uncompress": true
    },
    "uploader": {
        "parser": "parser:load_data",
        "on_duplicates": "error"
    }
}
```

### OBO ontology — shared parser, no parser.py
```json
{
    "version": "1.0",
    "__metadata__": {
        "name": "Example Ontology",
        "description": "Structured ontology of biomedical terms and their relationships.",
        "license": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "url": "https://datasource-homepage.org"
    },
    "dumper": {
        "data_url": "https://datasource.org/ontology.obo",
        "uncompress": false
    },
    "uploader": {
        "parser": "hub.dataload.data_parsers:load_obo",
        "parser_kwargs": {
            "obofile": "ontology.obo"
        },
        "on_duplicates": "error"
    }
}
```

### API-only source — custom dumper.py (no data_url)
When a custom `dumper.py` exists alongside `parser.py`, the manifest still declares a `dumper` block but `data_url` may be omitted or set to a placeholder — the Hub invokes the custom dumper class directly.
```json
{
    "version": "1.0",
    "requires": ["requests"],
    "__metadata__": {
        "name": "Example API Datasource",
        "description": "Drug-target interaction data retrieved via the datasource REST API.",
        "license": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "url": "https://datasource-homepage.org"
    },
    "dumper": {
        "data_url": "https://api.datasource.org/v1/entities"
    },
    "uploader": {
        "parser": "parser:load_data",
        "on_duplicates": "error"
    }
}
```

---

## Common Mistakes

| Mistake | Correct |
|---------|---------|
| `"uncompress": true` for `.gz` files | `"uncompress": false` — pandas/open_anyfile reads gzip natively |
| `"uncompress": false` for `.zip` files | `"uncompress": true` — the Hub must unzip before parsing |
| Using `uploaders` for multi-file sources | Use `uploader` (singular) — let the parser iterate files |
| Omitting `__metadata__` | Always include it with `name`, `description`, `license`, `license_url`, and `url` |
| Missing `name` or `description` in `__metadata__` | Both are required — always include them |
| Omitting `release` from `dumper` | Always include `"release": "version:get_release"` — requires a `version.py` alongside `parser.py` |
| `"version": "0.1"` or `"0.2"` | Always use `"version": "1.0"` for new plugins |
| `"requires": ["biothings"]` | Omit — biothings SDK is always available |
| `"requires": ["os"]`, `"requires": ["csv"]` | Omit — stdlib is always available |
| `"data_url"` pointing to a landing page | Must be a direct download link (curl-able) |
