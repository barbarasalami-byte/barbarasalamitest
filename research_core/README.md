# research_core

Source-agnostic literature review with verifiable citations. Register the
sources you have; the agent builds its tools, its prompt, and its citation
checks from whatever is registered.

    prompts/review_protocol.md   the method - names no specific database
    sources/base.py              the SourceProvider contract
    sources/registry.py          registration and availability
    sources/rest.py              shared JSON-over-HTTP base
    sources/VERIFICATION.md      what is and is not proven per source
    sources/pubmed.py            PubMed / NCBI E-utilities
    sources/crossref.py          Crossref (DOIs, all disciplines)
    sources/clinicaltrials.py    ClinicalTrials.gov (NCT, publication bias)
    sources/openfda.py           FDA drug data incl. CDER (approvals, labels, FAERS)
    sources/sec_edgar.py         SEC EDGAR filings full-text search
    sources/patentsview.py       USPTO granted patents (needs an API key)
    sources/socrata.py           Socrata portals; CDC dataset discovery
    sources/cms.py               CMS dataset discovery
    agent.py                     dynamic tool + prompt assembly
    verify.py                    cross-source citation audit

## Use

```python
from research_core import Researcher, audit_citations

result = Researcher().review("Your question", review_type="scoping")
print(result.report)

audit = audit_citations(result)
if not audit.ok:
    raise ValueError(audit.summary())   # don't ship the report
```

## Adding a source

Implement five methods and register. Nothing else changes — the agent gains
`search_<name>` and `fetch_<name>` tools, your `syntax_guide` is injected into
the prompt, and your `id_patterns` are enforced by the citation audit.

```python
class InternalCorpus:
    name = "internal"
    id_label = "DOCID"
    id_patterns = [re.compile(r"\bDOCID[:\s]\s*([A-Z]{2}-\d+)\b")]
    syntax_guide = "### Internal corpus\n\nPlain keyword search..."

    def available(self): return True, ""
    def search(self, query, max_results): ...   # -> SearchOutcome
    def fetch(self, ids): ...                   # -> list[Record]
    def exists(self, record_id): ...            # -> bool

register(InternalCorpus())
```

Working example in `examples/custom_source.py`. Wrap anything — an MCP client,
a vector store, a REST API, a local corpus.

## How it adapts

- **Prompt.** `build_system_prompt()` injects only the syntax guidance for
  sources that are available. The model is never told how to query a corpus it
  cannot reach. With no sources it is instructed to stop rather than answer
  from memory.
- **Tools.** One `search`/`fetch` pair per available source, generated at
  construction.
- **Availability.** A source missing its API key stays registered but drops out
  of `available_sources()`, so a misconfigured environment degrades to the
  sources that work instead of failing the run.
- **Failures.** A source that raises mid-run returns an error string to the
  model rather than killing the review.

## The citation audit

`audit_citations()` scans the report with every provider's `id_patterns` and
checks each identifier against what that run actually retrieved. Three outcomes
that mean different things:

- `nonexistent` — cited, never retrieved, and absent from the source. Fabricated.
- `unretrieved` minus the above — real, but cited from memory rather than
  retrieved. A different bug, equally disqualifying.
- `unchecked` — unretrieved and the source was unreachable, so it is *not*
  cleared. Absence of a check is never treated as a pass.

## Sources and what they are for

| Source | Identifier | Answers |
| --- | --- | --- |
| `pubmed` | PMID | Published biomedical literature |
| `crossref` | DOI | Any discipline, DOI resolution |
| `clinicaltrials` | NCT | Trials incl. completed-but-unpublished |
| `openfda` | NDA/ANDA/BLA | Approvals, labelling, adverse events (CDER data) |
| `sec_edgar` | Accession | What a company told investors |
| `uspto` | Patent no. | Prior art, exclusivity |
| `cdc` | Dataset id | Surveillance datasets |
| `cms` | Dataset id | Utilisation and spend datasets |

`sec_edgar` and `uspto` need credentials (`SEC_CONTACT_EMAIL`,
`PATENTSVIEW_API_KEY`) and report themselves unavailable without them, so a
review runs on the rest rather than failing.

**No provider has made a live request from the build environment** - every
upstream host is blocked at network policy. See `sources/VERIFICATION.md`.

## Notes

- Model is `claude-opus-5` with adaptive thinking; override via
  `Researcher(model=...)`.
- The system prompt is ~1.2K tokens. The minimum cacheable prefix is
  model-dependent (512–4096), so `cache_control` may not engage at this size.
  Watch `result.usage["cache_read_input_tokens"]`; grow the stable prefix or
  accept it.
- Output is an evidence synthesis, not clinical, legal, or investment advice.
