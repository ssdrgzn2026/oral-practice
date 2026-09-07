# -*- coding: utf-8 -*-
"""
MiscHub｜杂具小栈 —— 一站式零散工具工作台
模块：
- /         工具导航首页
- /oral     口语AI伴侣（Flask Blueprint，见 口语AI伴侣/blueprint.py）
- /convert/ 格式转换系统（独立 Streamlit 服务，由 nginx 反代；本地开发时跳转 8501 端口）
- /dcf/     DCF 估值工具（独立 Streamlit 服务，由 nginx 反代；本地开发时跳转 8502 端口）
"""

import importlib.util
import os
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request
from flask_cors import CORS

import stats_logger

BASE_DIR = Path(__file__).parent

app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

# 加载口语AI伴侣 Blueprint（目录名为中文，不能作为包导入，按文件路径加载）
import sys

_bp_path = BASE_DIR / "口语AI伴侣" / "blueprint.py"
_spec = importlib.util.spec_from_file_location("oral_blueprint", _bp_path)
_module = importlib.util.module_from_spec(_spec)
sys.modules["oral_blueprint"] = _module  # 让 Flask 能定位 Blueprint 的资源目录
_spec.loader.exec_module(_module)
app.register_blueprint(_module.oral_bp)


@app.before_request
def track_pageview():
    if stats_logger.should_track(request.path, request.method):
        stats_logger.log_pageview()


@app.route("/api/visit-beat", methods=["POST"])
def visit_beat():
    stats_logger.log_beat(request.get_json(silent=True) or {})
    return jsonify({"ok": True})


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/convert")
@app.route("/convert/")
def convert():
    # 生产环境由 nginx 将 /convert/ 反代到 Streamlit（8501），不会走到这里
    return redirect("http://127.0.0.1:8501/")


@app.route("/dcf")
@app.route("/dcf/")
def dcf():
    # 生产环境由 nginx 将 /dcf/ 反代到 Streamlit（8502），不会走到这里
    return redirect("http://127.0.0.1:8502/")


if __name__ == "__main__":
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("FLASK_PORT", "5000"))
    app.run(host=host, port=port, debug=False)
