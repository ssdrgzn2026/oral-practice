# -*- coding: utf-8 -*-
"""
访问统计模块：记录访客时间、IP、IP 归属地、访问页面、停留时长等。
数据写入 stats/ 目录（JSONL 文件），不在网页上展示。
"""

import json
import os
import re
import threading
import time
from datetime import datetime
from pathlib import Path

import requests
from flask import request

STATS_DIR = Path(__file__).parent / "stats"
VISITS_FILE = STATS_DIR / "visits.jsonl"   # 页面访问记录
BEATS_FILE = STATS_DIR / "beats.jsonl"     # 心跳记录（用于计算停留时长）
IP_CACHE_FILE = STATS_DIR / "ip_cache.json"

_write_lock = threading.Lock()
_ip_cache = None
# nginx 反代到 Flask 的路径才统计页面访问；/convert/ /dcf/ 由 nginx 直接转发，见 nginx 访问日志
_TRACKED_PAGES = {"/", "/oral", "/tickets", "/portal"}


def _append_jsonl(path, record):
    STATS_DIR.mkdir(exist_ok=True)
    with _write_lock:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _load_ip_cache():
    global _ip_cache
    if _ip_cache is None:
        try:
            with open(IP_CACHE_FILE, "r", encoding="utf-8") as f:
                _ip_cache = json.load(f)
        except (OSError, json.JSONDecodeError):
            _ip_cache = {}
    return _ip_cache


def _save_ip_cache():
    try:
        with open(IP_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_ip_cache, f, ensure_ascii=False)
    except OSError:
        pass


def _is_internal(ip):
    if not ip:
        return True
    if ip.startswith(("127.", "10.", "192.168.")):
        return True
    if ip.startswith("172."):
        try:
            return 16 <= int(ip.split(".")[1]) <= 31
        except (IndexError, ValueError):
            return False
    return False


def geo_lookup(ip):
    """查询 IP 归属地（ipwho.is，支持 https，容器内可达），结果本地缓存。失败返回空串。"""
    if _is_internal(ip):
        return "内网"
    cache = _load_ip_cache()
    if ip in cache and cache[ip] not in ("未知", "查询中"):
        return cache[ip]

    def worker():
        try:
            r = requests.get(f"https://ipwho.is/{ip}?lang=zh-CN", timeout=5)
            d = r.json()
            if d.get("success"):
                isp = (d.get("connection") or {}).get("isp", "")
                loc = " ".join(x for x in [d.get("country"), d.get("region"), d.get("city"), isp] if x)
            else:
                loc = ""
        except requests.RequestException:
            loc = ""
        cache[ip] = loc or "未知"
        _save_ip_cache()

    threading.Thread(target=worker, daemon=True).start()
    return cache.get(ip, "查询中")


def client_ip():
    return (request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or request.remote_addr or "")


def geo_short(geo):
    """归属地精简：只保留 国家 省 市，去掉冗长的运营商公司名"""
    if not geo:
        return geo
    parts = str(geo).split()
    return " ".join(parts[:3]) if len(parts) > 3 else str(geo)


def log_pageview(path=None):
    """记录一次页面访问（GET 且属于被跟踪页面）"""
    ip = client_ip()
    if _is_internal(ip):
        return  # 跳过健康检查等内网请求
    _append_jsonl(VISITS_FILE, {
        "time": datetime.now().isoformat(timespec="seconds"),
        "ip": ip,
        "geo": geo_lookup(ip),
        "path": path or request.path,
        "ua": request.headers.get("User-Agent", "")[:200],
        "referer": request.headers.get("Referer", "")[:200],
    })


def log_beat(body):
    """记录前端心跳：sid 会话标识，event 为 enter/beat/leave"""
    ip = client_ip()
    _append_jsonl(BEATS_FILE, {
        "time": datetime.now().isoformat(timespec="seconds"),
        "ip": ip,
        "geo": geo_lookup(ip),
        "sid": str(body.get("sid", ""))[:64],
        "event": str(body.get("event", "beat"))[:16],
        "path": str(body.get("path", ""))[:128],
        "user_id": str(body.get("user_id", ""))[:64],
    })


# 扫描器/爬虫 UA 特征：直接不记录（它们不执行 JS，对统计没意义）
_BOT_UA = re.compile(
    r"bot|spider|crawl|scan|python|curl/|wget/|okhttp|go-http|axios|node-|"
    r"headless|phantom|zgrab|masscan|nmap|httpie|libwww|java/|censys|shodan",
    re.I,
)


def should_track(path, method):
    if not (method == "GET" and path in _TRACKED_PAGES):
        return False
    ua = request.headers.get("User-Agent", "")
    if not ua or _BOT_UA.search(ua):
        return False
    return True
