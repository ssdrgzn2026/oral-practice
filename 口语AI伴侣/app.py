# -*- coding: utf-8 -*-
"""口语AI伴侣独立服务入口（独立容器，gunicorn 启动，监听 0.0.0.0:8504）

目录名为中文不能作为包导入，沿用主站做法：按文件路径加载 blueprint.py。
生产环境由 nginx 将 /oral 及 /api/*（口语相关）反代到本服务。
"""
import importlib.util
import os
import sys
from pathlib import Path

from flask import Flask

BASE_DIR = Path(__file__).resolve().parent

_bp_path = BASE_DIR / "blueprint.py"
_spec = importlib.util.spec_from_file_location("oral_blueprint", _bp_path)
_module = importlib.util.module_from_spec(_spec)
sys.modules["oral_blueprint"] = _module  # 让 Flask 能定位 Blueprint 的资源目录
_spec.loader.exec_module(_module)

app = Flask(__name__)
app.register_blueprint(_module.oral_bp)


@app.route("/oral/healthz")
def healthz():
    return "ok", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("ORAL_PORT", "8504")))
