# -*- coding: utf-8 -*-
"""可灵(Kling)开放平台 API 客户端：提交任务、轮询、下载。"""
import os
import time

import requests

from config import API_KEY, BASE_URL

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}


def _post(path, payload):
    r = requests.post(BASE_URL + path, json=payload, headers=HEADERS, timeout=60)
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        raise RuntimeError(f"API错误: {data}")
    return data["data"]


def _get(path):
    r = requests.get(BASE_URL + path, headers=HEADERS, timeout=60)
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        raise RuntimeError(f"API错误: {data}")
    return data["data"]


def create_text2image(prompt, model="kling-v2-1", aspect_ratio="16:9", n=1):
    payload = {
        "model_name": model,
        "prompt": prompt,
        "n": n,
        "aspect_ratio": aspect_ratio,
    }
    return _post("/v1/images/generations", payload)


def get_image_task(task_id):
    return _get(f"/v1/images/generations/{task_id}")


def create_image2video(image_b64, prompt, model="kling-v1-6", duration="5",
                       mode="std", negative_prompt=None):
    payload = {
        "model_name": model,
        "image": image_b64,
        "prompt": prompt,
        "duration": duration,
        "mode": mode,
    }
    if negative_prompt:
        payload["negative_prompt"] = negative_prompt
    return _post("/v1/videos/image2video", payload)


def create_text2video(prompt, model="kling-v3", duration="5", mode="std",
                      aspect_ratio="16:9", negative_prompt=None):
    payload = {
        "model_name": model,
        "prompt": prompt,
        "duration": duration,
        "mode": mode,
        "aspect_ratio": aspect_ratio,
    }
    if negative_prompt:
        payload["negative_prompt"] = negative_prompt
    return _post("/v1/videos/text2video", payload)


def get_video_task(task_id, kind="image2video"):
    return _get(f"/v1/videos/{kind}/{task_id}")


def wait_task(get_fn, task_id, interval=15, timeout=1800, label=""):
    """轮询任务直到完成，返回任务数据。"""
    t0 = time.time()
    while True:
        data = get_fn(task_id)
        status = data.get("task_status")
        print(f"[{label or task_id}] 状态: {status} ({int(time.time()-t0)}s)")
        if status == "succeed":
            return data
        if status == "failed":
            raise RuntimeError(f"任务失败: {data.get('task_status_msg')}")
        if time.time() - t0 > timeout:
            raise TimeoutError(f"任务超时: {task_id}")
        time.sleep(interval)


def download(url, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    return path
