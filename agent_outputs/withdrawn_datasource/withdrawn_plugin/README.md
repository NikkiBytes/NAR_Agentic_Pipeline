# Withdrawn 2.0 — Design Rationale

## Quick Stats

| Metric | Value |
|---|---|
| Source file | `withdrawns.csv` (1.58 MB, 647 data rows) |
| Documents yielded | 636 |
| Rows skipped | 11 (no usable InChIKey — see below) |
| Deduplication | 0 (all 636 InChIKeys unique; `seen_ids` guard is defensive only) |
| Target API | MyChem.info |
| Data format | CSV (single file, comma-delimited, embedded MDL molfile blocks in one column) |
| Total file size | 1.58 MB |

## Why These Dump Files Were Chosen

The Withdrawn 2.0 homepage (`https://bioinformatics.charite.de/withdrawn_3/index.php`) is a server-rendered PHP site with no bulk-download link on the landing page. Per the JS-Rendered Download Page Protocol, the FAQ page (`subpages/faq.php`) was checked next and links a bulk CSV under a relative `./downloads/` path. The literal relative path (`subpages/downloads/...`) 404s; the actual file lives one directory up, at the canonical URL:

- **Selected**: `https://bioinformatics.charite.de/withdrawn_3/downloads/withdrawns.csv` — confirmed via `curl -sIL` returning `200 OK` / `content-type: text/csv` / `content-length: 1654963`. Contains all 647 rows: chemical structure fields (SMILES/InChI/InChIKey/formula), cross-references (PubChem CID, ChEMBL ID, DrugBank ID, ATC codes, CTD ID), and withdrawal-specific curation (toxicity class/type, LD50, withdrawal countries, first/last-withdrawn years, first-approval year, provenance dataset tag).
- **Rejected**: `w200_checklist.csv` (10 KB) — an example/sample synonym-mapping file for a single drug (Ethinylestradiol), used by the site's own QA process, not a data file to ingest.
- **Not ingested (UI-only)**: Mechanism-of-action predictions (ChEMBL 29-derived) and KEGG disease-pathway enrichment results, both described in the NAR paper as key analysis features, are computed on-demand per drug through the web search UI and are not present in the bulk CSV. These are out of scope for the manifest-based bulk-download ingestion path used here; flagged as a paper-vs-reality partial mismatch.

## Why the Parser Works the Way It Does

- **`_id` strategy**: InChIKey (`inchikey` column), matching MyChem.info's canonical identifier. 11 of 647 rows have an empty/whitespace-only InChIKey (withdrawnIDs `DB00052, DB00055, DB00095, DB00111, DB06692, DB01038, DB01079, DB11597, w93, w214, w258`) and are skipped — they have no structure to merge on. All 636 remaining InChIKeys are unique (verified by direct enumeration of the raw CSV before writing the parser), so `on_duplicates: "error"` in the manifest is safe; the parser's `seen_ids` set is a defensive guard only, not a load-bearing dedup mechanism.
- **Document structure**: One top-level `withdrawn` object per document, with four sub-objects grouping related fields: `properties` (physicochemical descriptors: MW, TPSA, H-bond donor/acceptor, rotatable bonds), `toxicity` (LD50, toxicity class, toxicity type(s), first reported death), `withdrawal` (dataset/provenance tag, approval/withdrawal years, withdrawal countries, literature reference(s)), and `xrefs` (ATC, PubChem CID, ChEMBL ID, DrugBank ID, CTD ID).
- **Fields extracted**: All columns except `id` (internal DB row number, redundant with `withdrawnID`), `molfile` (OpenBabel-generated MDL block with placeholder `0.0000` 2D coordinates — no information beyond SMILES/InChI, which are already parsed), `maccsfp`/`fp24` (raw fingerprint bit strings, trivially recomputable from SMILES and not analytically useful as opaque strings), and `inchikey_jchem` (a JChem-recomputed InChIKey that occasionally diverges from `inchikey` on the stereochemistry layer for the same compound — noise duplicate of the primary key, not additional signal).
- **List fields**: `withdrawalCountries` (`;`-delimited, e.g. `EU;JPN;PER;RUS;TUR`), `toxtype` (`,`-delimited, e.g. `neurological, dermatological`), `reference` (`; `-delimited when multiple PubMed URLs are cited), and `atc` (`;`-delimited when a drug has multiple ATC codes) are all split into lists; `unlist()` collapses single-element lists back to scalars, which is why the mapping treats list and scalar the same way.
- **Data cleaning**: A shared `_clean()` helper treats `""`, `"N/A"`, `"NA"`, `"NULL"`, `"null"`, `"none"`, `"None"` (after stripping whitespace) as missing and returns `None`, which `dict_sweep()` then removes from the final document. Numeric helpers (`_to_int`, `_to_float`) route through the same cleaning step before casting, so a stray `"N/A"` in a numeric column (e.g. `firstdeath`, which is largely `N/A`) never survives into the output.
- **Deduplication**: None needed in practice (0 InChIKey collisions across 636 valid rows); `seen_ids` remains as a guard against future data-quality regressions in the source file.

