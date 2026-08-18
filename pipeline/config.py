"""加载 journals.json 与 keywords.yaml 配置。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Journal:
    name: str
    issn: str
    tier: str
    enabled: bool
    rss: list[str] = field(default_factory=list)


@dataclass
class Direction:
    id: str
    label: str
    keywords: list[str] = field(default_factory=list)


@dataclass
class Config:
    journals: list[Journal]
    directions: list[Direction]
    min_score: int
    excluded_title_terms: list[str]
    data_dir: Path
    site_dir: Path

    @property
    def enabled_journals(self) -> list[Journal]:
        return [j for j in self.journals if j.enabled]


def load_config(config_dir: str | Path = "config", data_dir: str | Path = "data", site_dir: str | Path = "site") -> Config:
    config_dir = Path(config_dir)
    with (config_dir / "journals.json").open("r", encoding="utf-8") as f:
        jdata = json.load(f)
    journals = [
        Journal(
            name=item["name"],
            issn=item["issn"],
            tier=item["tier"],
            enabled=bool(item.get("enabled", True)),
            rss=list(item.get("rss") or []),
        )
        for item in jdata.get("journals", [])
    ]
    with (config_dir / "keywords.yaml").open("r", encoding="utf-8") as f:
        kdata = yaml.safe_load(f)
    directions = [
        Direction(id=d["id"], label=d["label"], keywords=[str(k).lower() for k in d.get("keywords", [])])
        for d in kdata.get("directions", [])
    ]
    return Config(
        journals=journals,
        directions=directions,
        min_score=int(kdata.get("min_score", 2)),
        excluded_title_terms=[str(t).lower() for t in kdata.get("exclude_title_terms", [])],
        data_dir=Path(data_dir),
        site_dir=Path(site_dir),
    )
