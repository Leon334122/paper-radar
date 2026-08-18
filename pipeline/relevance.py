"""关键词相关性筛选。"""

from __future__ import annotations

from .config import Config


def score_paper(cfg: Config, title: str | None, abstract: str | None) -> tuple[int, list[str]]:
    """返回 (分数, 命中方向标签列表)。
    规则：标题命中任一关键词，或同一方向在摘要中命中 >=2 个关键词，即入选。
    """
    title = (title or "").lower()
    abstract = (abstract or "").lower()
    score = 0
    hit_labels: list[str] = []
    for d in cfg.directions:
        title_hits = sum(1 for kw in d.keywords if kw and kw in title)
        abstract_hits = sum(1 for kw in d.keywords if kw and kw in abstract)
        if title_hits > 0 or abstract_hits >= 2:
            score += 3 * min(title_hits, 3) + 1 * min(abstract_hits, 3)
            hit_labels.append(d.label)
    return score, hit_labels


def is_relevant(cfg: Config, score: int) -> bool:
    return score >= cfg.min_score

