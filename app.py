"""
口语练习系统
一个基于 Flask + 浏览器 Web Speech API 的口语练习工具。
支持：AI 情景对话、话题独白、影子跟读、每日表达。
"""

import json
import os
import random
from datetime import datetime
from pathlib import Path

import requests
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"


def load_json(filename):
    with open(DATA_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/random-topic")
def random_topic():
    data = load_json("topics.json")
    topic = random.choice(data["topics"])
    return jsonify(topic)


@app.route("/api/random-expression")
def random_expression():
    data = load_json("topics.json")
    expr = random.choice(data["expressions"])
    return jsonify(expr)


@app.route("/api/random-shadow")
def random_shadow():
    data = load_json("topics.json")
    shadow = random.choice(data["shadowing"])
    return jsonify(shadow)


@app.route("/api/chat", methods=["POST"])
def chat():
    """
    代理到用户配置的 OpenAI 兼容接口。
    请求体：{messages: [...], model?: ..., stream?: false}
    环境变量：OPENAI_API_KEY, OPENAI_BASE_URL（可选）
    """
    body = request.get_json(silent=True) or {}
    messages = body.get("messages", [])
    if not messages:
        return jsonify({"error": "messages is required"}), 400

    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")

    if not api_key:
        return jsonify({"error": "未配置 OPENAI_API_KEY，请在 start.bat 中设置后重启。"}), 401

    model = body.get("model") or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "temperature": 0.8,
    }

    try:
        resp = requests.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        return jsonify(resp.json())
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"请求失败：{str(e)}"}), 502


@app.route("/api/save-history", methods=["POST"])
def save_history():
    """保存练习记录到本地 history.jsonl"""
    body = request.get_json(silent=True) or {}
    record = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "mode": body.get("mode", "unknown"),
        "content": body.get("content", ""),
    }
    history_file = DATA_DIR / "history.jsonl"
    with open(history_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return jsonify({"ok": True})


@app.route("/api/history")
def get_history():
    history_file = DATA_DIR / "history.jsonl"
    if not history_file.exists():
        return jsonify([])
    records = []
    with open(history_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return jsonify(records[-50:])


if __name__ == "__main__":
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("FLASK_PORT", "5000"))
    app.run(host=host, port=port, debug=False)
