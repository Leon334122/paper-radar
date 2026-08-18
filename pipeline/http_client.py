"""带重试的 HTTP 工具。"""

from __future__ import annotations

import time

import requests


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36 paper-radar/1.1"
}


class HttpError(RuntimeError):
    pass


def get_json(
    url: str,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: int = 30,
    retries: int = 2,
    sleep: float = 1.0,
) -> dict:
    return _request("GET", url, params=params, headers=headers, timeout=timeout, retries=retries, sleep=sleep, json_mode=True)


def get_text(
    url: str,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: int = 30,
    retries: int = 2,
    sleep: float = 1.0,
) -> str:
    return _request("GET", url, params=params, headers=headers, timeout=timeout, retries=retries, sleep=sleep, json_mode=False)


def post_json(
    url: str,
    payload: dict,
    headers: dict | None = None,
    timeout: int = 60,
    retries: int = 1,
    sleep: float = 2.0,
) -> dict:
    return _request("POST", url, payload=payload, headers=headers, timeout=timeout, retries=retries, sleep=sleep, json_mode=True)


def _request(method: str, url: str, *, params=None, headers=None, payload=None, timeout: int, retries: int, sleep: float, json_mode: bool):
    last_err: Exception | None = None
    merged_headers = dict(DEFAULT_HEADERS)
    if headers:
        merged_headers.update(headers)
    for attempt in range(retries + 1):
        try:
            if method == "GET":
                r = requests.get(url, params=params, headers=merged_headers, timeout=timeout)
            else:
                r = requests.post(url, json=payload, headers=merged_headers, timeout=timeout)
            if r.status_code == 200:
                return r.json() if json_mode else r.text
            if r.status_code in (429, 500, 502, 503, 504):
                raise HttpError(f"{method} {url} -> HTTP {r.status_code}")
            r.raise_for_status()
        except (requests.RequestException, HttpError) as e:
            last_err = e
            if attempt < retries:
                time.sleep(sleep * (attempt + 1))
    raise RuntimeError(f"{method} {url} 失败: {last_err}")
