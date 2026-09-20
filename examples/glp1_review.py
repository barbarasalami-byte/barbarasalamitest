"""End-to-end example: a scoping review with a citation audit.

    export ANTHROPIC_API_KEY=...      # or: ant auth login
    export NCBI_EMAIL=you@example.com # NCBI asks for this; NCBI_API_KEY raises limits
    python examples/glp1_review.py
"""

import logging

from research_core import LiteratureReviewer, audit_citations

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

QUESTION = (
    "What is the cardiovascular outcomes evidence for GLP-1 receptor agonists "
    "in non-diabetic patients with obesity?"
)


def main() -> None:
    reviewer = LiteratureReviewer()
    result = reviewer.review(QUESTION, review_type="scoping")

    print(result.report)

    print("\n" + "=" * 72)
    print("SEARCH LOG (what was actually run)")
    for entry in result.search_log:
        print(
            f"  [{entry.searched_at}] {entry.count} matches, "
            f"{entry.returned} retrieved\n    {entry.query}"
        )

    print("\nCITATION AUDIT")
    print("  " + audit_citations(result).summary().replace("\n", "\n  "))

    usage = result.usage
    print(
        f"\nTOKENS  in={usage.get('input_tokens', 0):,} "
        f"out={usage.get('output_tokens', 0):,} "
        f"cache_read={usage.get('cache_read_input_tokens', 0):,}"
    )


if __name__ == "__main__":
    main()
