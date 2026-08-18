import unittest

from pipeline.models import dedupe_papers, merge_paper, paper_key, retain_papers
from pipeline.storage import dedupe_by_title


class TestStorage(unittest.TestCase):
    def test_dedupe_by_doi(self):
        a = {"doi": "10.1000/abc", "title": "A", "journal": "J", "first_seen": "2026-08-01T00:00:00+00:00"}
        b = {"doi": "10.1000/ABC", "title": "B", "journal": "J", "first_seen": "2026-08-02T00:00:00+00:00"}
        out = dedupe_papers([a, b])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["title"], "A")

    def test_merge_keeps_first_seen_and_summary(self):
        old = {
            "doi": "10.1000/x",
            "title": "T",
            "first_seen": "2026-08-01T00:00:00+00:00",
            "summary": {"one_liner": "旧总结"},
        }
        new = {"doi": "10.1000/x", "title": "T", "first_seen": "2026-08-03T00:00:00+00:00", "abstract": "新摘要"}
        merged = merge_paper(old, new)
        self.assertEqual(merged["first_seen"], "2026-08-01T00:00:00+00:00")
        self.assertEqual(merged["summary"]["one_liner"], "旧总结")
        self.assertEqual(merged["abstract"], "新摘要")

    def test_merge_replaces_future_issue_date_with_corrected_date(self):
        old = {"doi": "10.1000/y", "title": "T", "publication_date": "2026-10-01", "date_precision": "month"}
        new = {"doi": "10.1000/y", "title": "T", "publication_date": "2026-08-14", "date_precision": "approx"}
        merged = merge_paper(old, new)
        self.assertEqual(merged["publication_date"], "2026-08-14")
        self.assertEqual(merged["date_precision"], "approx")

    def test_retain_90_days(self):
        papers = [
            {"publication_date": "2026-08-10", "first_seen": "2026-08-10T00:00:00+00:00"},
            {"publication_date": "2026-01-01", "first_seen": "2026-01-01T00:00:00+00:00"},
        ]
        kept = retain_papers(papers, days=90)
        self.assertEqual(len(kept), 1)

    def test_paper_key_fallback(self):
        p = {"title": "Hello, World!", "journal": "Nature"}
        self.assertEqual(paper_key(p), "t:hello world|nature")
        p2 = {"url": "https://example.com/x"}
        self.assertEqual(paper_key(p2), "url:https://example.com/x")

    def test_dedupe_by_title_merges_url_and_doi_records(self):
        a = {"doi": "10.1000/xyz", "title": "Peptide nanofibers for lung delivery", "journal": "ACS Nano", "abstract": "A"}
        b = {"doi": None, "url": "https://pubs.acs.org/xyz", "title": "Peptide nanofibers for lung delivery", "journal": "ACS Nano", "abstract": "B"}
        out = dedupe_by_title([a, b])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["doi"], "10.1000/xyz")
        self.assertEqual(out[0]["url"], "https://pubs.acs.org/xyz")


if __name__ == "__main__":
    unittest.main()
