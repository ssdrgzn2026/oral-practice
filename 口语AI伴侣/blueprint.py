# -*- coding: utf-8 -*-
"""
口语AI伴侣模块（Flask Blueprint）
支持：AI 情景对话、话题独白、影子跟读、每日表达、雅思口语、练习记录。
"""

import json
import os
import random
from datetime import datetime
from pathlib import Path

import requests
from flask import Blueprint, Response, jsonify, render_template, request, stream_with_context

oral_bp = Blueprint(
    "oral",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/oral-static",
)

DATA_DIR = Path(__file__).parent / "data"


def load_json(filename):
    with open(DATA_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)


@oral_bp.route("/oral")
def oral():
    return render_template("oral.html")


@oral_bp.route("/api/random-topic")
def random_topic():
    data = load_json("topics.json")
    topic = random.choice(data["topics"])
    return jsonify(topic)


@oral_bp.route("/api/random-expression")
def random_expression():
    data = load_json("topics.json")
    expr = random.choice(data["expressions"])
    return jsonify(expr)


@oral_bp.route("/api/random-shadow")
def random_shadow():
    data = load_json("topics.json")
    shadow = random.choice(data["shadowing"])
    return jsonify(shadow)


@oral_bp.route("/api/chat", methods=["POST"])
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
    stream = body.get("stream", False)
    payload = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "temperature": 0.8,
        "max_tokens": 120,
    }

    try:
        resp = requests.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            stream=stream,
            timeout=60,
        )
        resp.raise_for_status()

        if stream:
            def generate():
                for line in resp.iter_lines():
                    if line:
                        yield line + b"\n\n"

            return Response(
                stream_with_context(generate()),
                mimetype="text/event-stream",
                headers={"X-Accel-Buffering": "no"},
            )

        return jsonify(resp.json())
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"请求失败：{str(e)}"}), 502


@oral_bp.route("/api/transcribe", methods=["POST"])
def transcribe():
    """
    接收上传的音频文件，调用 OpenAI 兼容接口的 Whisper 进行转写。
    需要配置 OPENAI_API_KEY。
    """
    if "audio" not in request.files:
        return jsonify({"error": "未收到音频文件"}), 400

    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    if not api_key:
        return jsonify({"error": "未配置 OPENAI_API_KEY，无法使用语音转写。"}), 401

    audio_file = request.files["audio"]
    whisper_model = os.environ.get("OPENAI_WHISPER_MODEL", "")
    chat_model = os.environ.get("OPENAI_MODEL", "")
    # 转写模型不能 fallback 到聊天模型，否则 SiliconFlow 会报 403
    model = (
        request.form.get("model")
        or whisper_model
        or "FunAudioLLM/SenseVoiceSmall"
    )

    try:
        resp = requests.post(
            f"{base_url}/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            files={
                "file": (
                    audio_file.filename or "audio.webm",
                    audio_file.stream,
                    audio_file.content_type or "audio/webm",
                )
            },
            data={"model": model, "language": "en"},
            timeout=60,
        )
        resp.raise_for_status()
        return jsonify(resp.json())
    except requests.exceptions.RequestException as e:
        return jsonify({
            "error": f"转写请求失败：{str(e)}",
            "model": model,
        }), 502


@oral_bp.route("/api/save-history", methods=["POST"])
def save_history():
    """保存练习记录到本地 history.jsonl，按 user_id 隔离"""
    body = request.get_json(silent=True) or {}
    record = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "mode": body.get("mode", "unknown"),
        "content": body.get("content", ""),
        "user_id": body.get("user_id", ""),
    }
    history_file = DATA_DIR / "history.jsonl"
    with open(history_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return jsonify({"ok": True})


@oral_bp.route("/api/history")
def get_history():
    user_id = request.args.get("user_id", "")
    history_file = DATA_DIR / "history.jsonl"
    if not history_file.exists():
        return jsonify([])
    records = []
    with open(history_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rec = json.loads(line)
                if user_id and rec.get("user_id") == user_id:
                    records.append(rec)
    return jsonify(records[-50:])


@oral_bp.route("/api/clear-history", methods=["POST"])
def clear_history():
    """按 user_id 删除该用户的练习记录"""
    body = request.get_json(silent=True) or {}
    user_id = body.get("user_id", "")
    history_file = DATA_DIR / "history.jsonl"
    if not history_file.exists() or not user_id:
        return jsonify({"ok": True})
    with open(history_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    kept = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            if json.loads(stripped).get("user_id") != user_id:
                kept.append(line)
        except json.JSONDecodeError:
            kept.append(line)
    with open(history_file, "w", encoding="utf-8") as f:
        f.writelines(kept)
    return jsonify({"ok": True})
