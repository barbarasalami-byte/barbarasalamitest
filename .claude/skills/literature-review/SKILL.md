---
name: literature-review
description: "Systematic literature search and evidence synthesis with verifiable citations, for biomedical, scientific, technical, legal, and market research. Use when the task is to find, screen, synthesize, and cite a body of literature or primary sources - a scoping or systematic review, a state-of-the-art summary, an evidence check on a claim, a competitive or prior-art landscape. Triggers include: 'literature review', 'what does the evidence say', 'systematic review', 'find papers on', 'research the evidence for', 'cite sources on', 'prior art', 'what's been published about'. Works with whatever retrieval tools are available in the session - web search, MCP servers, database clients, internal search - and adapts its search strategy to them. Do NOT use for a single factual lookup, or for clinical, legal, or investment advice about a specific case."
license: MIT. Methodology adapted from github.com/affaan-m/ECC - see references/NOTICE.md
---

# Literature review

Produce evidence syntheses whose every claim traces to a source that can be
checked. The method below is source-agnostic: it governs how you search,
screen, and cite, not which tool you search with.

## Step 0 — Inventory your retrieval tools first

**Before searching, establish what you can actually reach.** Look at the tools
available in this session and sort them:

| Kind | Examples | Use for |
|---|---|---|
| Bibliographic databases | PubMed/NCBI, arXiv, Crossref, Semantic Scholar, OpenAlex | Primary literature, citation metadata, DOIs |
| Registries and filings | ClinicalTrials.gov, USPTO/EPO, SEC EDGAR, regulatory dockets | Unpublished or non-journal primary evidence |
| General web | `WebSearch`, `WebFetch`, Firecrawl/Exa/Tavily MCPs | Grey literature, news, orientation, current events |
| Internal | Project RAG, vector store, document MCP, a local corpus | Proprietary evidence the public web cannot see |
| Execution | `Bash`, code execution | Calling an HTTP API directly when no wrapper tool exists |

Then state your plan in one or two lines: which tools you will use for which
concepts, and what you cannot reach. **If no retrieval tool is available, say
so and stop** — do not answer a literature-review question from memory. Recalled
citations are the single most common way these reports go wrong.

If only general web search is available, say that the review is limited to what
web search surfaces, and do not claim systematic coverage.

## Step 1 — Define the question

Decompose into concepts before searching.

- **Biomedical/clinical:** PICO — Population, Intervention or exposure,
  Comparator, Outcome.
- **Technical:** system or domain, method, comparison baseline, evaluation metric.
- **Legal/patent:** subject matter, claim elements, jurisdiction, date window.
- **Market/competitive:** market, segment, geography, time window.

## Step 2 — Choose the review type and say which

- **Narrative** — broad orientation. No completeness claim.
- **Scoping** — maps concepts and gaps. The default for exploratory work.
- **Systematic** — reproducible protocol, fixed criteria. Required before any
  clinical or publication claim.
- **Meta-analysis** — systematic plus quantitative aggregation.

Never claim systematic rigor without a reproducible, reported protocol.

## Step 3 — Plan the search before running it

Fix and state: date range, languages, publication or document types,
inclusion criteria, exclusion criteria. Write these down before the first
query, so results cannot quietly redefine them.

## Step 4 — Search, and log every pass verbatim

Translate each concept into the query syntax of the tool you are using. For
database-specific syntax (PubMed field tags and MeSH, arXiv categories,
Crossref filters, patent classification), read `references/source-syntax.md`.

Log every search as you go — not reconstructed afterward:

| Source | Date searched | Query (verbatim) | Filters | Results |
| --- | --- | --- | --- | ---: |

Rules that hold for every tool:

- Report the query exactly as issued, so a reader can re-run it.
- An empty result is a finding. Report it, then revise — never silently
  broaden a query and present the result as the original search.
- Search at least two independent sources before any broad claim. One source
  supports a claim only if you scope the claim to that source explicitly.

## Step 5 — Deduplicate

In order: DOI → source-native ID (PMID, arXiv ID, patent number, accession) →
exact title → normalized title + first author + year. Report how many
duplicates were removed.

## Step 6 — Screen in stages

Title → abstract/summary → full text. For systematic work, record an exclusion
reason for each dropped item: wrong population, wrong intervention, wrong
outcome, not primary research, duplicate, unavailable, outside date range.

## Step 7 — Extract into a table

| Study | Design | Population/Data | Method | Comparator | Outcome | Key finding | Limitations |
| --- | --- | --- | --- | --- | --- | --- | --- |

Adapt the columns to the domain — for technical work use dataset, benchmark,
metric, baseline, reproducibility.

## Step 8 — Synthesize by theme, not paper by paper

Lenses: strongest evidence · conflicting evidence · methodological weaknesses ·
population or dataset limits · recency and replication · unanswered questions.

Label every claim by confidence:

- **High** — replicated, high-quality evidence across independent sources.
- **Medium** — plausible but limited by sample, method, or recency.
- **Low** — early, speculative, single-source, or weakly measured.

## Step 9 — Verify citations before delivering

This is not optional, and it is where these reports fail.

- Every identifier you cite must have come back from a tool call **in this
  session**. If you cannot point to the call that returned it, remove it.
- Re-check each DOI, PMID, arXiv ID, or URL resolves to the record you claim.
- Never cite a source for a claim it does not make.
- Label preprints as preprints; distinguish reviews from primary evidence;
  label retracted work as retracted.

If you cannot verify an identifier, say so inline rather than dropping the
caveat: `(citation unverified — retrieved via web summary, not the record)`.

Where the project sets its own wording for absent or unverified evidence, use
that wording instead of inventing your own. If no convention is set, write
**Evidence pending** when a search has not yet been run or has not returned,
and **No public precedent available** when a search ran and returned nothing.
Never fill the gap with a plausible-looking citation.

## Output template

```markdown
# Literature Review: <Topic>

Generated: <date> · Review type: <type> · Search window: <dates>
Sources searched: <list> · Not reachable: <list>

## Research Question
## Search Strategy
## Inclusion and Exclusion Criteria
## Evidence Summary
## Thematic Synthesis
## Gaps and Limitations
## References
## Search Log
```

## Pitfalls

- Do not treat a search snippet as evidence — retrieve the record.
- Do not mix preprints, reviews, and primary studies without labels.
- Do not omit negative or conflicting findings; they are the point.
- Do not let a tool's ranking stand in for screening criteria.
- Do not answer from memory when retrieval fails. Report the failure.

## Scope boundary

This produces an evidence synthesis, not advice. State findings and their
quality; do not issue clinical recommendations for a patient, legal advice on
a matter, or investment guidance on a position. Point to the professional
judgment the decision needs.
