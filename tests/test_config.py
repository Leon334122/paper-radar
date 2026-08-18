import unittest
from pathlib import Path

from pipeline.config import load_config

ROOT = Path(__file__).resolve().parent.parent


class TestConfig(unittest.TestCase):
    def setUp(self):
        self.cfg = load_config(ROOT / "config", ROOT / "data", ROOT / "site")

    def test_journal_count_and_tiers(self):
        self.assertEqual(len(self.cfg.journals), 27)
        self.assertEqual(len(self.cfg.enabled_journals), 27)
        tiers = [j.tier for j in self.cfg.journals]
        self.assertTrue(all(t in {"S", "A", "B", "C"} for t in tiers))
        self.assertEqual(sum(t == "S" for t in tiers), 3)

    def test_journal_fields(self):
        for j in self.cfg.journals:
            self.assertTrue(j.name)
            self.assertRegex(j.issn, r"^\d{4}-\d{3}[\dXx]$")

    def test_directions_count(self):
        self.assertEqual(len(self.cfg.directions), 8)
        labels = [d.label for d in self.cfg.directions]
        for expected in ["药物递送系统", "自组装多肽", "纳米药物", "肿瘤治疗", "细胞搭便车", "肺部靶向", "细胞疗法", "基因治疗"]:
            self.assertIn(expected, labels)
        for d in self.cfg.directions:
            self.assertTrue(d.keywords)

    def test_min_score(self):
        self.assertGreaterEqual(self.cfg.min_score, 1)

    def test_exclude_title_terms(self):
        self.assertIn("correction", self.cfg.excluded_title_terms)


if __name__ == "__main__":
    unittest.main()
