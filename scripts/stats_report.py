# -*- coding: utf-8 -*-
"""
访客统计报表：读取 stats/visits.jsonl 与 stats/beats.jsonl，输出每位访客的时间、
IP、归属地、访问页面、停留时长等汇总信息。

用法（本地或服务器上均可，数据文件在 stats/ 目录）：
    python scripts/stats_report.py            # 按访客汇总（按最近访问时间排序）
    python scripts/stats_report.py --beats    # 查看原始心跳明细
"""

import argparse
import json
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # Windows 控制台中文正常显示

STATS_DIR = Path(__file__).resolve().parent.parent / "stats"

BAD_GEO = (None, "", "查询中", "未知")


def read_jsonl(path):
    if not path.exists():
        return []
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return rows


def parse_time(s):
    try:
        return datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def fmt_duration(seconds):
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}秒"
    if seconds < 3600:
        return f"{seconds // 60}分{seconds % 60}秒"
    return f"{seconds // 3600}时{(seconds % 3600) // 60}分"


def disp_width(s):
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in s)


def geo_short(geo):
    """归属地精简：中国留'省 市'，国外留'国家 城市'，去掉冗长运营商名"""
    if not geo:
        return "-"
    parts = str(geo).split()
    if not parts:
        return "-"
    if parts[0] == "中国":
        return " ".join(parts[1:3]) if len(parts) > 1 else parts[0]
    # 国外：国家 + 城市（第3段），无城市则国家+省
    if len(parts) >= 3:
        return f"{parts[0]} {parts[2]}"
    return " ".join(parts[:2])


CARRIERS = [
    (("telecom", "china networks"), "电信"),
    (("mobile",), "移动"),
    (("unicom", "china169"), "联通"),
    (("alibaba", "aliyun"), "阿里云"),
    (("tencent",), "腾讯云"),
    (("huawei",), "华为云"),
    (("google",), "谷歌云"),
    (("amazon",), "亚马逊云"),
    (("microsoft",), "微软云"),
    (("akamai",), "Akamai"),
    (("digitalocean",), "DigitalOcean"),
    (("ucloud",), "UCloud"),
    (("huashu",), "华数"),
]


def carrier_of(geo):
    """从归属地字符串的 ISP 部分识别运营商"""
    if not geo:
        return "-"
    parts = str(geo).split()
    isp = " ".join(parts[3:]).lower() if len(parts) > 3 else ""
    if not isp:
        return "-"
    for keys, name in CARRIERS:
        if any(k in isp for k in keys):
            return name
    return parts[3][:12]  # 其他给第一段简称


PATH_NAMES = {
    "/": "首页",
    "/oral": "口语",
    "/tickets": "票务",
    "/portal": "网站导航",
    "/convert/": "格式转换",
    "/dcf/": "DCF",
}


def page_names(paths):
    return "、".join(PATH_NAMES.get(p, p) for p in sorted(paths) if p)


def pad(s, width):
    """按显示宽度对齐（中文算 2 格），超长的截断加省略号，解决中英文混排错位"""
    s = str(s)
    w = disp_width(s)
    if w > width:
        out, cur = [], 0
        for c in s:
            cw = 2 if unicodedata.east_asian_width(c) in ("W", "F") else 1
            if cur + cw > width - 1:
                break
            out.append(c)
            cur += cw
        s = "".join(out) + "…"
        w = cur + 1
    return s + " " * max(0, width - w)


