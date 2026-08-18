"""生成静态网站数据（site/data/papers.json）。"""

from __future__ import annotations

import json
from pathlib import Path

from .config import Config
from .models import ensure_required_fields, now_iso


def build_site(cfg: Config, papers: list[dict], only_relevant: bool = True) -> Path:
    site_data = cfg.site_dir / "data"
    site_data.mkdir(parents=True, exist_ok=True)
    rows = []
    for p in papers:
        p = ensure_required_fields(p)
        if only_relevant and not p.get("relevant"):
            continue
        rows.append(
            {
                "doi": p.get("doi"),
                "title": p.get("title", ""),
                "authors": p.get("authors", []),
                "journal": p.get("journal", ""),
                "tier": p.get("tier", ""),
                "publication_date": p.get("publication_date"),
                "date_precision": p.get("date_precision", "day"),
                "directions": p.get("directions", []),
                "relevance_score": p.get("relevance_score", 0),
                "url": p.get("url"),
                "url_doi": p.get("url_doi"),
                "url_pubmed": p.get("url_pubmed"),
                "abstract": p.get("abstract"),
                "abstract_source": p.get("abstract_source"),
                "summary_status": p.get("summary_status", "pending"),
                "summary": p.get("summary"),
                "source": p.get("source"),
            }
        )
    rows.sort(key=lambda r: (r.get("publication_date") or "0000-00-00"), reverse=True)
    payload = {
        "updated_at": now_iso(),
        "count": len(rows),
        "note": "本文件由 pipeline build 自动生成，请勿手工编辑。",
        "papers": rows,
    }
    out = site_data / "papers.json"
    with out.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    return out
