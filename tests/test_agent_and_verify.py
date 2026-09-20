"""Offline tests: dynamic prompt/tool assembly and the citation audit."""

import unittest

from research_core.agent import ReviewResult, _make_tools, build_system_prompt
from research_core.sources import Record
from research_core.verify import audit_citations, extract_citations

from test_sources import FakeSource


class DynamicAssemblyTests(unittest.TestCase):
    def test_prompt_names_only_registered_sources(self):
        prompt = build_system_prompt({"fakedb": FakeSource()})
        self.assertIn("`fakedb` (identifier: FAKEID)", prompt)
        self.assertIn("Query with plain keywords", prompt)
        self.assertNotIn("PubMed", prompt)

    def test_prompt_with_no_sources_forbids_answering(self):
        prompt = build_system_prompt({})
        self.assertIn("do not answer from memory", prompt.lower())

    def test_tools_are_named_per_source(self):
        run = ReviewResult(report="")
        tools = _make_tools(FakeSource(), run)
        names = [t.to_dict()["name"] for t in tools]
        self.assertEqual(names, ["search_fakedb", "fetch_fakedb"])
        # The id label reaches the model via the parameter description,
        # since @beta_tool uses only the docstring summary as the tool description.
        fetch_schema = tools[1].to_dict()["input_schema"]
        self.assertIn("FAKEID", fetch_schema["properties"]["ids"]["description"])
        self.assertEqual(fetch_schema["additionalProperties"], False)

    def test_search_tool_records_the_log_and_results(self):
        run = ReviewResult(report="")
        search = _make_tools(FakeSource(), run)[0]
        search.call({"query": "obesity", "max_results": 5})

        self.assertEqual(len(run.search_log), 1)
        self.assertEqual(run.search_log[0].query, "obesity")
        self.assertEqual(run.search_log[0].source, "fakedb")
        self.assertEqual(run.sources_used, ["fakedb"])
        self.assertIn("fakedb:A001", run.records)

    def test_unreachable_source_degrades_instead_of_raising(self):
        class Broken(FakeSource):
            def search(self, query, max_results=25):
                raise ConnectionError("network down")

        run = ReviewResult(report="")
        search = _make_tools(Broken(), run)[0]
        result = search.call({"query": "x"})

        self.assertIn("unreachable", result)
        self.assertEqual(run.search_log, [])


class CitationAuditTests(unittest.TestCase):
    REGISTRY = {"fakedb": FakeSource()}

    def _run(self, report, retrieved):
        return ReviewResult(
            report=report,
            records={
                f"fakedb:{i}": Record(source="fakedb", id=i, title="t")
                for i in retrieved
            },
        )

    def test_extracts_ids_across_sources(self):
        found = extract_citations("PMID: 37356941 and 10.1056/NEJMoa2307563 here.")
        self.assertEqual(
            sorted(map(str, found)),
            ["crossref:10.1056/NEJMoa2307563", "pubmed:37356941"],
        )

    def test_doi_pattern_stops_at_sentence_punctuation(self):
        found = extract_citations("See 10.1056/NEJMoa2307563.")
        self.assertEqual({c.id for c in found}, {"10.1056/NEJMoa2307563"})

    def test_clean_report_passes(self):
        audit = audit_citations(
            self._run("Shown in FAKEID: A001.", {"A001"}), self.REGISTRY
        )
        self.assertTrue(audit.ok)

    def test_retrieving_more_than_you_cite_is_not_an_error(self):
        audit = audit_citations(
            self._run("Only FAKEID: A001.", {"A001", "A002"}), self.REGISTRY
        )
        self.assertTrue(audit.ok)

    def test_fabricated_id_is_flagged_as_nonexistent(self):
        audit = audit_citations(
            self._run("Claim (FAKEID: Z999).", {"A001"}), self.REGISTRY
        )
        self.assertFalse(audit.ok)
        self.assertEqual({c.id for c in audit.nonexistent}, {"Z999"})
        self.assertIn("fabricated", audit.summary())

    def test_real_but_unretrieved_id_is_distinguished_from_fabrication(self):
        # A001 exists at the source but was never returned this run: cited from
        # memory, which is a different bug from an invented identifier.
        audit = audit_citations(self._run("Claim (FAKEID: A001).", set()), self.REGISTRY)
        self.assertFalse(audit.ok)
        self.assertEqual(audit.nonexistent, set())
        self.assertIn("cited from memory", audit.summary())

    def test_unreachable_source_is_unchecked_not_cleared(self):
        class Broken(FakeSource):
            def exists(self, record_id):
                raise ConnectionError("network down")

        audit = audit_citations(
            self._run("Claim (FAKEID: A001).", set()), {"fakedb": Broken()}
        )
        self.assertFalse(audit.ok)
        self.assertEqual({c.id for c in audit.unchecked}, {"A001"})
        self.assertIn("unreachable", audit.summary())


if __name__ == "__main__":
    unittest.main()
