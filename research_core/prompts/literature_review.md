# Literature review protocol

## Review types

- **Narrative** — broad synthesis, useful for orientation.
- **Scoping** — maps concepts, methods, and evidence gaps. Default for
  exploratory work.
- **Systematic** — reproducible protocol. Default when the output supports a
  publication or a clinical claim.
- **Meta-analysis** — systematic review plus quantitative effect aggregation.

State which type you are performing at the top of the output. Do not claim
systematic rigor without a reproducible protocol.

## Workflow

### 1. Define the question

For clinical/biomedical work use PICO: Population, Intervention or exposure,
Comparator, Outcome.

### 2. Plan the search before collecting sources

Fix the date range, languages, publication types, and the inclusion and
exclusion criteria up front, and state them.

### 3. Search and log

Every search pass is logged verbatim:

| Database | Date searched | Query | Filters | Results |
| --- | --- | --- | --- | ---: |

### 4. Deduplicate

In order: DOI → PMID → exact title → normalized title + first author + year.
Record how many duplicates were removed.

### 5. Screen in stages

Title → abstract → full text. Record exclusion reasons: wrong population,
wrong intervention, wrong outcome, not primary research, duplicate,
unavailable full text, outside date range.

### 6. Extract into a structured table

| Study | Design | Population | Intervention | Comparator | Outcome | Key finding | Limitations |
| --- | --- | --- | --- | --- | --- | --- | --- |

### 7. Synthesize by theme, not paper by paper

Lenses: strongest evidence · conflicting evidence · methodological weaknesses ·
population limits · recency and replication · unanswered questions.

Separate every claim by confidence:

- **High** — replicated, high-quality evidence across sources.
- **Medium** — plausible but limited by sample, method, or recency.
- **Low** — early, speculative, single-source, or weakly measured.

### 8. Verify citations

Verify each PMID or DOI. Do not cite a paper for a claim it does not make.
Mark preprints as preprints. Distinguish reviews from primary evidence.

## Output template

    # Literature Review: <Topic>

    Generated: <date>
    Review type: <narrative | scoping | systematic | meta-analysis>
    Search window: <dates>
    Databases: <list>

    ## Research Question
    ## Search Strategy
    ## Inclusion and Exclusion Criteria
    ## Evidence Summary
    ## Thematic Synthesis
    ## Gaps and Limitations
    ## References
    ## Search Log

## Pitfalls

- Do not treat search snippets as evidence.
- Do not mix preprints, reviews, and primary studies without labeling them.
- Do not omit negative or conflicting findings.
- Do not use a single database for a broad claim unless the scope is explicitly
  limited to that database.

## Scope boundary

This produces a literature synthesis, not clinical, regulatory, or treatment
advice. State findings and their evidence quality; do not issue
recommendations for the care of an individual patient.
