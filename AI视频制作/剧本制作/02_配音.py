# -*- coding: utf-8 -*-
"""旁白配音：edge-tts 逐镜头生成 MP3。"""
import asyncio
import json
import os

import edge_tts

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "素材")
os.makedirs(ASSETS, exist_ok=True)

with open(os.path.join(HERE, "分镜样片.json"), encoding="utf-8") as f:
    BOARD = json.load(f)

VOICE = "zh-CN-YunjianNeural"  # 浑厚男声，适合历史题材旁白
RATE = "-8%"


async def main():
    for shot in BOARD["shots"]:
        out = os.path.join(ASSETS, f"{shot['id']}_旁白.mp3")
        tts = edge_tts.Communicate(shot["narration"], VOICE, rate=RATE)
        await tts.save(out)
        print("已生成:", out)


if __name__ == "__main__":
    asyncio.run(main())
