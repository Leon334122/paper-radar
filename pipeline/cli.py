"""命令行入口：python -m pipeline run / build。"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .abstracts import fetch_abstract
from .build_site import build_site
from .config import load_config
from .models import days_ago, ensure_required_fields, merge_paper, now_iso, paper_key
from .relevance import is_relevant, score_paper
from .rss import fetch_rss
from .sources import fetch_crossref, fetch_openalex, resolve_doi_by_title
from .storage import load_papers, normalize_store, save_papers
from .summarize import summarize_paper

log = logging.getLogger("pipeline")


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)


def _fetch_metadata_for_journal(journal, start_date: str, mailto: str | None, use_crossref_fallback: bool = True) -> list[dict]:
    records: list[dict] = []
    used_fallback = False
    try:
        records = fetch_openalex(journal, start_date, mailto=mailto)
        log.info("[%s] OpenAlex 返回 %d 条", journal.name, len(records))
    except Exception as e:
        log.warning("[%s] OpenAlex 失败: %s", journal.name, e)
    if (not records or len(records) < 10) and use_crossref_fallback:
        try:
            extra = fetch_crossref(journal, start_date)
            log.info("[%s] Crossref 补充返回 %d 条", journal.name, len(extra))
            records = records + extra
            used_fallback = True
        except Exception as e:
            log.warning("[%s] Crossref 补充失败: %s", journal.name, e)
    return records, used_fallback


def _collect_rss(cfg, start_date: str) -> list[dict]:
    records: list[dict] = []
    doi_lookups = 0
    for j in cfg.enabled_journals:
        for url in j.rss:
            items = fetch_rss(url, j.name, j.tier)
            kept = 0
            for it in items:
                if (it.get("publication_date") or "9999") < start_date:
                    continue
                if not it.get("doi") and "/articles/" in (it.get("url") or "") and doi_lookups < 40:
                    it["doi"] = resolve_doi_by_title(it.get("title", ""), j.name)
                    doi_lookups += 1
                    time.sleep(0.2)
                records.append(it)
                kept += 1
            if kept:
                log.info("[%s] RSS %s 新增 %d 条", j.name, url.rsplit("/", 1)[-1], kept)
    return records


def _enrich_abstracts(papers: list[dict], max_fetches: int = 300) -> int:
    """并发补充摘要（NCBI 无 API key 限速 3 次/秒，用 3 个并发安全可控）。"""
    targets = [p for p in papers if not p.get("abstract") and p.get("doi")][:max_fetches]
    fetched = 0
    if not targets:
        return 0
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            pool.submit(fetch_abstract, p.get("doi"), p.get("title"), p.get("journal")): p
            for p in targets
        }
        for fut in as_completed(futures):
            p = futures[fut]
            try:
                r = fut.result()
            except Exception:
                r = None
            if r:
                p["abstract"] = r["abstract"]
                p["abstract_source"] = r["source"]
                if r.get("pmid"):
                    p["url_pubmed"] = f"https://pubmed.ncbi.nlm.nih.gov/{r['pmid']}/"
                fetched += 1
    return fetched


def run_pipeline(args) -> None:
    cfg = load_config(args.config_dir, args.data_dir, args.site_dir)
    data_file = Path(args.data_dir) / "papers.json"
    start_date = days_ago(args.days)
    mailto = os.environ.get("OPENALEX_MAILTO")

    existing = load_papers(data_file)
    existing_by_key = {paper_key(p): p for p in existing}
    log.info("已有记录 %d 条", len(existing))

    new_records: list[dict] = []
    for j in cfg.enabled_journals:
        recs, _ = _fetch_metadata_for_journal(j, start_date, mailto)
        new_records += recs
    new_records += _collect_rss(cfg, start_date)
    log.info("本次共抓取 %d 条原始记录", len(new_records))

    merged: dict[str, dict] = {}
    for rec in new_records:
        rec = ensure_required_fields(rec)
        key = paper_key(rec)
        if key in merged:
            merged[key] = merge_paper(merged[key], rec)
        else:
            merged[key] = rec
    for key, rec in merged.items():
        if key in existing_by_key:
            existing_by_key[key] = merge_paper(existing_by_key[key], rec)
        else:
            existing_by_key[key] = rec

    all_papers = normalize_store(list(existing_by_key.values()), days=args.retain_days)
    log.info("去重/保留后共 %d 条", len(all_papers))

    fresh = [
        p
        for p in all_papers
        if p.get("first_seen") >= start_date or p.get("publication_date", "") >= start_date
    ]
    n_abs = _enrich_abstracts(fresh, max_fetches=args.max_abstracts)
    log.info("补充摘要 %d 条", n_abs)

    excluded_terms = [t.lower() for t in cfg.excluded_title_terms]
    relevant_count = 0
    for p in all_papers:
        title_lower = (p.get("title") or "").lower()
        if any(t in title_lower for t in excluded_terms):
            score, directions = 0, []
        else:
            score, directions = score_paper(cfg, p.get("title"), p.get("abstract"))
        p["relevance_score"] = score
        p["directions"] = directions
        p["relevant"] = is_relevant(cfg, score)
        if p["relevant"]:
            relevant_count += 1
    log.info("相关文章 %d 条", relevant_count)

    if not args.skip_summary:
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            log.warning("未设置 DEEPSEEK_API_KEY：相关文章的总结将保持“待补充”状态")
        to_summarize = [p for p in all_papers if p.get("relevant") and not p.get("summary")]
        for i, p in enumerate(to_summarize, 1):
            summary = summarize_paper(p, timeout=args.summary_timeout)
            if summary:
                p["summary"] = summary
                p["summary_status"] = "done"
            else:
                p["summary_status"] = "pending"
            log.info("总结进度 %d/%d", i, len(to_summarize))
    else:
        log.info("已跳过 AI 总结（--skip-summary）")

    if args.dry_run:
        log.info("--dry-run：不保存数据、不生成网站")
    else:
        save_papers(data_file, all_papers)
        log.info("已写入 %s", data_file)
        out = build_site(cfg, all_papers)
        log.info("已生成网站数据 %s（相关文章 %d 条）", out, relevant_count)


def build_command(args) -> None:
    cfg = load_config(args.config_dir, args.data_dir, args.site_dir)
    papers = load_papers(Path(args.data_dir) / "papers.json")
    out = build_site(cfg, papers)
    log.info("已生成网站数据 %s", out)


def rescore_command(args) -> None:
    """仅对已抓取数据重新做相关性评分与建站（调整关键词/阈值后无需重抓）。"""
    cfg = load_config(args.config_dir, args.data_dir, args.site_dir)
    data_file = Path(args.data_dir) / "papers.json"
    papers = load_papers(data_file)
    excluded_terms = [t.lower() for t in cfg.excluded_title_terms]
    relevant_count = 0
    for p in papers:
        title_lower = (p.get("title") or "").lower()
        if any(t in title_lower for t in excluded_terms):
            score, directions = 0, []
        else:
            score, directions = score_paper(cfg, p.get("title"), p.get("abstract"))
        p["relevance_score"] = score
        p["directions"] = directions
        p["relevant"] = is_relevant(cfg, score)
        if p["relevant"]:
            relevant_count += 1
    save_papers(data_file, papers)
    log.info("重新评分完成：相关文章 %d 条", relevant_count)
    out = build_site(cfg, papers)
    log.info("已生成网站数据 %s", out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pipeline", description="个人文献雷达抓取与建站")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="抓取-筛选-总结-建站全流程")
    p_run.add_argument("--days", type=int, default=7, help="回溯天数（默认 7）")
    p_run.add_argument("--retain-days", type=int, default=90, help="滚动保留天数（默认 90）")
    p_run.add_argument("--skip-summary", action="store_true", help="跳过 AI 总结")
    p_run.add_argument("--dry-run", action="store_true", help="只抓取统计，不落盘")
    p_run.add_argument("--max-abstracts", type=int, default=300, help="单次补充摘要上限")
    p_run.add_argument("--summary-timeout", type=int, default=90)
    p_run.add_argument("--verbose", action="store_true")
    p_run.set_defaults(func=run_pipeline)

    p_build = sub.add_parser("build", help="仅根据已有数据重建网站")
    p_build.add_argument("--verbose", action="store_true")
    p_build.set_defaults(func=build_command)

    p_rescore = sub.add_parser("rescore", help="调整关键词后仅重新评分与建站")
    p_rescore.add_argument("--verbose", action="store_true")
    p_rescore.set_defaults(func=rescore_command)

    for p in (p_run, p_build, p_rescore):
        p.add_argument("--config-dir", default="config")
        p.add_argument("--data-dir", default="data")
        p.add_argument("--site-dir", default="site")

    args = parser.parse_args(argv)
    _setup_logging(getattr(args, "verbose", False))
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
