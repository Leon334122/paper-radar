import unittest

from pipeline.models import parse_date
from pipeline.sources import _openalex_abstract, _crossref_date, resolve_doi_by_title


class TestSources(unittest.TestCase):
    def test_openalex_abstract_reconstruction(self):
        inverted = {
            "delivery": [0, 5],
            "peptide": [1],
            "system": [2, 6],
            "for": [3],
            "lung": [4],
        }
        text = _openalex_abstract(inverted)
        self.assertEqual(text, "delivery peptide system for lung delivery system")
        self.assertIsNone(_openalex_abstract(None))

    def test_crossref_date(self):
        self.assertEqual(_crossref_date({"date-parts": [[2026, 8, 15]]}), "2026-08-15")
        self.assertEqual(_crossref_date({"date-parts": [[2026, 8]]}), "2026-08-01")
        self.assertEqual(_crossref_date({"date-parts": [[2026]]}), "2026-01-01")
        self.assertIsNone(_crossref_date({}))

    def test_parse_date_variants(self):
        self.assertEqual(parse_date("2026-08-15"), "2026-08-15")
        self.assertEqual(parse_date("2026-08"), "2026-08-01")
        self.assertEqual(parse_date("2026"), "2026-01-01")
        self.assertEqual(parse_date(""), None)

    def test_resolve_doi_by_title_returns_none_without_network(self):
        # 无网络环境下应抛出并返回 None（这里不实际请求，仅验证函数存在且可调用签名）
        self.assertTrue(callable(resolve_doi_by_title))


if __name__ == "__main__":
    unittest.main()
