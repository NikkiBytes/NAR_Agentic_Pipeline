# AgeAnnoMO — KG Edge Model

Produced by `claude/kg-edge-modeler/SKILL.md` on 2026-09-22 against
`NAR.API/plugins/ageannomo`. Every rate below was measured against live
NodeNorm / NameRes in this run. Machine-readable form: `edge_model.json`.

**KG verdict: NEEDS_CURATION.** Ingest verdict is unchanged at
`RECOMMEND_INGEST` — this plugin is a valid annotation source. Two of its four
entity types are not usable as KG edges as shipped.

| | docs | verdict |
|---|---|---|
| protein_expression | 16,091 | KG_READY |
| metabolite | 2,959 | KG_READY |
| gene_expression | 40,402 | BLOCKED_PENDING_CURATION |
| lifespan_regulator | 1,881 | BLOCKED_PENDING_CURATION |
| **KG-usable** | **19,050 (31%)** | |

The shipped parser was re-run against freshly downloaded source files and
reproduces `README.md` exactly: 61,333 documents, 0 duplicate `_id`s.
Nothing below is a defect in the parser — it is a question about what the
documents can be used *for*.

---

## protein_expression — KG_READY

UniProtKB accessions via NodeNorm, n=200, taxon-checked against each row's own
`Animal` value across all 9 species present:

**any_hit 95% · correct_hit 94%** (1 resolved with no taxon attached)

| species (as written) | sampled | correct |
|---|---|---|
| Human | 48 | 92% |
| Rhesus monkeys | 45 | 89% |
| C. elegans | 34 | 97% |
| Nothobranchius furzeri | 29 | 100% |
| Rabit *(sic)* | 24 | 100% |
| Drosophila melanogaster | 9 | 100% |
| Callithrix jacchus | 8 | 88% |
| Rat | 2 | 100% |
| Mouse | 1 | 100% |

One modeling note: accessions do **not** normalize to a consistent category —
125 of 190 resolve to `biolink:Gene`, 65 to `biolink:Protein`. Read the subject
category off the normalized node; do not assume `Protein` from the column name.

**Edge:** normalized UniProtKB node — `biolink:associated_with` → age-group
comparison, qualified by species / tissue / direction, with PubMed and PRIDE
`ProjectID` as provenance.

**Filter:** `adj.P.Val < 0.05` keeps **7,170 of 16,109** (45%); adding
`abs(logFC) > 1` keeps 3,662. Note that `P.Value < 0.05` passes 16,108 of 16,109
— the file is already pre-filtered on nominal p, so the raw p-value column is
not a usable filter. Same pattern as `plsda_vip` in the metabolite file: use the
adjusted column.

## metabolite — KG_READY

PubChem CIDs via NodeNorm, n=200: **any_hit 100% · correct_hit 100%**, all 200
to `biolink:SmallMolecule`. 0 null CIDs. The cleanest column in the source.

**Filter:** the file's own curator flag `is_AgeRelatedMetabolite == True` keeps
**77 of 2,960 (2.6%)**. Note that `plsda_vip > 1` passes 2,956 of 2,960 (99.9%)
— it looks like a threshold column and discriminates nothing. Use the flag.

**Unmodelable context:** `Age group` is free text using an ideographic comma as
the list separator — `"Old: 59、92 weeks old; Young: 3、16 weeks old"`. Turning
that into a structured age qualifier needs locale-aware parsing. This is the
concrete form the "resources are in Chinese" concern takes inside the data.

## gene_expression — BLOCKED_PENDING_CURATION

Gene symbols via NameRes, 30 distinct symbols per species × 10 species:

