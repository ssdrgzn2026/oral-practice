#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AutoDL 无人值守看门狗（阿里云 cron 每 5 分钟跑一次）：
三个条件同时满足才关机：
  1. 距最后一次 GPU 活动（杂具小栈心跳文件）超过 IDLE_MIN 分钟
  2. ComfyUI 队列空（或隧道离线，说明没活）
  3. 没有 LoRA 训练进程在跑（ssh 查进程）
环境变量来自 /opt/oral-practice/.env：AUTODL_TOKEN / AUTODL_INSTANCE / AUTODL_SSH_TARGET
"""
import os
import subprocess
import sys
import time

import requests

ENV_CANDIDATES = ["/app/.env", "/opt/oral-practice/.env"]
HEARTBEAT_CANDIDATES = ["/app/AI视频制作/data/video_cache/autodl_heartbeat",
                        "/opt/oral-practice/AI视频制作/data/video_cache/autodl_heartbeat"]
IDLE_MIN = int(os.environ.get("AUTODL_IDLE_MIN", "45"))


def load_env():
    for env_file in ENV_CANDIDATES:
        try:
            for line in open(env_file, encoding="utf-8"):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
            return
        except OSError:
            continue


def heartbeat_mtime() -> float:
    for p in HEARTBEAT_CANDIDATES:
        try:
            return os.path.getmtime(p)
        except OSError:
            continue
    return 0.0


def log(msg):
    print(time.strftime("[%F %T]"), msg, flush=True)


def main():
    load_env()
    token = os.environ.get("AUTODL_TOKEN", "")
    inst = os.environ.get("AUTODL_INSTANCE", "")
    ssh_target = os.environ.get("AUTODL_SSH_TARGET", "")
    if not (token and inst and ssh_target):
        log("未配置 AUTODL_TOKEN/INSTANCE/SSH_TARGET，跳过")
        return

    # 条件1：心跳静默超时
    hb = heartbeat_mtime()
    idle = time.time() - hb if hb else 1e9  # 从未有心跳
    if idle < IDLE_MIN * 60:
        log(f"心跳活跃（{idle/60:.0f} 分钟前有活动），不关机")
        return

    # 条件2：ComfyUI 队列（隧道在线时）
    comfy_base = os.environ.get("COMFYUI_BASE", "http://127.0.0.1:6006").rstrip("/")
    try:
        q = requests.get(f"{comfy_base}/queue", timeout=5).json()
        busy = len(q.get("queue_running", [])) + len(q.get("queue_pending", []))
        if busy:
            log(f"ComfyUI 有 {busy} 个任务在跑，不关机")
            return
    except Exception:
        pass  # 离线视为无任务，继续判断

    # 条件3：训练进程（注意：用 ps+grep 且排除 grep 自身；pgrep -f 会匹配命令行里
    # 含同样字符串的 ssh 临时 shell，造成"永远有训练"的误判）
    r = subprocess.run(
        f"ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=8 {ssh_target} "
        "'ps aux | grep sdxl_train_network | grep -v grep | wc -l'",
        shell=True, capture_output=True, text=True, timeout=30)
    n_train = (r.stdout.strip() or "0")
    if r.returncode == 0 and n_train not in ("0", ""):
        log(f"有 LoRA 训练在跑（{n_train} 个进程），不关机")
        return

    # 关机：普通容器实例走实例内 shutdown（等效控制台关机，停止计费）；
    # Pro 实例以后可换 API power_off
    log(f"闲置 {idle/60:.0f} 分钟且无任务，执行关机")
    r = subprocess.run(
        f"ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=8 {ssh_target} "
        "'shutdown -h now'",
        shell=True, capture_output=True, text=True, timeout=30)
    log(f"shutdown 已下发（ssh 返回 {r.returncode}，实例断电即断连属正常）")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        log(f"看门狗异常：{e}")
        sys.exit(0)  # 看门狗失败绝不报警，下次再说
