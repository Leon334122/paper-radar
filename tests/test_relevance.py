import unittest

from pipeline.config import load_config
from pipeline.relevance import is_relevant, score_paper

CFG = load_config("config", "data", "site")


class TestRelevance(unittest.TestCase):
    def _score(self, title, abstract=""):
        return score_paper(CFG, title, abstract)

    def test_title_hit_includes(self):
        score, labels = self._score("Platelet-hitchhiking peptide nanofibers for pulmonary drug delivery")
        self.assertTrue(is_relevant(CFG, score))
        self.assertTrue(any("细胞搭便车" in l for l in labels))
        self.assertTrue(any("肺部靶向" in l for l in labels))

    def test_abstract_two_hits_in_same_direction(self):
        abstract = (
            "The engineered T cells were expanded ex vivo and reinfused. "
            "CAR-T cells showed durable antitumor activity in vivo."
        )
        score, labels = self._score("Adoptive immunotherapy for solid tumors", abstract)
        self.assertTrue(is_relevant(CFG, score))
        self.assertTrue(any("细胞疗法" in l for l in labels))

    def test_gene_therapy_positive(self):
        score, labels = self._score("Lipid nanoparticles enable CRISPR genome editing in the lung")
        self.assertTrue(is_relevant(CFG, score))
        self.assertTrue(any("基因治疗" in l for l in labels))
        self.assertTrue(any("肺部靶向" in l for l in labels))

    def test_unrelated_rejected(self):
        score, labels = self._score("Quantum simulation of topological insulators at low temperature")
        self.assertFalse(is_relevant(CFG, score))
        self.assertEqual(labels, [])

    def test_single_abstract_hit_not_enough(self):
        score, labels = self._score("Climate change effects on agriculture", "We discuss the lung microbiome.")
        self.assertFalse(is_relevant(CFG, score))

    def test_all_directions_covered_by_keywords(self):
        cases = {
            "药物递送系统": ("Polymeric drug delivery systems for oral administration", ""),
            "自组装多肽": ("Self-assembling peptide hydrogels for tissue repair", ""),
            "纳米药物": ("Gold nanoparticles for cancer photothermal therapy", ""),
            "肿瘤治疗": ("Combination immunotherapy against melanoma", ""),
            "细胞搭便车": ("Macrophage-mediated delivery of nanomedicines to tumors", ""),
            "肺部靶向": ("Inhaled aerosol formulations for cystic fibrosis", ""),
            "细胞疗法": ("NK cell therapy for hematologic malignancies", ""),
            "基因治疗": ("AAV-based gene therapy for hemophilia", ""),
        }
        for label, (title, abstract) in cases.items():
            with self.subTest(label=label):
                score, labels = self._score(title, abstract)
                self.assertTrue(is_relevant(CFG, score), title)
                self.assertTrue(any(label in l for l in labels), title)


if __name__ == "__main__":
    unittest.main()

