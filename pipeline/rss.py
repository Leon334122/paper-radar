"""RSS 解析：兼容 RSS 1.0 (RDF) 与 RSS 2.0。"""

from __future__ import annotations

import html
import logging
import re
from xml.etree import ElementTree as ET

from .http_client import get_text
from .models import parse_date

log = logging.getLogger(__name__)

NS = {
    "": "http://purl.org/rss/1.0/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "dc": "http://purl.org/dc/elements/1.1/",
    "prism": "http://prismstandard.org/namespaces/basic/2.0/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "atom": "http://www.w3.org/2005/Atom",
}


def _local(el: ET.Element) -> str:
    tag = el.tag
    return tag.rsplit("}", 1)[-1]


def _child_text(el: ET.Element, names: list[str]) -> str | None:
    for name in names:
        found = el.find(name) if name else None
        if found is not None and found.text:
            return found.text.strip()
    return None


def _find_items(root: ET.Element) -> list[ET.Element]:
    """兼容 RSS 1.0（默认命名空间）与 RSS 2.0（无命名空间）的 item 元素。"""
    items: list[ET.Element] = []
    for el in root.iter():
        if _local(el) == "item" and el is not root:
            items.append(el)
    return items


def _field(item: ET.Element, rss1: str, names: list[str]) -> str | None:
    return _child_text(item, [f"{{{NS['']}}}{rss1}"] + names)


def _strip_html(value: str | None) -> str | None:
    if not value:
        return None
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip() or None


def extract_doi(url: str | None) -> str | None:
    if not url:
        return None
    m = re.search(r"articles/(s\d+[a-z0-9\-]*)$", url, re.I)
    if m:
        return "10.1038/" + m.group(1)
    m = re.search(r"doi\.org/(10\.\S+)", url, re.I)
    if m:
        return m.group(1).rstrip("/")
    m = re.search(r"doi=10\.\S+", url, re.I)
    if m:
        return m.group(0).split("=", 1)[1].rstrip("/")
    m = re.search(r"(10\.\d{4,9}/[^\s\"'<>]+)", url)
    if m:
        return m.group(1).rstrip("/")
    return None


def fetch_rss(url: str, journal: str, tier: str) -> list[dict]:
    try:
        content = get_text(url, timeout=40, retries=2)
    except Exception as e:
        log.warning("RSS 抓取失败 %s: %s", url, e)
        return []
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        log.warning("RSS 解析失败 %s: %s", url, e)
        return []
    items = _find_items(root)
    records: list[dict] = []
    for item in items:
        about = item.get(f"{{{NS['rdf']}}}about")
        link = _field(item, "link", ["link"]) or about
        title = _field(item, "title", ["title", f"{{{NS['dc']}}}title"])
        if not title:
            continue
        date = _child_text(item, [f"{{{NS['dc']}}}date", f"{{{NS['prism']}}}publicationDate", "pubDate"]) or _field(item, "date", [])
        desc = _field(item, "description", ["description", f"{{{NS['content']}}}encoded"])
        doi = extract_doi(link)
        records.append(
            {
                "doi": doi,
                "title": title.strip(),
                "authors": [],
                "journal": journal,
                "journal_issn": None,
                "tier": tier,
                "publication_date": parse_date(date),
                "date_precision": "day" if parse_date(date) else None,
                "url": link or None,
                "abstract": _strip_html(desc),
                "abstract_source": "rss",
                "source": "rss",
            }
        )
    return records
