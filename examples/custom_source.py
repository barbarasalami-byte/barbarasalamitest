"""Add your own source: implement five methods, register, done.

Nothing else changes - the agent picks up the tools, the prompt guidance, and
the citation checks automatically.
"""

import re

from research_core import Record, SearchOutcome, register, build_system_prompt, available_sources


class InternalCorpus:
    name = "internal"
    id_label = "DOCID"
    id_patterns = [re.compile(r"\bDOCID[:\s]\s*([A-Z]{2}-\d+)\b")]
    syntax_guide = (
        "### Internal corpus\n\n"
        "Plain keyword search over internal research memos. No field tags. "
        "Not public - never present these as published literature."
    )

    def available(self):
        return True, ""

    def search(self, query: str, max_results: int = 25) -> SearchOutcome:
        hits = my_vector_store_search(query, k=max_results)  # your code here
        return SearchOutcome(
            source=self.name,
            query=query,
            total_matches=len(hits),
            records=[self._to_record(h) for h in hits],
        )

    def fetch(self, ids: list[str]) -> list[Record]:
        return [self._to_record(my_doc_lookup(i)) for i in ids]

    def exists(self, record_id: str) -> bool:
        return my_doc_lookup(record_id) is not None

    def _to_record(self, hit) -> Record:
        return Record(
            source=self.name,
            id=hit["id"],
            title=hit["title"],
            year=hit.get("year", ""),
            venue="Internal",
            abstract=hit.get("text", ""),
        )


def my_vector_store_search(query, k):  # placeholder
    return [{"id": "IN-1", "title": "An internal memo", "text": "..."}]


def my_doc_lookup(doc_id):  # placeholder
    return {"id": doc_id, "title": "An internal memo", "text": "..."}


if __name__ == "__main__":
    register(InternalCorpus())
    print("Sources now available:", ", ".join(available_sources()))
    prompt = build_system_prompt(available_sources())
    print("\nThe prompt now carries:")
    for line in prompt.splitlines():
        if "internal" in line.lower():
            print("  " + line)
