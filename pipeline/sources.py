"""元数据抓取：OpenAlex 为主，Crossref 兜底。"""

from __future__ import annotations

import logging
import time
from datetime import date, timedelta

from .config import Journal
from .http_client import get_json
from .models import parse_date

log = logging.getLogger(__name__)

OPENALEX_BASE = "https://api.openalex.org/works"
CROSSREF_BASE = "https://api.crossref.org/journals"


def _openalex_abstract(inverted: dict | None) -> str | None:
    if not inverted:
        return None
    positions = []
    for word, idxs in inverted.items():
        for i in idxs:
            positions.append((i, word))
    positions.sort()
    return " ".join(w for _, w in positions).strip() or None


def fetch_openalex(journal: Journal, start_date: str, mailto: str | None = None, max_pages: int = 8) -> list[dict]:
    params = {
        "filter": f"from_publication_date:{start_date},primary_location.source.issn:{journal.issn},type:article",
        "per-page": "100",
        "sort": "publication_date:desc",
        "select": "id,doi,title,publication_date,authorships,primary_location,abstract_inverted_index",
    }
    if mailto:
        params["mailto"] = mailto
    records: list[dict] = []
    cursor: str | None = None
    for _ in range(max_pages):
        p = dict(params)
        if cursor:
            p["cursor"] = cursor
        data = get_json(OPENALEX_BASE, params=p, timeout=40)
        works = data.get("results", [])
        for w in works:
            doi = (w.get("doi") or "").strip()
            pub_date = parse_date(w.get("publication_date"))
            title = (w.get("title") or "").strip()
            source = (w.get("primary_location") or {}).get("source") or {}
            authors = [
                a.get("author", {}).get("display_name")
                for a in w.get("authorships", [])[:20]
                if a.get("author", {}).get("display_name")
            ]
            if not title:
                continue
            records.append(
                {
                    "doi": doi.lstrip("https://doi.org/") or None,
                    "title": title,
                    "authors": authors,
                    "journal": source.get("display_name") or journal.name,
                    "journal_issn": journal.issn,
                    "tier": journal.tier,
                    "publication_date": pub_date,
                    "url": (w.get("doi") or "").strip() or None,
                    "abstract": _openalex_abstract(w.get("abstract_inverted_index")),
                    "abstract_source": "openalex" if w.get("abstract_inverted_index") else None,
                    "source": "openalex",
                }
            )
        meta = data.get("meta", {})
        cursor = meta.get("next_cursor")
        if not cursor or not works:
            break
        if records and (records[-1].get("publication_date") or "9999") < start_date:
            break
        time.sleep(0.15)
    return records


def fetch_crossref(journal: Journal, start_date: str, rows: int = 200, buffer_days: int = 14) -> list[dict]:
    """Crossref 兜底/补充：日期窗口前移 buffer_days，避免“仅月份粒度”的在线优先文章漏掉。"""
    try:
        start_dt = date.fromisoformat(start_date) - timedelta(days=buffer_days)
        api_start = start_dt.isoformat()
    except ValueError:
        api_start = start_date
    params = {
        "filter": f"from-pub-date:{api_start},type:journal-article",
        "rows": str(rows),
        "sort": "published",
        "order": "desc",
        "select": "DOI,title,author,abstract,issued,published-online,published,created,URL,container-title",
    }
    data = get_json(f"{CROSSREF_BASE}/{journal.issn}/works", params=params, timeout=40)
    records: list[dict] = []
    for item in data.get("message", {}).get("items", []):
        title = (item.get("title") or [""])[0].strip()
        doi = (item.get("DOI") or "").strip()
        if not title:
            continue
        date_node = item.get("published-online") or item.get("issued") or item.get("published")
        has_online = bool(item.get("published-online"))
        pub_date = _crossref_date(date_node)
        date_precision = _crossref_date_precision(date_node)
        if pub_date and not has_online and _is_future(pub_date, days=7):
            # 只有未来印刷期号日期（无在线日期）时，用 Crossref 元数据创建时间近似发表时间
            created = _crossref_date(item.get("created"))
            if created and not _is_future(created, days=2):
                pub_date, date_precision = created, "approx"
            else:
                pub_date, date_precision = None, None
        authors = [
            " ".join(x for x in [a.get("given"), a.get("family")] if x)
            for a in item.get("author", [])[:20]
        ]
        container = (item.get("container-title") or [""])
        container = container[0] if isinstance(container, list) else str(container)
        records.append(
            {
                "doi": doi or None,
                "title": title,
                "authors": authors,
                "journal": container.strip() or journal.name,
                "journal_issn": journal.issn,
                "tier": journal.tier,
                "publication_date": pub_date,
                "date_precision": date_precision,
                "url": f"https://doi.org/{doi}" if doi else (item.get("URL") or None),
                "abstract": (item.get("abstract") or "").strip() or None,
                "abstract_source": "crossref" if item.get("abstract") else None,
                "source": "crossref",
            }
        )
    return records


def _crossref_date(node: dict | None) -> str | None:
    if not node:
        return None
    parts = node.get("date-parts") or []
    if not parts or not parts[0]:
        return None
    p = parts[0]
    if len(p) >= 3:
        return f"{p[0]}-{p[1]:02d}-{p[2]:02d}"
    if len(p) == 2:
        return f"{p[0]}-{p[1]:02d}-01"
    if len(p) == 1:
        return f"{p[0]}-01-01"
    return None


def _crossref_date_precision(node: dict | None) -> str | None:
    if not node:
        return None
    parts = node.get("date-parts") or []
    if not parts or not parts[0]:
        return None
    return "day" if len(parts[0]) >= 3 else "month"


def _is_future(date_str: str | None, days: int = 45) -> bool:
    if not date_str:
        return False
    try:
        d = date.fromisoformat(date_str)
    except ValueError:
        return False
    return d > date.today() + timedelta(days=days)


def resolve_doi_by_title(title: str, journal_name: str) -> str | None:
    """RSS 条目缺少 DOI 时，用标题在 Crossref 检索补全 DOI。"""
    try:
        data = get_json(
            "https://api.crossref.org/works",
            params={
                "query.bibliographic": title,
                "rows": "3",
                "select": "DOI,title,container-title,published-online,issued",
            },
            timeout=30,
        )
        for item in data.get("message", {}).get("items", []):
            container = item.get("container-title") or [""]
            container = container[0] if isinstance(container, list) else str(container)
            if journal_name.lower() in container.lower():
                return (item.get("DOI") or "").strip() or None
    except Exception:
        log.warning("Crossref 标题检索失败: %r", title[:80])
    return None
