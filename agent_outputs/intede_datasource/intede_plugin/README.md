# INTEDE Plugin — Design Rationale

## Quick Stats

| Metric | Value |
|---|---|
| Source files ingested | 5 (1 CSV + 4 long-format key-value TXT) |
| Total source rows/lines (data rows only) | 6,795 (MICBIO CSV) + ~286,669 XEOTIC attribute-lines + ~888 xref attribute-lines + ~12,353 HOSPPI-TF attribute-lines + ~53,510 methylation attribute-lines |
| Documents yielded | **921** (one per unique DME `_id`) |
| Rows skipped | 0 (every `DME\d+`-prefixed line across all 5 files was attributable to a DME already known or newly created; no row was dropped) |
| Deduplication | None needed — `_id` is the DME ID itself, and each file is grouped/merged into the same `entities` dict keyed by DME ID, so there is exactly one document per DME by construction |
| Target API | pending.api |
| Data format | 1 CSV (2.0 MB) + 4 TXT (19.3 MB + 1.2 MB + 3.6 MB + 0.17 MB) = **~26.3 MB total** |

## Why These Dump Files Were Chosen

INTEDE's `/full-data-download` page exposes 18 static files. Applying the generator's file-selection policy (most-specific/independent files preferred over supersets):

**Selected (5 files, all mutually independent — no super/subset relationship between them):**
- `P2-04-1-INTEDE_DME_Cross_Matching_ID.txt` — DME identity: UniProt ID, NCBI Gene ID, EC number. Needed to give each DME document real cross-references, not just an internal ID.
- `P1-02-1-INTEDE_XEOTIC_DME_Interaction.txt` — xenobiotic/drug modulation of DME expression or activity (induction/inhibition). The largest and most information-dense file (19.3 MB); 500 of the 921 DMEs have at least one entry.
- `P1-01-1-INTEDE_MICBIO_DME_Interaction.csv` — gut-microbiome species that further metabolize a DME-generated drug metabolite. The only plain CSV in the set; genuinely distinct relation type (microbiome, not enzyme regulation).
- `P1-03-1-INTEDE_HOSPPI_DME_Interaction_TF&Oligomerization&ncRNA&Histone_Modification.txt` — host-protein/ncRNA regulation of DME transcription (TF binding, oligomerization, histone modification).
- `P1-03-2-INTEDE_HOSPPI_DME_Interaction_DNA_Methylation.txt` — disease-associated DME promoter methylation, ICD-11 coded, with quantitative delta-beta/p-value statistics.

**Excluded (13 files) — reasons:**
- `P2-01-1..4` (DME FASTA sequence, drug-affinity data, tissue distribution, complete EC tree) — largely redundant with MyGene.info/UniProt sequence data, or (EC tree) already partially captured via `ECNUMBER` in the ingested xref file.
- `P2-02-1..4` (drug 2D/3D SDF structures, SMILES/InChI, physicochemical properties) and `P2-03-1..3` (xenobiotic structures/sequence) — these describe the **drug/xenobiotic** side with a separate ID namespace (`DR####`/structure files) that is not cross-referenced to the interaction files ingested here without an additional join; scoped out of v1 to keep the DME-centric document model tractable. A future v2 could add a `MyChem.info`-style companion plugin keyed by InChIKey using these files.
- `P2-04-2..4` (DME/drug synonyms, DME-disease ICD, drug-disease ICD) — lower-priority cross-reference tables; candidates for a v2 enrichment pass.

## Why the Parser Works the Way It Does

**`_id` strategy**: `DME___ID` (e.g. `DME0001`) — INTEDE's own stable internal identifier for each Drug-Metabolizing Enzyme. Chosen over UniProt ID because ~3.5% of DMEs (32/921) have no UniProt mapping in the source data (e.g. species-specific or "unclear mechanism" enzymes), so UniProt cannot serve as a universal primary key.

**Document structure**: One document per DME, with four independent, optional list-of-object sub-fields (`xenobiotic_interactions`, `microbiome_interactions`, `host_protein_interactions`, `methylation_interactions`) plus scalar identity fields (`name`, `species`, `uniprot`, `gene_id`, `ec_number`).

**Source file format**: INTEDE's `.txt` bulk files use a non-tabular "long" key-value-per-line format rather than a normal table, e.g.:
```
DME0001    DME___ID    DME0001
DME0001    DME_NAME    Cytochrome P450 3A4 (CYP3A4)
DME0001    XEOTICID    XEO00001    XEO_NAME    Dimethyl sulfoxide
DME0001    XEOTICID    XEO00001    MOACRIVE    Induction
```
Each row is either a **top-level attribute** (`DME_ID <TAB> KEY <TAB> VALUE`, 3 columns) or a **nested sub-entity attribute** (`DME_ID <TAB> MARKER <TAB> SUB_ID <TAB> KEY <TAB> VALUE`, 5 columns), where `MARKER` identifies the type of nested partner (`XEOTICID`, `UNIPROID`/`MIRNA_ID`, or `ICD_CODE`). The parser's `_iter_data_rows()` helper skips the human-readable header/abbreviations block (present at the top of every file) by looking for the first line whose first tab-field matches `^DME\d+$`, then classifies each subsequent row by column count and marker value. Per-file loader functions (`_load_xref`, `_load_xeotic`, `_load_micbio`, `_load_hosppi`, `_load_methylation`) build/merge a shared `entities` dict keyed by DME ID; nested sub-entities are grouped into per-DME dicts keyed by their sub-ID (`xeo_id`, `partner_id`, `icd_code`) during accumulation, then flattened to lists just before that file's loop ends.

