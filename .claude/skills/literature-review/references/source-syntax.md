# Source query syntax

Read the section for the source you are actually searching. Skip the rest.

## PubMed / NCBI E-utilities

Field tags: `[ti]` title · `[ab]` abstract · `[tiab]` title or abstract ·
`[au]` author · `[ta]` journal abbreviation · `[mh]` MeSH · `[majr]` major MeSH
topic · `[pt]` publication type · `[dp]` date · `[la]` language

Subheadings precede the field tag:

    diabetes mellitus, type 2/drug therapy[mh]
    cardiovascular diseases/prevention & control[mh]

Publication types: `randomized controlled trial[pt]`, `meta-analysis[pt]`,
`systematic review[pt]`, `guideline[pt]`, `clinical trial[pt]`
Dates: `2026[dp]`, `2020:2026[dp]` · Availability: `free full text[sb]`

    diabetes mellitus[mh] AND treatment[tiab] AND systematic review[pt] AND 2023:2026[dp]

Prefer MeSH where a controlled term exists; pair with `[tiab]` synonyms for new
terminology that MeSH has not caught up to. `[majr]` raises precision but
silently drops relevant work.

E-utilities endpoints: `esearch.fcgi` (query → IDs), `esummary.fcgi` (light
metadata), `efetch.fcgi` (abstracts/full records), `elink.fcgi` (related).
Rate limit 3/sec anonymous, 10/sec with an API key. For large sets use
`usehistory=y` with `WebEnv` and `query_key` rather than long ID lists in URLs.

## arXiv

Prefixes: `ti:` `abs:` `au:` `cat:` `all:` — combine with `AND`/`OR`/`ANDNOT`.

    cat:cs.CL AND abs:"retrieval augmented generation" AND submittedDate:[20240101 TO 20261231]

Everything on arXiv is a preprint unless a DOI shows journal publication.
Label it as such.

## Crossref

REST filters on `https://api.crossref.org/works`:
`query.bibliographic`, `filter=from-pub-date:2020-01-01`, `filter=type:journal-article`,
`rows`, `select` to trim the payload. Crossref is the authority for DOI
resolution and is the cheapest way to confirm a DOI exists.

## Semantic Scholar / OpenAlex

Good for citation graphs — forward citations, references, influential-citation
counts. Use to find what cited a landmark paper, which keyword search misses.
Both have generous free tiers; OpenAlex needs no key.

## ClinicalTrials.gov

Query `NCT` IDs, condition, intervention, phase, status, results-posted.
Essential for publication bias: trials registered and completed but never
published are evidence a journal-only search cannot see.

## Patents (USPTO / EPO / Google Patents)

Search claims and classification (CPC/IPC), not just abstracts. Priority date
matters more than publication date for prior art. Family members are
duplicates — deduplicate by simple family, not document number.

## General web search

Treat as orientation and grey literature, not as a bibliographic database.
Follow every claim to the primary record before citing it. A search snippet is
not evidence.
