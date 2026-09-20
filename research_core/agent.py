"""Literature-review agent: vendored ECC methodology + real PubMed tool calls.

The prompts under `prompts/` are adapted from ECC (MIT) - see prompts/NOTICE.md.
They are plain Markdown on purpose: edit them to tune behavior, no code change
needed.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import anthropic
from anthropic import beta_tool

from .pubmed import Article, PubMed

log = logging.getLogger(__name__)

MODEL = "claude-opus-5"
PROMPTS = Path(__file__).parent / "prompts"


def _load(name: str) -> str:
    return (PROMPTS / name).read_text(encoding="utf-8")


def build_system_prompt() -> str:
    """Assemble the stable system prompt.

    Everything here must be byte-stable across requests - it is the cached
    prefix. Anything varying per request (the question, today's date) belongs
    in the user message instead.
    """
    return "\n\n---\n\n".join(
        [
            "You are a biomedical literature research assistant. You search "
            "PubMed through the tools provided and synthesize what you find. "
            "You never state a finding you did not retrieve.",
            _load("pubmed_query.md"),
            _load("literature_review.md"),
        ]
    )


@dataclass
class SearchLogEntry:
    query: str
    count: int
    returned: int
    searched_at: str


@dataclass
class ReviewResult:
    report: str
    search_log: list[SearchLogEntry]
    articles: dict[str, Article]
    usage: dict[str, int] = field(default_factory=dict)

    @property
    def cited_pmids(self) -> set[str]:
        """PMIDs that were actually retrieved during this run."""
        return set(self.articles)


class LiteratureReviewer:
    def __init__(
        self,
        client: anthropic.Anthropic | None = None,
        pubmed: PubMed | None = None,
        model: str = MODEL,
    ) -> None:
        self.client = client or anthropic.Anthropic()
        self.pubmed = pubmed or PubMed()
        self.model = model
        self.system_prompt = build_system_prompt()

    def _tools(self, run: ReviewResult) -> list:
        """Build tools bound to this run, so retrievals are recorded."""
        pubmed = self.pubmed

        @beta_tool
        def search_pubmed(query: str, max_results: int = 25) -> str:
            """Search PubMed and return matching PMIDs with titles.

            Args:
                query: A PubMed query string using standard field tags, e.g.
                    'semaglutide[tiab] AND randomized controlled trial[pt]'.
                max_results: Maximum PMIDs to return (1-100).
            """
            try:
                result = pubmed.esearch(query, retmax=max(1, min(max_results, 100)))
            except ValueError as exc:
                return f"Query rejected: {exc}"

            run.search_log.append(
                SearchLogEntry(
                    query=result.query,
                    count=result.count,
                    returned=len(result.pmids),
                    searched_at=result.searched_at,
                )
            )
            if not result.pmids:
                return f"0 results for {query!r}. Revise and report the empty search."

            articles = pubmed.efetch(result.pmids)
            for article in articles:
                run.articles[article.pmid] = article
            return json.dumps(
                {
                    "total_matches": result.count,
                    "returned": len(articles),
                    "results": [
                        {
                            "pmid": a.pmid,
                            "title": a.title,
                            "journal": a.journal,
                            "year": a.year,
                            "publication_types": a.publication_types,
                        }
                        for a in articles
                    ],
                },
                indent=2,
            )

        @beta_tool
        def fetch_abstracts(pmids: list[str]) -> str:
            """Fetch full abstracts for specific PMIDs found via search_pubmed.

            Args:
                pmids: PMIDs to retrieve, at most 20 per call.
            """
            articles = pubmed.efetch(pmids[:20])
            for article in articles:
                run.articles[article.pmid] = article
            if not articles:
                return "No records found for those PMIDs."
            return "\n\n".join(
                f"PMID {a.pmid} | {a.journal} {a.year} | {'; '.join(a.publication_types)}\n"
                f"{a.title}\n"
                f"Authors: {', '.join(a.authors[:8]) or 'n/a'}\n\n"
                f"{a.abstract or '(no abstract)'}"
                for a in articles
            )

        return [search_pubmed, fetch_abstracts]

    def review(
        self,
        question: str,
        review_type: str = "scoping",
        max_tokens: int = 16000,
    ) -> ReviewResult:
        """Run a literature review and return the report plus its evidence trail."""
        run = ReviewResult(report="", search_log=[], articles={})

        request = (
            f"Research question: {question}\n\n"
            f"Review type: {review_type}\n"
            f"Today's date: {date.today().isoformat()}\n\n"
            "Search PubMed, screen what you find, and produce the review using "
            "the output template. Report every search string verbatim in the "
            "Search Log."
        )

        runner = self.client.beta.messages.tool_runner(
            model=self.model,
            max_tokens=max_tokens,
            thinking={"type": "adaptive"},
            system=[
                {
                    "type": "text",
                    "text": self.system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=self._tools(run),
            messages=[{"role": "user", "content": request}],
        )

        final = None
        for message in runner:
            final = message
            usage = getattr(message, "usage", None)
            if usage is not None:
                for key in (
                    "input_tokens",
                    "output_tokens",
                    "cache_read_input_tokens",
                    "cache_creation_input_tokens",
                ):
                    run.usage[key] = run.usage.get(key, 0) + (
                        getattr(usage, key, 0) or 0
                    )

        if final is None:
            raise RuntimeError("Tool runner produced no messages")
        if final.stop_reason == "max_tokens":
            log.warning("Report hit max_tokens and is truncated; raise max_tokens.")
        if final.stop_reason == "refusal":
            raise RuntimeError(f"Request declined: {final.stop_details}")

        run.report = "\n".join(
            block.text for block in final.content if block.type == "text"
        )
        return run