| species (as written) | rows | any_hit | correct (naive) | correct (`only_taxa`) |
|---|---|---|---|---|
| Nothobranchius furzeri | 12,645 | 97% | 0% | 97% ⚠ |
| Danio_rerio | 12,507 | 73% | 23% | 87% |
| Mouse | 4,318 | 100% | 0% | 97% ⚠ |
| Drosophila melanogaster | 3,410 | 100% | 63% | — |
| Caenorhabditis. elegans | 1,766 | 87% | 87% | — |
| Human | 1,577 | 100% | 20% | 100% |
| Naked mole rat | 1,490 | 100% | 3% | 93% |
| Sus scrofa | 1,320 | 100% | 67% | — |
| Canis lupus | 823 | **0%** | 0% | — |
| Rat | 596 | 100% | 3% | — |

**Weighted: any_hit 86% · correct_hit 27%.** This is why the skill requires both
rates. Naive top-1 resolution puts most rows on the wrong species' ortholog, and
the headline number hides it completely.

**⚠ The `only_taxa` column is not a fix.** All **4,318 Mouse rows — 100% of
them — have a purely numeric `symbol`** (every other species is 0% numeric).
Taxon-constrained NameRes returns a best fuzzy match inside the taxon for any
input whatsoever:

```
'3155' -> NCBIGene:102633820  Gm31552
'331'  -> NCBIGene:100504689  Plscr5
'Sdcbp'-> NCBIGene:53378      Sdcbp    (a real symbol; resolves correctly)
```

so the 97% is manufactured. Two alternative readings of the numeric column were
tested and both fail: as mouse Entrez IDs, 0/60 resolve to mouse; several
resolve to *human* genes (`516`→ATP5MC1, `965`→CD58, `4058`→LTK) and many do not
resolve at all. **The provenance of this column is unidentified and needs to be
asked of the source authors.** The shipped plugin reports `gene.symbol` at 100%
field coverage — true, and biologically empty for every mouse row — and bakes
the values into `_id` as `amoexpr:...:3155:...`.

Also blocking: Canis lupus resolves at 0/30, and the species column itself needs
normalization before any taxon constraint can be applied (mixed common and Latin
names, `Danio_rerio` with an underscore, `Caenorhabditis. elegans` with a stray
period).

**Filter:** `FDR < 0.05` keeps **12,933 of 40,452 (32%)**; adding
`abs(logFC) > 1` keeps 10,666. 788 rows carry `FDR == 1`; 1,577 have null
`logFC`. The plugin ingests all rows unfiltered.

## lifespan_regulator — BLOCKED_PENDING_CURATION

n=30 symbols: **any_hit 100% · correct_hit 0%** against an assumed mouse taxon.

The file has four columns — `Gene`, `R_value`, `p_value`, `Category`. There is
**no species column anywhere in it.** The mouse assumption comes from
`README.md` prose, not from the data, so per the skill's step 3.4 the
column is unresolvable as shipped rather than resolvable-with-effort.

**No predicate proposed.** `Pos-MLS` / `neg-MLS` (1,121 / 760) is the sign of a
correlation with maximum lifespan, not a causal claim. Mapping it to a
lifespan-extension predicate would assert something the source does not.

**Filter:** pre-filtered; all 1,881 rows pass `p_value < 0.05`.

---

## Files never examined

The relevancy report scored AgeAnnoMO across 10 aging hallmarks. The inspection
enumerated 9 files from 4 hallmark directories. The plugin ingests 4. Never
listed, never inspected, never reached the generator's file-selection policy:

- **Anti-aging interventions** (intervention → effect → target → hallmark)
- Dysbiosis / microbiota
- Aging-related immune repertoire (TCR/BCR)
- Epigenetic alterations
- Intercellular communication

The intervention file is the most edge-shaped content in the source and the
likeliest KG value. It was excluded before any shape-based reasoning ran — by
omission, not by decision.

## Curation required

1. Normalize the species columns in both expression files.
2. Establish what the numeric Mouse `symbol` column in
   `Differential expression.xlsx` actually contains — ask the authors.
3. Establish the species for `Lifespan regulators.xlsx`.
4. Inspect `Anti-aging interventions`; it is a sibling-plugin candidate.

Items 2–4 are questions for the source, not engineering work. Item 1 is cheap.
