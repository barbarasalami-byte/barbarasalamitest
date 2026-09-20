# PubMed query construction

Split the research question into concepts, then combine them with Boolean
operators. Prefer MeSH terms where a stable controlled-vocabulary term exists;
pair MeSH with title/abstract synonyms when the topic is new or terminology
varies.

## Field tags

`[ti]` title · `[ab]` abstract · `[tiab]` title or abstract · `[au]` author
`[ta]` journal abbreviation · `[mh]` MeSH term · `[majr]` major MeSH topic
`[pt]` publication type · `[dp]` date of publication · `[la]` language

Subheadings go before the field tag:

    diabetes mellitus, type 2/drug therapy[mh]
    cardiovascular diseases/prevention & control[mh]

Use `[majr]` only when the topic must be central to the paper. It raises
precision but silently drops relevant work.

## Publication-type filters

`randomized controlled trial[pt]` · `clinical trial[pt]` · `meta-analysis[pt]`
`systematic review[pt]` · `review[pt]` · `guideline[pt]`

Date: `2026[dp]`, `2020:2026[dp]`, `2026/03/15[dp]`
Availability: `free full text[sb]`, `hasabstract[text]`

## Worked examples

    diabetes mellitus[mh] AND treatment[tiab] AND systematic review[pt] AND 2023:2026[dp]
    (metformin[nm] OR insulin[nm]) AND diabetes mellitus, type 2[mh] AND randomized controlled trial[pt]

## Rules

- Every search you run must be reported verbatim, so the user can paste it into
  PubMed and get the same result set.
- Never invent a PMID. Every PMID you cite must have come back from a tool call
  in this conversation.
- If a search returns nothing, report the empty result and revise the query.
  Do not silently broaden it and present the result as the original search.