**Fields extracted vs. skipped**: All abbreviation-block fields for the 5 ingested files are extracted. `SUBSTRAT` (HOSPPI substrate) exists in the source abbreviations but was never observed populated in the sample and is handled generically (extracted if present, dropped by `dict_sweep` if empty).

**Deduplication**: Not needed in the traditional `seen_ids` sense — because every file is grouped by DME ID (and, within a DME, by sub-entity ID) before being appended to the shared `entities` dict, duplicate rows for the same (DME, partner) pair simply overwrite/merge fields on the same sub-entity dict rather than creating a second entry. `on_duplicates: "error"` in the manifest is safe because the parser guarantees a single yield per DME ID.

**Data cleaning**: `dict_sweep(unlist(doc), [None, "", []])` removes empty/None/empty-list values and collapses any single-item lists (e.g. a DME with exactly one xenobiotic interaction) to a bare object — observed directly in the `DME1257` sample below.

## Sample Output Documents

**Typical document** (`DME0001` — Cytochrome P450 3A4, all 4 interaction types present; lists truncated here for readability, full lists confirmed populated in testing):
```json
{
  "_id": "DME0001",
  "intede": {
    "dme_id": "DME0001",
    "name": "Cytochrome P450 3A4 (CYP3A4)",
    "species": "Homo sapiens",
    "uniprot": "CP3A4_HUMAN",
    "gene_id": "1576",
    "ec_number": "1.14.14.55",
    "xenobiotic_interactions": [
      {
        "xeotic_id": "XEO00001",
        "name": "Dimethyl sulfoxide",
        "type": "Pharmaceutical Agent(s)",
        "classification": "Approved/Marketed Drug",
        "description": "Dimethyl sulfoxide up-regulates the expression of DME CYP3A4",
        "gene_form": "mRNA",
        "modulation_type": "Induction"
      }
    ],
    "microbiome_interactions": [
      {
        "drug_id": "DR0881",
        "drug_name": "Irinotecan hydrochloride",
        "interacted_species": "Bacteroides thetaiotaomicron (CFB bacteria)",
        "location": "Gut",
        "result": "Human Cytochrome P450 3A4 (CYP3A4) metabolizes the drug Irinotecan hydrochloride, and Bacteroides thetaiotaomicron further metabolizes its metabolite (SN-38G), which can indirectly affect efficacy, safety or bioavailability of this drug."
      }
    ],
    "host_protein_interactions": [
      {
        "partner_id": "EHMT1_HUMAN",
        "partner_type": "protein",
        "partner_name": "Histone methyltransferases (HMTs)",
        "disease": "Liver cancer [ICD-11: 2C12]",
        "mof_classification": "Histone modification",
        "mof_detail": "Histone hypermethylation",
        "cell_line": "HepG2 cell line",
        "summary": "HMTs-CYP3A4 interaction",
        "description": "The Histone 3 lysine 4 dimethylation of CYP3A4 gene is reported to activate the transcriptional activity of the drug-metabolizing enzyme Cytochrome P450 3A4. As a result, the interaction between Histone methyltransferases (HMTs) and CYP3A4 can enhance the drug-metabolizing process of Cytochrome P450 3A4."
      }
    ]
  }
}
```
Source cross-reference: `http://intede.idrblab.net/search/dme-xeotic-search?search_api_fulltext=CYP3A4` (DME detail page for CYP3A4).

**Edge-case document** (`DME1257` — a microbial DME with only a single xenobiotic interaction; no UniProt/Gene/EC identifiers found; demonstrates `unlist()` collapsing a single-item list to a scalar object):
```json
{
  "_id": "DME1257",
  "intede": {
    "dme_id": "DME1257",
    "name": "Unclear metabolic mechanism (DME-unclear)",
    "species": "Bifidobacterium longum",
    "xenobiotic_interactions": {
      "xeotic_id": "XEO03113",
      "name": "Royalisin defensin-1",
      "type": "Amino Acid(s), Peptide(s) or Protein(s)",
      "classification": "Peptide",
      "description": "Royalisin defensin-1 inhibits the drug-metabolizing activity of Unclear enzyme (DME-unclear) from Bifidobacterium longum",
      "gene_form": "Protein",
      "modulation_type": "Inhibition"
    }
  }
}
```
Source cross-reference: `http://intede.idrblab.net/search/dme-xeotic-search` (search by species "Bifidobacterium longum").