## Sample Output Documents

**Typical example** — single withdrawal country, single toxicity type:

Source cross-reference: <https://bioinformatics.charite.de/withdrawn_3/subpages/drug_info.php?id=w1>

```json
{
  "_id": "ACGUYXCXAPNIKK-UHFFFAOYSA-N",
  "withdrawn": {
    "withdrawn_id": "w1",
    "name": "Hexachlorophene",
    "inchi": "InChI=1S/C13H6Cl6O2/c14-6-2-8(16)12(20)4(10(6)18)1-5-11(19)7(15)3-9(17)13(5)21/h2-3,20-21H,1H2",
    "smiles": "Oc1c(Cl)cc(Cl)c(Cl)c1Cc1c(O)c(Cl)cc(Cl)c1Cl",
    "formula": "C13H6Cl6O2",
    "properties": {
      "molwt": 406.904,
      "tpsa": 40.5,
      "hbond_acceptor": 2,
      "hbond_donor": 2,
      "rotatable_bonds": 2
    },
    "toxicity": {
      "ld50": 100.0,
      "tox_class": 3,
      "tox_type": "neurological"
    },
    "withdrawal": {
      "dataset": "Safety Withdrawal",
      "first_approval_year": 1949,
      "first_withdrawn_year": 1972,
      "last_withdrawn_year": 1988,
      "countries": ["EU", "JPN", "PER", "RUS", "TUR"],
      "reference": "https://www.ncbi.nlm.nih.gov/pubmed/1117313"
    },
    "xrefs": {
      "atc": "D08AE01",
      "pubchem": 3598,
      "chembl": "CHEMBL496",
      "drugbank": "DB00756",
      "ctd": "D006582"
    }
  }
}
```

**Edge-case example** — multi-value `tox_type` list, `countries: "Worldwide"` (non-ISO scalar value):

Source cross-reference: <https://bioinformatics.charite.de/withdrawn_3/subpages/drug_info.php?id=w100>

```json
{
  "_id": "OYPPVKRFBIWMSX-SXGWCWSVSA-N",
  "withdrawn": {
    "withdrawn_id": "w100",
    "name": "Zimelidine",
    "inchi": "InChI=1S/C16H17BrN2/c1-19(2)11-9-16(14-4-3-10-18-12-14)13-5-7-15(17)8-6-13/h3-10,12H,11H2,1-2H3/b16-9-",
    "smiles": "CN(C)C/C=C(/c1ccc(Br)cc1)c1cccnc1",
    "formula": "C16H17BrN2",
    "properties": {
      "molwt": 317.23,
      "tpsa": 16.1,
      "hbond_acceptor": 2,
      "hbond_donor": 0,
      "rotatable_bonds": 4
    },
    "toxicity": {
      "ld50": 341.0,
      "tox_class": 4,
      "tox_type": ["neurological", "dermatological"]
    },
    "withdrawal": {
      "dataset": "Safety Withdrawal",
      "first_approval_year": 1982,
      "first_withdrawn_year": 1983,
      "last_withdrawn_year": 1983,
      "countries": "Worldwide",
      "reference": "https://www.ncbi.nlm.nih.gov/pubmed/2530181"
    },
    "xrefs": {
      "atc": "N06AB02",
      "pubchem": 5365247,
      "chembl": "CHEMBL37744",
      "drugbank": "DB04832",
      "ctd": "D015031"
    }
  }
}
```

## Field Coverage

(Computed by running `parser.load_data()` against the full downloaded file — all 636 yielded documents, not a sample.)

