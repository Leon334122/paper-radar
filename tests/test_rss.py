import unittest
from xml.etree import ElementTree as ET

from pipeline.rss import _strip_html, extract_doi, fetch_rss

RSS1 = """<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:dc="http://purl.org/dc/elements/1.1/"
         xmlns:prism="http://prismstandard.org/namespaces/basic/2.0/"
         xmlns="http://purl.org/rss/1.0/">
  <channel rdf:about="http://example.com/feed">
    <title>Test Journal</title>
  </channel>
  <item rdf:about="https://www.nature.com/articles/s41551-026-01765-w">
    <title>A peptide nanofiber study</title>
    <link>https://www.nature.com/articles/s41551-026-01765-w</link>
    <dc:date>2026-08-15</dc:date>
    <description>Self-assembling peptides for drug delivery &amp; lung targeting.</description>
  </item>
</rdf:RDF>"""

RSS2 = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Feed</title>
    <item>
      <title>CRISPR gene therapy advances</title>
      <link>https://example.org/paper/1</link>
      <pubDate>Mon, 17 Aug 2026 08:00:00 GMT</pubDate>
      <description>Gene editing with AAV vectors.</description>
    </item>
  </channel>
</rss>"""


class TestRss(unittest.TestCase):
    def test_fetch_rss1(self, monkey=None):
        # 直接解析本地 XML 字符串：临时替换 get_text
        import pipeline.rss as rss_mod
        original = rss_mod.get_text
        rss_mod.get_text = lambda url, **kw: RSS1
        try:
            records = rss_mod.fetch_rss("http://x", "NBE", "A")
        finally:
            rss_mod.get_text = original
        self.assertEqual(len(records), 1)
        r = records[0]
        self.assertEqual(r["title"], "A peptide nanofiber study")
        self.assertEqual(r["doi"], "10.1038/s41551-026-01765-w")
        self.assertEqual(r["publication_date"], "2026-08-15")
        self.assertIn("Self-assembling", r["abstract"])

    def test_fetch_rss2(self):
        import pipeline.rss as rss_mod
        original = rss_mod.get_text
        rss_mod.get_text = lambda url, **kw: RSS2
        try:
            records = rss_mod.fetch_rss("http://x", "Science", "S")
        finally:
            rss_mod.get_text = original
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["title"], "CRISPR gene therapy advances")
        self.assertEqual(records[0]["publication_date"], "2026-08-17")

    def test_extract_doi(self):
        self.assertEqual(extract_doi("https://www.nature.com/articles/s41551-026-01765-w"), "10.1038/s41551-026-01765-w")
        self.assertEqual(extract_doi("https://doi.org/10.1021/acsnano.5c06178"), "10.1021/acsnano.5c06178")
        self.assertIsNone(extract_doi("https://example.com/paper/1"))

    def test_strip_html(self):
        self.assertEqual(_strip_html("<p>Hello <b>world</b> &amp; friends</p>"), "Hello world & friends")
        self.assertIsNone(_strip_html(None))


if __name__ == "__main__":
    unittest.main()
