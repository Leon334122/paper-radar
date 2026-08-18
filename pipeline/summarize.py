"""DeepSeek 中文总结（OpenAI 兼容接口，直接走 HTTP）。"""

from __future__ import annotations

import json
import logging
import os
import re

from .http_client import post_json
from .models import now_iso

log = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "你是一位药学与纳米医学领域的中文科研助手。请阅读给定的文献信息，输出严格的 JSON，"
    '格式为 {"one_liner": "一句话概述（30-50字）", "innovation": "创新点（2-3条，分号分隔）", '
    '"significance": "意义与应用前景（2-3句）"}。只输出 JSON，不要输出 Markdown 或其他文字。'
)


def _build_user_message(p: dict) -> str:
    lines = [f"标题：{p.get('title')}"]
    lines.append(f"期刊：{p.get('journal')}（层级 {p.get('tier')}）")
    if p.get("publication_date"):
        lines.append(f"发表日期：{p.get('publication_date')}")
    if p.get("abstract"):
        lines.append(f"摘要：{p.get('abstract')}")
    else:
        lines.append("摘要：（暂无摘要，请仅依据标题概括）")
    return "\n".join(lines)


def summarize_paper(
    p: dict,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    timeout: int = 90,
) -> dict | None:
    api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        log.info("未配置 DEEPSEEK_API_KEY，跳过总结：%s", p.get("title", "")[:60])
        return None
    base_url = (base_url or os.environ.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com").rstrip("/")
    model = model or os.environ.get("DEEPSEEK_MODEL") or "deepseek-v4-flash"
    payload = {
        "model": model,
        "temperature": 0.3,
        "max_tokens": 700,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_message(p)},
        ],
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        data = post_json(f"{base_url}/chat/completions", payload, headers=headers, timeout=timeout)
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        parsed = _parse_json_content(content)
        if parsed:
            parsed["model"] = model
            parsed["generated_at"] = now_iso()
        return parsed
    except Exception as e:
        log.warning("DeepSeek 总结失败 %s: %s", p.get("title", "")[:60], e)
        return None


def _parse_json_content(content: str) -> dict | None:
    if not content:
        return None
    text = content.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict):
        return None
    one = data.get("one_liner") or data.get("概述") or data.get("summary")
    inn = data.get("innovation") or data.get("创新点")
    sig = data.get("significance") or data.get("意义")
    if not (one or inn or sig):
        return None
    return {
        "one_liner": str(one).strip() if one else "",
        "innovation": str(inn).strip() if inn else "",
        "significance": str(sig).strip() if sig else "",
    }