- `withdrawn.name`: 100.0%
- `withdrawn.inchi` / `withdrawn.smiles` / `withdrawn.formula`: 100.0%
- `withdrawn.properties.molwt`: 100.0%
- `withdrawn.properties.tpsa`: 99.8%
- `withdrawn.properties.hbond_acceptor` / `hbond_donor`: 99.8%
- `withdrawn.properties.rotatable_bonds`: 98.4%
- `withdrawn.xrefs.pubchem`: 99.5%
- `withdrawn.xrefs.atc`: 99.8%
- `withdrawn.xrefs.chembl`: 86.8%
- `withdrawn.xrefs.drugbank`: 74.1%
- `withdrawn.xrefs.ctd`: 64.9%
- `withdrawn.toxicity.ld50` / `tox_class`: 98.4%
- `withdrawn.toxicity.tox_type`: 43.2%
- `withdrawn.toxicity.first_death`: 13.5%
- `withdrawn.withdrawal.dataset`: 100.0%
- `withdrawn.withdrawal.first_approval_year`: 77.5%
- `withdrawn.withdrawal.first_withdrawn_year`: 57.9%
- `withdrawn.withdrawal.last_withdrawn_year`: 53.5%
- `withdrawn.withdrawal.countries`: 67.9%
- `withdrawn.withdrawal.reference`: 43.1%

## Test Results Summary

`biothings-cli` itself could not be exercised in this environment: every subcommand (`validate`, `dump`, `upload`, `list`, `inspect`, `inspect --mode mapping`) raises `AttributeError: module 'typer' has no attribute 'rich_utils'` at import time, a known typer 0.26.7 / biothings 1.0.2 incompatibility already logged for ~15 other plugins in `built-plugins-index.md` (see `chemprob`/`molbic` notes). This is a shared-environment issue, not specific to this plugin, and the shared environment was not patched.

Instead, the plugin was validated end-to-end by:
1. Downloading `withdrawns.csv` directly with `curl -A "Mozilla/5.0"` into a scratch data folder (simulating the dumper stage).
2. Calling `parser.load_data(data_folder)` directly from a standalone Python script (simulating the uploader stage) and materializing all yielded documents.
3. Checking document count, `_id` uniqueness/format, and field-level type/coverage across the **entire** result set (not a sample, since the source is a single 1.58 MB CSV).

**Results:**
- 647 source rows read → 636 documents yielded, 636 unique `_id` values (100% uniqueness, no collisions).
- 11 rows skipped for missing/whitespace-only `inchikey` (no MyChem-mergeable identifier).
- `_id` format: 27-character InChIKey (e.g. `ACGUYXCXAPNIKK-UHFFFAOYSA-N`) for all 636 documents — no malformed IDs observed.
- `dict_sweep`/`unlist` cleanliness: no `None`, empty string, or NaN values found in any yielded document; single-element lists (e.g. a solitary ATC code or reference URL) correctly collapsed to scalars by `unlist()`.
- Mapping validation (see below): PASS, 0 missing fields, 0 type mismatches, 0 unused mapping entries.

## Mapping Overview

`mapping.py` defines `get_customized_mapping`, nesting all fields under the parser's `withdrawn` top-level key:

- `withdrawn_id`, `name`, `inchi`, `smiles`, `formula` → `keyword`
- `properties.{molwt, tpsa}` → `float`; `properties.{hbond_acceptor, hbond_donor, rotatable_bonds}` → `integer`
- `toxicity.{ld50}` → `float`; `toxicity.tox_class` → `integer`; `toxicity.{tox_type, first_death}` → `keyword`
- `withdrawal.{first_approval_year, first_withdrawn_year, last_withdrawn_year}` → `integer`; `withdrawal.{dataset, countries, reference}` → `keyword`
- `xrefs.pubchem` → `integer`; `xrefs.{atc, chembl, drugbank, ctd}` → `keyword`

**Validation**: `inspect --mode mapping` could not be run (typer/biothings blocker above). Instead, a standalone script recursively walked all 636 yielded documents, recorded the observed Python type at every field path, and diffed that against `mapping.py`'s flattened `properties`. Result: 25/25 observed leaf fields present in the mapping, 0 missing fields, 0 type mismatches, 0 unused mapping entries (every mapped field was observed in at least one document). List-vs-scalar fields (`tox_type`, `countries`, `reference`, `atc`) were confirmed to hold homogeneous scalar-`str` elements in every observed document, consistent with mapping them by element type rather than a separate array type.

**Mapping Conflicts**: None. No field exhibited a genuine type or shape conflict (scalar-vs-object, incompatible numeric/string mixing) across the 636-document sample.
