# NAR / OUP Article URL Resolution

When a user provides an OUP article URL (e.g., `https://academic.oup.com/nar/article/53/D1/D1016/7905315`), direct fetching with `fetch_web_pages` will usually fail (JS-rendered page, bot blocking). Use this resolution procedure instead.

## Step 0: Check for a local PDF (fastest path — try this first)

Before making any HTTP calls, check if a PDF is already available locally:
```bash
ls agent_outputs/<datasource>_datasource/*.pdf 2>/dev/null
```
If a PDF exists, read it directly with `read_files` and skip Steps 1–4 entirely. The Data Availability and Methods sections of the PDF contain everything needed for the evaluation.

## Step 1: Extract metadata from the URL

OUP NAR article URLs follow this pattern:
```
https://academic.oup.com/nar/article/{volume}/{issue}/{start_page}/{oup_article_id}
```

Example: `https://academic.oup.com/nar/article/53/D1/D1016/7905315?searchresult=1`
- Volume: 53
- Issue: D1
- Start page: D1016
- OUP article ID: 7905315 (this is NOT a PMID or PMCID)

## Step 2: Find the PMID via PubMed E-utilities

Use the volume and start page to search PubMed:
```bash
curl -sL "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=nucleic+acids+research[journal]+AND+{volume}[volume]+AND+{start_page}[page]&retmode=json"
```

Example:
```bash
curl -sL "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=nucleic+acids+research[journal]+AND+53[volume]+AND+D1016[page]&retmode=json"
```

Parse the JSON response: `esearchresult.idlist[0]` is the PMID.

## Step 3: Fetch article metadata from PubMed

Use the PMID to get full citation metadata including the PMCID:
```bash
curl -sL "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={PMID}&retmode=json"
```

From the response, extract:
- `title` — paper title
- `authors` — author list
- `fulljournalname` — journal name
- `elocationid` — DOI (format: `doi: 10.1093/nar/...`)
- `articleids` — look for `idtype: "pmc"` to get the PMCID

**Alternative DOI extraction**: If the E-utilities response lacks a DOI, construct it from the OUP URL. NAR DOIs follow `10.1093/nar/gk...` — search the PubMed record or use:
```bash
curl -sL "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={PMID}&rettype=xml" | grep -oP '10\.1093/nar/\w+'
```

## Step 4: Fetch full text from PMC

All NAR Database Issue articles are open access. **Preferred: fetch the PMC PDF directly** — it is the same content as the published paper and avoids XML parsing:
```
https://pmc.ncbi.nlm.nih.gov/articles/{PMCID}/pdf/
```
Use `read_files` on this URL. The PDF contains the Data Availability section, Methods, entity counts, and identifiers needed for evaluation.

**Alternative: PMC HTML page** (if PDF fetch fails):
```
https://pmc.ncbi.nlm.nih.gov/articles/{PMCID}/
```
Use `fetch_web_pages` — PMC pages are reliably fetchable unlike OUP pages.

**Alternative: PMC XML** (if structured data extraction is needed):
```bash
curl -sL "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id={PMCID}&rettype=xml" > /tmp/nar_article.xml
```

## Step 5: Fallback — web search

If Steps 2–4 fail (e.g., very new paper not yet in PMC), fall back to:
```
exa_web_search("NAR {start_page} {volume} D1 database {year}")
```

Or try the DOI directly if known:
```
fetch_web_pages(["https://doi.org/10.1093/nar/gk..."])
```

## Quick Reference: Volume → Year Mapping (NAR Database Issues)

- Volume 53, Issue D1 → January 2025
- Volume 54, Issue D1 → January 2026
- Volume 52, Issue D1 → January 2024

## Common Pitfalls

- **OUP article ID ≠ PMCID**: The number in the OUP URL path (e.g., `7905315`) is OUP's internal ID, not a PMCID. Do not pass it to PMC APIs.
- **Query params**: Strip `?searchresult=1` and similar query params before parsing the URL.
- **Multiple results**: If the PubMed search returns multiple PMIDs, use the one whose title matches the expected database topic.
- **Rate limiting**: NCBI E-utilities have a 3 requests/second limit without an API key. Add `&api_key=` if available, or add brief pauses between calls.