## Field Coverage

(computed over all 921 documents)

- `name`: 100.0%
- `species`: 100.0%
- `uniprot`: 96.5%
- `gene_id`: 96.5%
- `ec_number`: 96.5%
- `xenobiotic_interactions`: 54.3%
- `host_protein_interactions`: 43.1%
- `methylation_interactions`: 32.6%
- `microbiome_interactions`: 20.2%

## Test Results Summary

`biothings-cli` is broken in this sandbox — every subcommand (`validate`, `dump`, `upload`, `list`, `inspect`, `inspect --mode mapping`) raises `AttributeError: module 'typer' has no attribute 'rich_utils'` at import time (`typer 0.26.7` incompatible with `biothings 1.0.2`; reproduced fresh via `biothings-cli --version`). This is the same environment-wide blocker already logged for ~15 other plugins in `built-plugins-index.md` (ecbd, coconut, chemprob, molbic, ageannomo, cancerproteome, drmref, etc.). Per the generator skill's instructions, the shared environment was **not** patched; validation was performed directly instead:

1. **Parser execution**: Downloaded all 5 manifest files with `curl -A "Mozilla/5.0"` into a scratch `data_folder`, then imported `parser.py` and called `load_data(data_folder)` directly (no CLI). Result: **921 unique documents, 921 unique `_id`s, 0 duplicates, 0 exceptions.**
2. **`_id` format check**: All 921 `_id` values match `DME\d+` (INTEDE's own DME identifier), string type, ≤512 chars. PASS.
3. **Field-type consistency**: Every leaf field path in the 921 yielded documents was recursively walked and its observed Python type recorded; all string-typed leaves were consistently strings, all numeric leaves (`methylation_interactions.*.delta_beta` / `.pvalue`) were consistently `float`. **0 heterogeneous/conflicting fields found.**
4. **`dict_sweep`/`unlist` cleanliness**: No `None`, empty string, or empty-list values observed in any yielded document; single-item interaction lists correctly collapse to bare objects (see `DME1257` sample above) rather than single-element arrays.
5. **Mapping validation** (in place of `inspect --mode mapping`): A standalone script recursively walked all 921 documents, recorded the observed type at every field path, and diffed it against `mapping.py`'s flattened `properties`. Result: **0 missing fields, 0 type mismatches, 0 unused mapping entries** (the tool's own bookkeeping counted the root `intede` object path itself as "missing" from a properties-only flattening — a harness artifact, not a real gap; every leaf and nested-object field is covered).

| Check | Result |
|---|---|
| Parser runs end-to-end | PASS (921 docs, 0 exceptions) |
| Unique `_id` | PASS (921/921 unique) |
| `_id` format | PASS (`DME\d+`) |
| Field-type consistency | PASS (0 conflicts) |
| `dict_sweep`/`unlist` cleanliness | PASS |
| Mapping vs. real documents | PASS (0 missing, 0 mismatches) |
| `biothings-cli` 6-step workflow | BLOCKED (sandbox-wide typer/biothings incompatibility, not plugin-specific) |

## Mapping Overview

`mapping.py`'s `get_customized_mapping()` returns a single top-level `intede` object with:

- **Scalar identity fields** (`dme_id`, `name`, `species`, `uniprot`, `gene_id`, `ec_number`) → `keyword`
- **`xenobiotic_interactions`** (nested object, list-collapsible): `xeotic_id`/`name`/`type`/`classification`/`gene_form`/`modulation_type` → `keyword`; `description` → `text` with a `.raw` `keyword` subfield (long free-text narrative, e.g. IC50/Ki experimental detail — full-text search is useful here, but exact-match/aggregation is preserved via `.raw`)
- **`microbiome_interactions`** (nested object): `drug_id`/`drug_name`/`interacted_species`/`location` → `keyword`; `result` → `text` + `.raw` (long narrative sentence)
- **`host_protein_interactions`** (nested object): `partner_id`/`partner_type`/`partner_name`/`disease`/`mof_classification`/`mof_detail`/`substrate`/`cell_line`/`summary` → `keyword`; `description` → `text` + `.raw`
- **`methylation_interactions`** (nested object): `icd_code`/`disease_name` → `keyword`; three sub-objects `case_vs_health`/`case_vs_adjacent`/`case_vs_other`, each with `status` (`keyword`), `delta_beta` (`float`), `pvalue` (`float`)

All four interaction fields are mapped via `properties` (object), not an array type — Elasticsearch has no array type, and `unlist()` in the parser collapses single-item lists to bare objects (confirmed in the `DME1257` sample), so the object mapping is correct for both the list and collapsed-scalar cases.

### Mapping Conflicts
None. Every field path resolved to exactly one consistent type across all 921 documents (see Test Results Summary, step 3) — no heterogeneous or incompatible fields were found, so no fields required special-case handling or exclusion.
