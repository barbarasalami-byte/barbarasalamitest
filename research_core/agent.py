"""Source-agnostic literature reviewer.

The agent reads the source registry at construction time and builds its tools,
its prompt guidance, and its citation rules from whatever is registered. Adding
a source changes nothing here.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import anthropic
from anthropic import beta_tool

from .sources import Record, SourceProvider, available_sources, unavailable_sources

log = logging.getLogger(__name__)

MODEL = "claude-opus-5"
PROMPTS = Path(__file__).parent / "prompts"


@dataclass
class SearchLogEntry:
    source: str
    query: str
    total_matches: int
    returned: int
    searched_at: str


@dataclass
class ReviewResult:
    report: str
    search_log: list[SearchLogEntry] = field(default_factory=list)
    records: dict[str, Record] = field(default_factory=dict)
    """Everything retrieved this run, keyed by 'source:id'."""
    sources_used: list[str] = field(default_factory=list)
    sources_unavailable: dict[str, str] = field(default_factory=dict)
    usage: dict[str, int] = field(default_factory=dict)

    def retrieved_ids(self, source: str) -> set[str]:
        return {r.id for r in self.records.values() if r.source == source}


def build_system_prompt(providers: dict[str, SourceProvider]) -> str:
    """Assemble the prompt from the protocol plus the registered sources.

    Only the syntax guidance for sources that are actually available gets
    injected - the model is never told how to query a corpus it cannot reach.
    Keep this byte-stable across requests so the cached prefix holds.
    """
    protocol = (PROMPTS / "review_protocol.md").read_text(encoding="utf-8")

    if providers:
        roster = "\n".join(
            f"- `{name}` (identifier: {p.id_label}) - tools: "
            f"`search_{name}`, `fetch_{name}`"
            for name, p in sorted(providers.items())
        )
        guides = "\n\n".join(
            p.syntax_guide for _, p in sorted(providers.items()) if p.syntax_guide
        )
        sources_section = (
            f"## Sources available in this session\n\n{roster}\n\n"
            "Search at least two independent sources before any broad claim. "
            "If only one is available, scope the claim to that source "
            "explicitly.\n\n"
            f"## Source query syntax\n\n{guides}"
        )
    else:
        sources_section = (
            "## Sources available in this session\n\n"
            "**None.** No retrieval tool is available. Say so and stop - do not "
            "answer from memory."
        )

    return "\n\n---\n\n".join(
        [
            "You are a research assistant. You search the sources provided as "
            "tools and synthesize what you retrieve. You never state a finding "
            "you did not retrieve, and never cite an identifier that did not "
            "come back from a tool call.",
            protocol,
            sources_section,
        ]
    )


def _make_tools(provider: SourceProvider, run: ReviewResult) -> list:
    """Build the search/fetch pair for one source, bound to this run."""
    name, label = provider.name, provider.id_label

    def search(query: str, max_results: int = 25) -> str:
        try:
            outcome = provider.search(query, max_results)
        except ValueError as exc:
            return f"Query rejected: {exc}"
        except Exception as exc:  # a dead source must not kill the run
            log.warning("Source %r search failed: %s", name, exc)
            return f"Source {name} is unreachable ({exc}). Report this and try another."

        run.search_log.append(
            SearchLogEntry(
                source=name,
                query=outcome.query,
                total_matches=outcome.total_matches,
                returned=len(outcome.records),
                searched_at=outcome.searched_at,
            )
        )
        for record in outcome.records:
            run.records[record.citation_key()] = record
        if name not in run.sources_used:
            run.sources_used.append(name)

        if not outcome.records:
            return f"0 results for {query!r}. Report the empty search, then revise."
        return json.dumps(
            {
                "total_matches": outcome.total_matches,
                "returned": len(outcome.records),
                "results": [
                    {
                        label.lower(): r.id,
                        "title": r.title,
                        "venue": r.venue,
                        "year": r.year,
                        "types": r.doc_types,
                        "preprint": r.is_preprint,
                    }
                    for r in outcome.records
                ],
            },
            indent=2,
        )

    search.__name__ = f"search_{name}"
    search.__doc__ = f"""Search {name} and return matching records.

    Args:
        query: A {name} query string. Follow the {name} syntax in the system prompt.
        max_results: Maximum records to return (1-100).
    """

    def fetch(ids: list[str]) -> str:
        try:
            records = provider.fetch(ids[:20])
        except Exception as exc:
            log.warning("Source %r fetch failed: %s", name, exc)
            return f"Source {name} is unreachable ({exc})."
        for record in records:
            run.records[record.citation_key()] = record
        if not records:
            return f"No {name} records found for those {label}s."
        return "\n\n".join(
            f"{label} {r.id} | {r.summary_line()}\n{r.title}\n"
            f"Authors: {', '.join(r.authors[:8]) or 'n/a'}\n\n"
            f"{r.abstract or '(no abstract available)'}"
            for r in records
        )

    fetch.__name__ = f"fetch_{name}"
    fetch.__doc__ = f"""Fetch full records from {name} for specific identifiers.

    Args:
        ids: {label} values from a prior search_{name} call, at most 20.
    """

    return [beta_tool(search), beta_tool(fetch)]


class Researcher:
    """Runs a review over every available source."""

    def __init__(
        self,
        client: anthropic.Anthropic | None = None,
        providers: dict[str, SourceProvider] | None = None,
        model: str = MODEL,
    ) -> None:
        self.client = client or anthropic.Anthropic()
        self.providers = available_sources() if providers is None else providers
        self.model = model
        self.system_prompt = build_system_prompt(self.providers)

    def review(
        self,
        question: str,
        review_type: str = "scoping",
        max_tokens: int = 16000,
    ) -> ReviewResult:
        run = ReviewResult(report="", sources_unavailable=unavailable_sources())

        if not self.providers:
            raise RuntimeError(
                "No research sources available. Register at least one provider; "
                f"unavailable: {run.sources_unavailable or 'none registered'}"
            )

        tools = [t for p in self.providers.values() for t in _make_tools(p, run)]

        request = (
            f"Research question: {question}\n\n"
            f"Review type: {review_type}\n"
            f"Today's date: {date.today().isoformat()}\n\n"
            "Search the available sources, screen what you find, and produce the "
            "review using the output template. Report every search string "
            "verbatim in the Search Log."
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
            tools=tools,
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
                    run.usage[key] = run.usage.get(key, 0) + (getattr(usage, key, 0) or 0)

        if final is None:
            raise RuntimeError("Tool runner produced no messages")
        if final.stop_reason == "max_tokens":
            log.warning("Report hit max_tokens and is truncated; raise max_tokens.")
        if final.stop_reason == "refusal":
            raise RuntimeError(f"Request declined: {final.stop_details}")

        run.report = "\n".join(b.text for b in final.content if b.type == "text")
        return run
