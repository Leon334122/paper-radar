"""摘要获取：PubMed E-utilities 为主，Europe PMC 兜底。"""

from __future__ import annotations

import logging
import time
from xml.etree import ElementTree as ET

from .http_client import get_json, get_text
from .models import norm_title

log = logging.getLogger(__name__)

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"


def fetch_abstract(doi: str | None, title: str | None, journal: str | None) -> dict | None:
    """返回 {abstract, pmid, source}；失败返回 None。"""
    if doi:
        r = _pubmed_by_doi(doi)
        if r:
            return r
    if title:
        r = _pubmed_by_title(title, journal)
        if r:
            return r
    if doi:
        r = _europepmc_by_doi(doi)
        if r:
            return r
    return None


def _pubmed_by_doi(doi: str) -> dict | None:
    try:
        data = get_json(
            f"{EUTILS}/esearch.fcgi",
            params={"db": "pubmed", "term": f'"{doi}"[DOI]', "retmode": "json", "retmax": "3"},
            timeout=30,
        )
        ids = data.get("esearchresult", {}).get("idlist", [])
        time.sleep(0.34)
        if ids:
            return _pubmed_fetch(ids[0])
    except Exception as e:
        log.debug("PubMed DOI 检索失败 %s: %s", doi, e)
    return None


def _pubmed_by_title(title: str, journal: str | None) -> dict | None:
    phrase = norm_title(title)
    if len(phrase) > 100:
        phrase = " ".join(phrase.split()[:16])
    term = f'"{phrase}"[Title]'
    if journal:
        term += f' AND "{journal}"[Journal]'
    try:
        data = get_json(
            f"{EUTILS}/esearch.fcgi",
            params={"db": "pubmed", "term": term, "retmode": "json", "retmax": "3"},
            timeout=30,
        )
        ids = data.get("esearchresult", {}).get("idlist", [])
        time.sleep(0.34)
        if ids:
            return _pubmed_fetch(ids[0])
    except Exception as e:
        log.debug("PubMed 标题检索失败 %s: %s", title[:60], e)
    return None


def _pubmed_fetch(pmid: str) -> dict | None:
    try:
        xml = get_text(
            f"{EUTILS}/efetch.fcgi",
            params={"db": "pubmed", "id": pmid, "rettype": "abstract", "retmode": "xml"},
            timeout=40,
        )
        root = ET.fromstring(xml)
        abstract_parts = []
        for node in root.iter("AbstractText"):
            label = node.get("Label")
            text = "".join(node.itertext()).strip()
            if text:
                abstract_parts.append(f"{label}: {text}" if label else text)
        abstract = " ".join(abstract_parts).strip() or None
        if not abstract:
            return None
        return {"abstract": abstract, "pmid": pmid, "source": "pubmed"}
    except Exception as e:
        log.debug("PubMed 摘要获取失败 %s: %s", pmid, e)
    return None


def _europepmc_by_doi(doi: str) -> dict | None:
    try:
        data = get_json(
            f"{EPMC}/search",
            params={"query": f'DOI:"{doi}"', "resultType": "core", "format": "json", "pageSize": "1"},
            timeout=30,
        )
        result = (data.get("resultList") or {}).get("result") or []
        if not result:
            return None
        r = result[0]
        abstract = (r.get("abstractText") or "").strip() or None
        if not abstract:
            return None
        return {"abstract": abstract, "pmid": r.get("pmid"), "source": "europepmc"}
    except Exception as e:
        log.debug("Europe PMC 摘要获取失败 %s: %s", doi, e)
    return None

