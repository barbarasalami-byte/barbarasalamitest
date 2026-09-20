# Verification status

The build environment blocks every upstream host at network policy (403 at
CONNECT), so **no provider below has made a live request**. Response *mapping*
is tested against fixtures; the *endpoint contract* — URL, parameter names,
response field paths — is written from documentation and is unproven.

Run `PYTHONPATH=. python examples/run_review.py "..."` against a real network
before trusting any of these. Expect corrections; they are one-line changes in
`_search_params` / `_records_from` / `_to_record`.

| Source | Endpoint contract | Notes |
| --- | --- | --- |
| `pubmed` | **unverified** | E-utilities is stable and long-documented; highest confidence of the set. |
| `crossref` | **unverified** | Stable public REST API. |
| `clinicaltrials` | **unverified** | API v2 (`/api/v2/studies`). v1 was retired; if a request 404s, confirm the v2 path first. |
| `openfda` | **unverified** | `api.fda.gov/drug/{drugsfda,label,event}.json`. Lucene `search` syntax. |
| `sec_edgar` | **unverified, lowest confidence** | The full-text endpoint (`efts.sec.gov/LATEST/search-index`) is not formally documented; parameter names (`q`, `from`, `size`) and the `hits.hits._source` shape are the most likely things to be wrong here. |
| `uspto` | **unverified** | PatentsView v1 (`search.patentsview.org/api/v1/patent/`). Requires an API key. |
| `cdc` | **unverified** | Socrata discovery API. Returns *datasets*, not rows. |
| `cms` | **unverified** | CMS DCAT catalogue (`data.cms.gov/data.json`), filtered client-side because the catalogue has no server-side search. Returns *datasets*, not rows. |

## Scope boundaries worth knowing

- **CDER is not a separate API.** It is a centre within FDA; its drug
  approvals, labels, and adverse-event data are served through the openFDA
  drug endpoints. `openfda` is the CDER provider.
- **CMS coverage determinations (NCD/LCD) are not covered.** Those live in the
  Medicare Coverage Database, a different system. A CMS search here does not
  reach coverage policy.
- **CDC and CMS return dataset descriptions, not data.** Discovery first, then
  `rows(dataset_id, ...)` on the chosen dataset.
- **FAERS counts are not incidence rates.** Spontaneous reports; a count is
  not a denominator and not causation.
- **CMS spend is gross, not net of rebate.** Never present it as net price.
