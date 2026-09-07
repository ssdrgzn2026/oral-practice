# -*- coding: utf-8 -*-
"""
访客统计报表：读取 stats/visits.jsonl 与 stats/beats.jsonl，输出每位访客的时间、
IP、归属地、访问页面、停留时长等汇总信息。

用法（本地或服务器上均可，数据文件在 stats/ 目录）：
    python scripts/stats_report.py            # 按访客汇总
    python scripts/stats_report.py --beats    # 查看原始心跳明细
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # Windows 控制台中文正常显示

STATS_DIR = Path(__file__).resolve().parent.parent / "stats"


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--beats", action="store_true", help="输出原始心跳明细")
    args = ap.parse_args()

    visits = read_jsonl(STATS_DIR / "visits.jsonl")
    beats = read_jsonl(STATS_DIR / "beats.jsonl")

    if args.beats:
        for b in beats:
            print(f"{b.get('time')}  {b.get('ip'):<16} {b.get('geo',''):<14} {b.get('event'):<6} {b.get('path')}")
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
        duration = (last[0] - first[0]).total_seconds()
        meta = last[1]
        session_info[sid] = {
            "start": first[0],
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
        d["geo"] = v.get("geo") or d["geo"]
        d["visits"] += 1
        d["pages"].add(v.get("path", ""))
        if t:
            d["first"] = t if d["first"] is None or t < d["first"] else d["first"]
            d["last"] = t if d["last"] is None or t > d["last"] else d["last"]

    for s in session_info.values():
        d = visitors[s["ip"]]
        d["sessions"] += 1
        d["total_sec"] += s["duration"]
        if s["user_id"]:
            d["user_ids"].add(s["user_id"])
        d["pages"] |= set(s["paths"])

    print(f"{'IP':<16} {'归属地':<16} {'页面浏览':<6} {'会话':<4} {'总停留':<10} {'首次访问':<20} {'最近访问':<20} 页面")
    print("-" * 130)
    for ip, d in sorted(visitors.items(), key=lambda kv: kv[1]["visits"], reverse=True):
        print(f"{ip:<16} {d['geo']:<16} {d['visits']:<6} {d['sessions']:<4} "
              f"{fmt_duration(d['total_sec']):<10} "
              f"{d['first'].strftime('%Y-%m-%d %H:%M') if d['first'] else '-':<20} "
              f"{d['last'].strftime('%Y-%m-%d %H:%M') if d['last'] else '-':<20} "
              f"{','.join(sorted(d['pages']))}")
    print(f"\n共 {len(visitors)} 个独立 IP，{len(visits)} 次页面浏览，{len(session_info)} 个会话")


if __name__ == "__main__":
    main()
