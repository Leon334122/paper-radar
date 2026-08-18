"""论文数据模型与通用工具。"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Iterable


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def norm_title(title: str | None) -> str:
    if not title:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def parse_date(value: str | None) -> str | None:
    """把多种日期写法统一为 YYYY-MM-DD；无法解析时返回 None。"""
    if not value:
        return None
    s = str(value).strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return m.group(0)
    m = re.match(r"(\d{4})-(\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-01"
    m = re.match(r"(\d{4})", s)
    if m:
        return f"{m.group(1)}-01-01"
    try:
        dt = parsedate_to_datetime(s)
        return dt.date().isoformat()
    except (TypeError, ValueError):
        pass
    return None


def date_to_dt(date_str: str | None) -> datetime | None:
    d = parse_date(date_str)
    if not d:
        return None
    try:
        return datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def is_future_beyond(date_str: str | None, days: int = 7) -> bool:
    d = date_to_dt(date_str)
    if not d:
        return False
    return d > datetime.now(timezone.utc) + timedelta(days=days)


def today_utc() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def days_ago(days: int) -> str:
    return (datetime.now(timezone.utc).date() - timedelta(days=days)).isoformat()


def paper_key(p: dict[str, Any]) -> str:
    """去重主键：DOI > 原文 URL > 标题+期刊。"""
    if p.get("doi"):
        return "doi:" + str(p["doi"]).lower().strip()
    if p.get("url"):
        return "url:" + str(p["url"]).strip()
    title = norm_title(p.get("title"))
    journal = (p.get("journal") or "").strip().lower()
    return "t:" + title + "|" + journal


def merge_paper(existing: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """合并两条同键记录：已存在的非空字段优先，缺失字段用新值补齐。"""
    merged = dict(existing)
    for k, v in new.items():
        if k == "first_seen":
            continue
        cur = merged.get(k)
        if k == "directions":
            merged[k] = sorted(set((cur or []) + (v or [])))
        elif k == "summary":
            if not cur and v:
                merged[k] = v
        elif k == "publication_date":
            if not cur:
                merged[k] = v
            elif v and cur != v and is_future_beyond(cur) and not is_future_beyond(v):
                merged[k] = v
                if new.get("date_precision"):
                    merged["date_precision"] = new["date_precision"]
        elif v not in (None, "", []):
            if cur in (None, "", []):
                merged[k] = v
    old_fs = existing.get("first_seen") or new.get("first_seen") or now_iso()
    new_fs = new.get("first_seen") or existing.get("first_seen") or now_iso()
    merged["first_seen"] = min(old_fs, new_fs)
    return merged


def dedupe_papers(papers: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for p in papers:
        key = paper_key(p)
        if not key or key == "t:|":
            continue
        if key in seen:
            seen[key] = merge_paper(seen[key], p)
        else:
            seen[key] = dict(p)
    return list(seen.values())


def retain_papers(papers: list[dict[str, Any]], days: int = 90) -> list[dict[str, Any]]:
    """滚动保留：发表日期或首次收录时间在窗口内（含在线优先的未来日期）。"""
    cutoff = date_to_dt(days_ago(days))
    if not cutoff:
        return papers
    kept = []
    for p in papers:
        pub = date_to_dt(p.get("publication_date"))
        seen = date_to_dt(p.get("first_seen"))
        if (pub and pub >= cutoff) or (seen and seen >= cutoff):
            kept.append(p)
    return kept


def ensure_required_fields(p: dict[str, Any]) -> dict[str, Any]:
    p.setdefault("doi", None)
    p.setdefault("title", "")
    p.setdefault("authors", [])
    p.setdefault("journal", "")
    p.setdefault("journal_issn", None)
    p.setdefault("tier", "")
    p.setdefault("publication_date", None)
    p.setdefault("date_precision", "day")
    p.setdefault("first_seen", now_iso())
    p.setdefault("url", None)
    p.setdefault("url_doi", f"https://doi.org/{p['doi']}" if p.get("doi") else None)
    p.setdefault("url_pubmed", None)
    p.setdefault("abstract", None)
    p.setdefault("abstract_source", None)
    p.setdefault("directions", [])
    p.setdefault("relevance_score", 0)
    p.setdefault("relevant", False)
    p.setdefault("summary_status", "pending")
    p.setdefault("summary", None)
    p.setdefault("source", None)
    return p
