# -*- coding: utf-8 -*-
"""样片素材生成：定妆图 -> 图生视频三镜头。
用法:
  python 01_生成素材.py image    # 第一步：生成主角定妆图
  python 01_生成素材.py submit   # 第二步：提交三个图生视频任务
  python 01_生成素材.py poll     # 第三步：轮询并下载视频片段
"""
import base64
import json
import os
import sys

import kling_api as K

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "素材")
os.makedirs(ASSETS, exist_ok=True)

with open(os.path.join(HERE, "分镜样片.json"), encoding="utf-8") as f:
    BOARD = json.load(f)

STATE = os.path.join(ASSETS, "tasks.json")


def load_state():
    if os.path.exists(STATE):
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(s):
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)


def step_image():
    resp = K.create_text2image(BOARD["character_image_prompt"])
    print("图片任务已提交:", resp)
    data = K.wait_task(K.get_image_task, resp["task_id"], interval=10, label="定妆图")
    results = data["task_result"]["images"]
    path = os.path.join(ASSETS, "主角定妆图.png")
    K.download(results[0]["url"], path)
    print("定妆图已保存:", path)


CHARACTER = "25岁中国男性青年，短发，面容坚毅，身穿深灰色现代户外冲锋衣，背负迷彩色登山背包"
NEG = "低画质, 变形, 多余手指, 模糊, 水印"


def step_submit():
    """文生视频（试用资源包不含图片生成，故走 text2video，
    每个镜头提示词内嵌角色描述以保持人物一致性）。"""
    state = load_state()
    for shot in BOARD["shots"]:
        out = os.path.join(ASSETS, f"{shot['id']}.mp4")
        if os.path.exists(out):
            print(shot["id"], "已有成片，跳过（如需重生成请先删除对应 mp4）")
            continue
        resp = K.create_text2video(
            f"{shot['prompt']}。主角特征：{CHARACTER}",
            duration=str(shot["duration"]), mode="std",
            negative_prompt=NEG,
        )
        state[shot["id"]] = resp["task_id"]
        print(shot["id"], "->", resp["task_id"])
    save_state(state)


def step_poll():
    state = load_state()
    for shot in BOARD["shots"]:
        tid = state.get(shot["id"])
        out = os.path.join(ASSETS, f"{shot['id']}.mp4")
        if not tid or os.path.exists(out):
            continue
        data = K.wait_task(lambda t: K.get_video_task(t, "text2video"), tid,
                           interval=20, label=shot["id"])
        url = data["task_result"]["videos"][0]["url"]
        K.download(url, out)
        print(shot["id"], "已下载:", out)


if __name__ == "__main__":
    {"image": step_image, "submit": step_submit, "poll": step_poll}[sys.argv[1]]()
