# research_core

A literature-review layer: ECC's research methodology vendored as editable
Markdown, driving Claude with real PubMed tool calls and a citation audit.

## Why it is shaped this way

ECC skills are Markdown prompt files, not a library. There is nothing to import
and no runtime to adopt. So the methodology lives in `prompts/` as plain
Markdown you can edit without touching code, and everything that has to be real
— the searches, the PMIDs, the verification — is ordinary Python.

    prompts/pubmed_query.md        query construction, field tags, filters
    prompts/literature_review.md   review protocol, screening, synthesis, template
    prompts/NOTICE.md              MIT attribution (retain if you redistribute)
    pubmed.py                      NCBI E-utilities client, rate-limited
    agent.py                       tool runner + prompt assembly
    verify.py                      citation audit

## Use

```python
from research_core import LiteratureReviewer, audit_citations

reviewer = LiteratureReviewer()
result = reviewer.review(
    "Cardiovascular outcomes of GLP-1 receptor agonists in non-diabetic obesity",
    review_type="scoping",
)

print(result.report)
print(audit_citations(result).summary())
```

Environment: `ANTHROPIC_API_KEY` (or `ant auth login`), `NCBI_EMAIL`, and
`NCBI_API_KEY` to raise NCBI's rate limit from 3/sec to 10/sec.

## The part that matters for a research product

`audit_citations` compares every PMID in the report against the set actually
returned by tool calls during that run. A PMID in `unretrieved` never came back
from PubMed — treat it as fabricated. This is the check that separates a
research product from a chat wrapper, and it is cheap: it runs offline against
data you already have.

Gate on it:

```python
audit = audit_citations(result)
if not audit.ok:
    raise ValueError(audit.summary())   # don't ship the report
```

## Tuning

Edit the Markdown in `prompts/`. `build_system_prompt()` concatenates them in a
fixed order; keep that output byte-stable across requests so the cached prefix
holds. Per-request content (the question, the date) goes in the user message.

## Notes

- Model is `claude-opus-5` with adaptive thinking. Override via
  `LiteratureReviewer(model=...)`.
- The system prompt is ~1.2K tokens. Minimum cacheable prefix is model-dependent
  (512–4096 tokens), so `cache_control` may silently not engage at this size.
  Check `result.usage["cache_read_input_tokens"]` across runs — if it stays 0,
  either accept it or grow the stable prefix.
- PubMed only. For a broad claim add a second database (arXiv, Crossref,
  clinical-trial registries) — the review protocol says not to rest a broad
  claim on one source, and nothing in the code enforces that.
- Output is a literature synthesis, not clinical or regulatory advice.
