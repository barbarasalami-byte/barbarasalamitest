"""Run a review over whatever sources are registered.

    export ANTHROPIC_API_KEY=...        # or: ant auth login
    export NCBI_EMAIL=you@example.com   # NCBI_API_KEY raises the rate limit
    export CROSSREF_EMAIL=you@example.com
    python examples/run_review.py "your research question"
"""

import logging
import sys

from research_core import Researcher, audit_citations, available_sources

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

DEFAULT_QUESTION = (
    "What is the cardiovascular outcomes evidence for GLP-1 receptor agonists "
    "in non-diabetic patients with obesity?"
)


def main() -> int:
    question = " ".join(sys.argv[1:]) or DEFAULT_QUESTION

    print(f"Sources available: {', '.join(available_sources()) or 'NONE'}\n")
    result = Researcher().review(question, review_type="scoping")

    print(result.report)

    print("\n" + "=" * 72)
    print("SEARCH LOG (what was actually run)")
    for entry in result.search_log:
        print(
            f"  [{entry.searched_at}] {entry.source}: {entry.total_matches} matches, "
            f"{entry.returned} retrieved\n    {entry.query}"
        )

    print("\nCITATION AUDIT")
    audit = audit_citations(result)
    print("  " + audit.summary().replace("\n", "\n  "))

    usage = result.usage
    print(
        f"\nTOKENS  in={usage.get('input_tokens', 0):,} "
        f"out={usage.get('output_tokens', 0):,} "
        f"cache_read={usage.get('cache_read_input_tokens', 0):,}"
    )
    return 0 if audit.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
