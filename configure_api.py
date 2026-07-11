#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""配置 AI 对话 API 信息，生成 config.bat"""

import os
import sys

print("=" * 50)
print("   配置 AI 对话 API")
print("=" * 50)
print()
print("支持任意 OpenAI 兼容接口，例如：")
print("  OpenAI:   https://api.openai.com/v1")
print("  Kimi:     https://api.moonshot.cn/v1")
print("  DeepSeek: https://api.deepseek.com/v1")
print()

key = input("请输入 API Key（不配置请直接回车）：").strip()
if not key:
    print("未输入 Key，取消配置。")
    sys.exit(0)

base = input("请输入 Base URL（直接回车使用默认 https://api.openai.com/v1）：").strip()
if not base:
    base = "https://api.openai.com/v1"

# 根据 base_url 给默认模型建议
if "moonshot" in base.lower():
    default_model = "moonshot-v1-8k"
elif "deepseek" in base.lower():
    default_model = "deepseek-chat"
else:
    default_model = "gpt-4o-mini"

model = input(f"请输入模型名称（直接回车使用默认 {default_model}）：").strip()
if not model:
    model = default_model

config_path = os.path.join(os.path.dirname(__file__), "config.bat")
content = f"""@echo off
REM 由 configure_api.py 自动生成，请勿手动修改编码
set OPENAI_API_KEY={key}
set OPENAI_BASE_URL={base}
set OPENAI_MODEL={model}
"""

with open(config_path, "w", encoding="gbk") as f:
    f.write(content)

print()
print(f"已保存到：{config_path}")
print("现在可以关闭此窗口，然后重新双击 start.bat 启动系统。")
print()
input("按回车退出...")
