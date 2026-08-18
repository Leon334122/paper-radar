"""论文存储：读取、写入、去重与滚动保留。"""

from __future__ import annotations

import json
from pathlib import Path

from .models import dedupe_papers, merge_paper, now_iso, norm_title, retain_papers


def load_papers(path: str | Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return list(data.get("papers", []))
    except (json.JSONDecodeError, OSError):
        return []


def save_papers(path: str | Path, papers: list[dict], updated_at: str | None = None) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": updated_at or now_iso(),
        "count": len(papers),
        "papers": papers,
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)


def normalize_store(papers: list[dict], days: int = 90) -> list[dict]:
    papers = dedupe_papers(papers)
    papers = dedupe_by_title(papers)
    papers = retain_papers(papers, days=days)
    papers.sort(key=lambda p: (p.get("publication_date") or "0000-00-00"), reverse=True)
    return papers


def dedupe_by_title(papers: list[dict]) -> list[dict]:
    """标题+期刊相同的记录合并（RSS URL 与 OpenAlex DOI 两条记录互认）。DOI 记录优先。"""
    groups: dict[tuple[str, str], list[dict]] = {}
    for p in papers:
        key = (norm_title(p.get("title")), (p.get("journal") or "").strip().lower())
        if key[0]:
            groups.setdefault(key, []).append(p)
    merged: list[dict] = []
    seen: set[int] = set()
    for key, group in groups.items():
        if len(group) <= 1:
            continue
        by_doi = [p for p in group if p.get("doi")]
        base = by_doi[0] if by_doi else group[0]
        for p in group:
            if p is not base:
                base = merge_paper(base, p)
            seen.add(id(p))
        merged.append(base)
    for p in papers:
        if id(p) not in seen:
            merged.append(p)
    return merged