def fill_geo(rows, cache):
    """用缓存补全归属地；缓存也没有的，现场联网查询一次并写回缓存"""
    need_lookup = set()
    for row in rows:
        if row.get("geo") in BAD_GEO:
            ip = row.get("ip", "")
            if cache.get(ip) and cache[ip] not in BAD_GEO:
                row["geo"] = cache[ip]
            elif ip:
                need_lookup.add(ip)
    if not need_lookup:
        return
    import urllib.request
    for ip in sorted(need_lookup):
        try:
            req = urllib.request.Request(f"https://ipwho.is/{ip}?lang=zh-CN",
                                         headers={"User-Agent": "curl/8"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                d = json.loads(resp.read().decode("utf-8"))
            if d.get("success"):
                isp = (d.get("connection") or {}).get("isp", "")
                loc = " ".join(x for x in [d.get("country"), d.get("region"), d.get("city"), isp] if x)
                cache[ip] = loc or "未知"
        except Exception:
            continue
    for row in rows:
        if row.get("geo") in BAD_GEO and cache.get(row.get("ip")) not in BAD_GEO:
            row["geo"] = cache.get(row.get("ip"), row.get("geo"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--beats", action="store_true", help="输出原始心跳明细")
    args = ap.parse_args()

    visits = read_jsonl(STATS_DIR / "visits.jsonl")
    beats = read_jsonl(STATS_DIR / "beats.jsonl")

    cache_file = STATS_DIR / "ip_cache.json"
    ip_cache = {}
    if cache_file.exists():
        try:
            ip_cache = json.loads(cache_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    fill_geo(visits + beats, ip_cache)
    try:
        cache_file.write_text(json.dumps(ip_cache, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass

    if args.beats:
        for b in beats:
            print(f"{b.get('time')}  {pad(b.get('ip'), 16)} {pad(b.get('geo', ''), 20)} {pad(b.get('event'), 6)} {b.get('path')}")
        print(f"\n共 {len(beats)} 条心跳")
        return

    # 按 sid 聚合心跳，计算每次会话的停留时长
    sessions = defaultdict(list)
    for b in beats:
        t = parse_time(b.get("time"))
        if b.get("sid") and t:
            sessions[b["sid"]].append((t, b))

    session_info = {}
    for sid, items in sessions.items():
        items.sort(key=lambda x: x[0])
        first, last = items[0], items[-1]
        meta = last[1]
        # 时长按心跳累加：相邻心跳间隔超过 60 秒视为离开（PWA 常驻后台会虚高）
        duration = 0.0
        for i in range(1, len(items)):
            gap = (items[i][0] - items[i - 1][0]).total_seconds()
            if gap <= 60:
                duration += gap
        session_info[sid] = {
            "start": first[0],
            "end": last[0],
            "duration": duration,
            "ip": meta.get("ip", ""),
            "geo": meta.get("geo", ""),
            "user_id": meta.get("user_id", ""),
            "paths": sorted({i[1].get("path", "") for i in items}),
        }

    # 按 IP 汇总
    visitors = defaultdict(lambda: {"geo": "", "visits": 0, "pages": set(),
                                    "first": None, "last": None, "total_sec": 0,
                                    "user_ids": set(), "sessions": 0})
    for v in visits:
        ip = v.get("ip", "")
        t = parse_time(v.get("time"))
        d = visitors[ip]
        g = v.get("geo")
        if g not in BAD_GEO:
            d["geo"] = g
        d["visits"] += 1
        d["pages"].add(v.get("path", ""))
        if t:
            d["first"] = t if d["first"] is None or t < d["first"] else d["first"]
            d["last"] = t if d["last"] is None or t > d["last"] else d["last"]

    for s in session_info.values():
        d = visitors[s["ip"]]
        if s["geo"] not in BAD_GEO and not d["geo"]:
            d["geo"] = s["geo"]
        d["sessions"] += 1
        d["total_sec"] += s["duration"]
        # 只有心跳没有页面访问记录时，用的心跳时间补上首末时间
        if d["first"] is None or s["start"] < d["first"]:
            d["first"] = s["start"]
        if d["last"] is None or s["end"] > d["last"]:
            d["last"] = s["end"]
        if s["user_id"]:
            d["user_ids"].add(s["user_id"])
        d["pages"] |= set(s["paths"])

    print(pad("首次访问", 13) + pad("最近访问", 13) + pad("IP", 17) + pad("归属地", 14) + pad("运营商", 8) + pad("类型", 9)
          + pad("浏览", 5) + pad("会话", 5) + pad("总停留", 10) + "访问过的页面")
    print("-" * 118)
    # 按最近访问时间倒序
    rows = sorted(visitors.items(),
                  key=lambda kv: kv[1]["last"] or datetime.min, reverse=True)
    for ip, d in rows:
        kind = "真人" if d["sessions"] > 0 else "扫描/爬虫"
        print(pad(d["first"].strftime("%m-%d %H:%M") if d["first"] else "-", 13)
              + pad(d["last"].strftime("%m-%d %H:%M") if d["last"] else "-", 13)
              + pad(ip, 17)
              + pad(geo_short(d["geo"]), 14)
              + pad(carrier_of(d["geo"]), 8)
              + pad(kind, 9)
              + pad(d["visits"], 5)
              + pad(d["sessions"], 5)
              + pad(fmt_duration(d["total_sec"]), 10)
              + page_names(d["pages"]))
    real = sum(1 for d in visitors.values() if d["sessions"] > 0)
    print(f"\n共 {len(visitors)} 个独立 IP（真人 {real} 个，扫描/爬虫 {len(visitors) - real} 个），"
          f"{len(visits)} 次页面浏览，{len(session_info)} 个会话")

    # 各模块访问量汇总（按页面路径统计）
    page_counts = defaultdict(int)
    for v in visits:
        page_counts[v.get("path", "")] += 1
    if page_counts:
        print("\n各模块访问量：")
        for p, n in sorted(page_counts.items(), key=lambda kv: kv[1], reverse=True):
            print(f"  {PATH_NAMES.get(p, p)}：{n} 次")


if __name__ == "__main__":
    main()
