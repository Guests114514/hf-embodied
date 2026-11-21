import datetime
import json
import os
import time

import requests

import config

RETRY_ERRORS = (requests.exceptions.SSLError,
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout)
_SESSION = requests.Session()
_SESSION.headers.update(config.HEADERS)

def _get(path, params=None):
    resp = None
    for attempt in range(3):
        try:
            resp = _SESSION.get(config.BASE_URL + path, params=params or {},
                                timeout=30)
        except RETRY_ERRORS as e:
            resp = None
            wait = 2 * (attempt + 1)
            print(f"  网络抖动 {type(e).__name__}，等 {wait}s 重试（第 {attempt + 1}/3 次）")
            time.sleep(wait)
            continue
        if resp.status_code == 429:
            wait = 5 * (attempt + 1)
            print(f"  被限流 429，等 {wait}s 重试（第 {attempt + 1}/3 次）")
            time.sleep(wait)
            continue
        return resp
    if resp is None:
        raise RuntimeError(f"连续 3 次都连不上：{path}")
    return resp


def _json(resp, path):
    try:
        return resp.json()
    except ValueError:
        raise RuntimeError(f"{path} 返回的不是 JSON，前 200 字：{resp.text[:200]}")


def fetch(path, params=None):
    resp = _get(path, params)
    resp.raise_for_status()
    return _json(resp, path)


def fetch_or_none(path, params=None):
    resp = _get(path, params)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return _json(resp, path)
def fetch_text(path):
    """受限仓库返回 401/403、README 不存在返回 404，这三种都按拿不到处理。"""
    resp = _get(path)
    if resp.status_code in (401, 403, 404):
        return None
    resp.raise_for_status()
    return resp.text


def save_text(name, text):
    os.makedirs(config.RAW_DIR, exist_ok=True)
    path = os.path.join(config.RAW_DIR, f"{name}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path

def save_raw(name, obj):
    os.makedirs(config.RAW_DIR, exist_ok=True)
    path = os.path.join(config.RAW_DIR, f"{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    return path


def today():
    return datetime.date.today().isoformat()