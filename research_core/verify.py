"""Citation verification across every registered source.

The failure mode that matters in a research product is a fluent report citing
identifiers that were never retrieved. This catches that for any source, using
the ID patterns each provider declares.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .agent import ReviewResult
from .sources import SourceProvider, all_sources


@dataclass(frozen=True)
class Citation:
    source: str
    id: str

    def __str__(self) -> str:
        return f"{self.source}:{self.id}"


@dataclass
class CitationAudit:
    cited: set[Citation] = field(default_factory=set)
    unretrieved: set[Citation] = field(default_factory=set)
    """Cited but never returned by a tool call this run - treat as fabricated."""
    nonexistent: set[Citation] = field(default_factory=set)
    """Unretrieved AND absent from the source itself."""
    unchecked: set[Citation] = field(default_factory=set)
    """Unretrieved, and the source was unreachable for a live check."""

    @property
    def ok(self) -> bool:
        return not self.unretrieved

    def summary(self) -> str:
        if not self.cited:
            return "No citations found in the report."
        if self.ok:
            return f"All {len(self.cited)} cited identifiers were retrieved in-run."

        lines = [f"{len(self.cited)} identifiers cited, {len(self.unretrieved)} unverified."]
        if self.nonexistent:
            lines.append(
                "DO NOT RESOLVE AT SOURCE (fabricated): "
                + ", ".join(sorted(map(str, self.nonexistent)))
            )
        confirmed_real = self.unretrieved - self.nonexistent - self.unchecked
        if confirmed_real:
            lines.append(
                "REAL BUT NOT RETRIEVED THIS RUN (cited from memory): "
                + ", ".join(sorted(map(str, confirmed_real)))
            )
        if self.unchecked:
            lines.append(
                "COULD NOT CHECK (source unreachable): "
                + ", ".join(sorted(map(str, self.unchecked)))
            )
        return "\n".join(lines)


def _namespace_peers(
    registry: dict[str, SourceProvider], source: str
) -> list[str]:
    """Sources sharing an identifier namespace with `source`.

    Several providers can read the same corpus through different endpoints -
    the three SEC providers all cite accession numbers - so an identifier
    retrieved by one is legitimately cited from any of them. `id_label` is the
    namespace key.
    """
    label = registry[source].id_label.lower() if source in registry else ""
    if not label:
        return [source]
    return [n for n, p in registry.items() if p.id_label.lower() == label]


def extract_citations(
    text: str, providers: dict[str, SourceProvider] | None = None
) -> set[Citation]:
    """Find every source identifier in the text, using each provider's patterns.

    One identifier yields one citation even when several providers recognise
    it: sources sharing an `id_label` share a namespace, and the citation is
    attributed to the first of them by name so the result is deterministic.
    """
    registry = providers if providers is not None else all_sources()
    by_namespace: dict[tuple[str, str], str] = {}

    for name, provider in registry.items():
        label = provider.id_label.lower()
        for pattern in provider.id_patterns:
            for match in pattern.finditer(text):
                key = (label, match.group(1))
                current = by_namespace.get(key)
                if current is None or name < current:
                    by_namespace[key] = name

    return {
        Citation(source=source, id=identifier)
        for (_, identifier), source in by_namespace.items()
    }


def audit_citations(
    result: ReviewResult, providers: dict[str, SourceProvider] | None = None
) -> CitationAudit:
    """Check every identifier in the report against what was actually retrieved.

    A citation in `unretrieved` did not come from a tool call in this run. Those
    are then checked against the live source to separate a real-but-recalled
    reference from an invented one; both are failures, but they mean different
    things about the model's behavior.
    """
    registry = providers if providers is not None else all_sources()
    audit = CitationAudit(cited=extract_citations(result.report, registry))

    for citation in audit.cited:
        # A namespace peer's retrieval counts: the same accession fetched by
        # sec_submissions satisfies a citation attributed to sec_edgar.
        peers = _namespace_peers(registry, citation.source)
        if any(citation.id in result.retrieved_ids(peer) for peer in peers):
            continue
        audit.unretrieved.add(citation)

        provider = registry.get(citation.source)
        if provider is None:
            audit.unchecked.add(citation)
            continue
        try:
            if not provider.exists(citation.id):
                audit.nonexistent.add(citation)
        except Exception:
            audit.unchecked.add(citation)

    return audit
