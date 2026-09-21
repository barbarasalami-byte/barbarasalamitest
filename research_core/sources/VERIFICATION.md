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
| `openfda` | **unverified** | `api.fda.gov/drug/drugsfda.json`. Orange Book TE codes read from `products[].te_code`. |
| `fda_label` | **unverified** | `drug/label.json`. Current label only, no history. |
| `fda_faers` | **unverified** | `drug/event.json`. For production volume, prefer the quarterly bulk archives over the API. |
| `fda_ndc` | **unverified** | `drug/ndc.json`. |
| `fda_enforcement` | **unverified** | `drug/enforcement.json`. Covers recalls only — inspection classifications and warning letters come from the FDA Data Dashboard, which is **not built**. |
| `sec_edgar` | **unverified, lowest confidence** | `efts.sec.gov/LATEST/search-index` is not formally documented. Kept alongside `sec_submissions` at the team's request. |
| `sec_submissions` | **unverified** | `data.sec.gov/submissions/CIK{cik}.json`, the documented API. Prefer this where the question is about one company. |
| `sec_insider` | **unverified** | Same endpoint, filtered to Forms 3/4/5. Does **not** yet parse the ownership XML, so transaction codes, share counts and prices are not extracted — only that a form was filed. |
| `uspto` | **unverified** | PatentsView v1. Requires an API key. |
| `uspto_assignments` | **unverified** | `developer.uspto.gov/ds-api/`. The response field names (`assignorName`, `patNum`, …) are the least certain part; the mapper accepts both scalar and list forms defensively. |
| `cdc` | **unverified** | Socrata discovery API. Returns *datasets*, not rows. |
| `cms` | **unverified** | CMS DCAT catalogue, filtered client-side. Returns *datasets*, not rows. |
| `cms_spending` | **unavailable** | Needs a dataset id, which changes per dashboard year. Discover it with `cms` first, then set `DATASET`. |
| `cms_open_payments` | **unavailable** | Same: needs the program-year dataset id. |

### Not built from the matrix

| Row | Source | Why not a live provider |
| --- | --- | --- |
| 4 | FDA CBER / Purple Book | Published as bulk CSV, not an API. Belongs in a scheduled ingestion job, not the live tool surface. |
| 8 | EMA EPAR & PMS | FHIR gateway needs EMA developer registration; the open route is weekly bulk XML/XLSX. Ingestion job. |
| 25 | NCI SEER | Requires a signed data use agreement. Cannot be an anonymous provider at all. |

These three are **class B**: bulk sources that should land in Delta tables on a
schedule, then be exposed to the research layer as an internal source over
those tables. That keeps the licence and registration boundaries where they
belong — in the ingestion job, not in an agent's tool call.

Row 24 (RxNorm/RxNav) is **class C**: a normaliser, not a source. It lives in
`research_core/normalize.py` and is deliberately not registered — an RxCUI is a
join key, not citable evidence.

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
