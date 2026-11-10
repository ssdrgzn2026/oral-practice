# -*- coding: utf-8 -*-
"""ComfyUI API 客户端：上传参考脸 + 提交 PuLID 工作流 + 取回图片。
前提：AutoDL SSH 隧道已开（本地 6006 -> 云端 ComfyUI）。"""
import json
import os
import time
import uuid

import requests

BASE = os.environ.get("COMFYUI_BASE", "http://127.0.0.1:6006")
HERE = os.path.dirname(os.path.abspath(__file__))
WORKFLOW_PATH = os.path.join(HERE, "PuLID_simple (1).json")

# 工作流里各节点的编号（来自导出的 API JSON）
NODE_PROMPT = "22"      # 正面提示词
NODE_NEGATIVE = "23"    # 负面提示词
NODE_IMAGE = "12"       # 参考脸图片
NODE_SEED = "3"         # K采样器
NODE_SIZE = "5"         # 空Latent（宽高）


def upload_image(img_path):
    """上传参考图到 ComfyUI，返回服务器上的文件名。"""
    with open(img_path, "rb") as f:
        r = requests.post(f"{BASE}/upload/image",
                          files={"image": (os.path.basename(img_path), f)},
                          timeout=120)
    r.raise_for_status()
    return r.json()["name"]


def generate(prompt, ref_image, negative=None, seed=None, width=768, height=1024,
             timeout=300):
    """提交一次锁脸出图，返回图片字节。ref_image 可以是本地路径或已上传的文件名。"""
    with open(WORKFLOW_PATH, encoding="utf-8") as f:
        wf = json.load(f)

    if os.path.exists(str(ref_image)):
        ref_image = upload_image(ref_image)
    wf[NODE_IMAGE]["inputs"]["image"] = ref_image
    wf[NODE_PROMPT]["inputs"]["text"] = prompt
    if negative is not None:
        wf[NODE_NEGATIVE]["inputs"]["text"] = negative
    if seed is not None:
        wf[NODE_SEED]["inputs"]["seed"] = seed
    wf[NODE_SIZE]["inputs"]["width"] = width
    wf[NODE_SIZE]["inputs"]["height"] = height

    r = requests.post(f"{BASE}/prompt", json={"prompt": wf,
                                              "client_id": str(uuid.uuid4())},
                      timeout=60)
    r.raise_for_status()
    prompt_id = r.json()["prompt_id"]

    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(3)
        h = requests.get(f"{BASE}/history/{prompt_id}", timeout=30).json()
        if prompt_id not in h:
            continue
        outputs = h[prompt_id].get("outputs", {})
        for node_out in outputs.values():
            imgs = node_out.get("images", [])
            if imgs:
                img = imgs[0]
                r = requests.get(f"{BASE}/view", params={
                    "filename": img["filename"],
                    "subfolder": img.get("subfolder", ""),
                    "type": img.get("type", "temp"),
                }, timeout=120)
                r.raise_for_status()
                return r.content
        status = h[prompt_id].get("status", {})
        if status.get("completed") is False and status.get("status_str") == "error":
            raise RuntimeError(f"ComfyUI 执行出错: {status}")
    raise TimeoutError("ComfyUI 出图超时")


if __name__ == "__main__":
    # 测试：从 ComfyUI output 里拿林策参考图当脸，生成一张新场景
    import sys
    ref = sys.argv[1] if len(sys.argv) > 1 else None
    prompt = ("cinematic photo of the same young man walking through a bustling "
              "Song dynasty night market, lanterns, crowd, movie quality")
    img = generate(prompt, ref or "ComfyUI_00002_.png", seed=int(time.time()))
    out = os.path.join(HERE, "素材", f"comfyui_test_{int(time.time())}.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "wb") as f:
        f.write(img)
    print("已保存:", out)
