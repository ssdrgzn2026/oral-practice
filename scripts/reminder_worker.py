# -*- coding: utf-8 -*-
"""
票务提醒推送 worker：每 20 秒检查一次订阅
- 医院放号提醒：每天放号时间前 2 分钟推送
- 演出开票提醒：开票时间前 2 分钟推送（一次性）
推送渠道：Server酱（微信）
"""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

REMINDER_DIR = Path(os.environ.get("MISC_REMINDER_DIR", str(Path(__file__).resolve().parent.parent / "reminder-data")))
SUBS_FILE = REMINDER_DIR / "subscriptions.json"
REMIND_AHEAD = timedelta(minutes=2)


def load_subs():
    if not SUBS_FILE.exists():
        return []
    try:
        return json.loads(SUBS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def save_subs(subs):
    SUBS_FILE.write_text(json.dumps(subs, ensure_ascii=False, indent=1), encoding="utf-8")


def push(sendkey, title, desp):
    try:
        r = requests.post(
            f"https://sctapi.ftqq.com/{sendkey}.send",
            data={"title": title, "desp": desp},
            timeout=10,
        )
        ok = r.json().get("code") == 0
        print(f"[push] {'ok' if ok else 'fail'} {title}", flush=True)
        return ok
    except Exception as e:
        print(f"[push] error {e}", flush=True)
        return False


def main():
    print("reminder worker started", flush=True)
    while True:
        now = datetime.now()
        subs = load_subs()
        changed = False

        for s in subs:
            if s.get("kind") == "hospital":
                try:
                    hh, mm = s["release_time"].split(":")
                except (KeyError, ValueError):
                    continue
                fire_at = now.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0) - REMIND_AHEAD
                today = now.strftime("%Y-%m-%d")
                if fire_at <= now < fire_at + timedelta(seconds=40) and s.get("last_fired") != today:
                    doctor = f" {s['doctor']}" if s.get("doctor") else ""
                    ok = push(
                        s["sendkey"],
                        f"⏰ 放号提醒：{s['hospital']}{doctor}",
                        f"{s['hospital']} 将在 **{s['release_time']}** 放号（还剩约 2 分钟）。\n\n"
                        f"请立即打开 114 预约挂号：https://www.114yygh.com\n\n祝挂号顺利！",
                    )
                    if ok:
                        s["last_fired"] = today
                        changed = True

            elif s.get("kind") == "event" and not s.get("fired"):
                try:
                    event_at = datetime.fromisoformat(s["event_time"])
                except (KeyError, ValueError):
                    continue
                fire_at = event_at - REMIND_AHEAD
                if fire_at <= now < fire_at + timedelta(seconds=40):
                    link = f"\n\n购票链接：{s['link']}" if s.get("link") else ""
                    ok = push(
                        s["sendkey"],
                        f"🎫 开票提醒：{s['title']}",
                        f"**{s['title']}** 将在 **{s['event_time'].replace('T', ' ')}** 开票（还剩约 2 分钟）。"
                        f"{link}\n\n祝抢票顺利！",
                    )
                    if ok:
                        s["fired"] = True
                        changed = True

        if changed:
            save_subs(subs)
        time.sleep(20)


if __name__ == "__main__":
    main()
