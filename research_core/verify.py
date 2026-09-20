"""Citation verification.

The failure mode that matters in a research product is a fluent report citing
PMIDs that do not exist or were never retrieved. This module catches both.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .agent import ReviewResult
from .pubmed import PubMed

PMID_PATTERN = re.compile(r"\bPMID:?\s*(\d{4,8})\b", re.IGNORECASE)


@dataclass
class CitationAudit:
    cited: set[str]
    retrieved: set[str]
    unretrieved: set[str]
    nonexistent: set[str]

    @property
    def ok(self) -> bool:
        return not self.unretrieved and not self.nonexistent

    def summary(self) -> str:
        if self.ok:
            return f"All {len(self.cited)} cited PMIDs were retrieved in-run and resolve."
        lines = [f"{len(self.cited)} PMIDs cited."]
        if self.unretrieved:
            lines.append(
                f"NOT RETRIEVED IN THIS RUN (possible fabrication): "
                f"{', '.join(sorted(self.unretrieved))}"
            )
        if self.nonexistent:
            lines.append(
                f"DO NOT RESOLVE AT PUBMED: {', '.join(sorted(self.nonexistent))}"
            )
        return "\n".join(lines)


def audit_citations(result: ReviewResult, pubmed: PubMed | None = None) -> CitationAudit:
    """Check every PMID in the report against what was actually retrieved.

    A PMID in `unretrieved` did not come from a tool call in this run - treat it
    as fabricated until proven otherwise. `nonexistent` PMIDs fail at PubMed too.
    """
    cited = set(PMID_PATTERN.findall(result.report))
    retrieved = result.cited_pmids
    unretrieved = cited - retrieved

    nonexistent: set[str] = set()
    if unretrieved:
        checker = pubmed or PubMed()
        nonexistent = {pmid for pmid in unretrieved if not checker.exists(pmid)}

    return CitationAudit(
        cited=cited,
        retrieved=retrieved,
        unretrieved=unretrieved,
        nonexistent=nonexistent,
    )
