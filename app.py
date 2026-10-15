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
import json
import os
import threading
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, send_from_directory
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


@app.route("/api/pv")
def pv_pixel():
    """Streamlit 模块（格式转换/DCF）的访问统计像素：页面加载时以 <img> 形式上报"""
    p = request.args.get("p", "")
    allowed = {"convert": "/convert/", "dcf": "/dcf/"}
    if p in allowed:
        ua = request.headers.get("User-Agent", "")
        if ua and not stats_logger._BOT_UA.search(ua):
            stats_logger.log_pageview(path=allowed[p])
    return ("", 204, {"Cache-Control": "no-store"})


@app.route("/api/visit-beat", methods=["POST"])
def visit_beat():
    stats_logger.log_beat(request.get_json(silent=True) or {})
    return jsonify({"ok": True})


@app.route("/manifest.json")
def manifest():
    if is_atlas_host():
        return jsonify({
            "name": "学科星图",
            "short_name": "学科星图",
            "description": "一站式学科知识图谱：下钻、演示、AI 导学、学科时间线",
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "background_color": "#f5f5f4",
            "theme_color": "#0b1026",
            "lang": "zh-CN",
            "icons": [
                {"src": "/static/img/atlas-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
                {"src": "/static/img/atlas-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            ],
        })
    return send_from_directory("static", "manifest.json")


@app.route("/sw.js")
def service_worker():
    # Service Worker 必须在根路径下提供，才能接管全站作用域
    return send_from_directory("static", "sw.js", mimetype="text/javascript")


@app.route("/files/<token>/<path:filename>")
def download_file(token, filename):
    """格式转换结果的暂存文件下载（强制附件下载，文件名保留中文）"""
    from flask import send_file

    download_dir = Path(os.environ.get("MISC_DOWNLOAD_DIR", str(BASE_DIR / "downloads")))
    # token 只允许十六进制，防目录穿越
    if not token.isalnum():
        return "invalid", 400
    matches = list(download_dir.glob(f"{token}.*"))
    if not matches:
        return "文件已过期或不存在，请重新转换", 404
    # ?raw=1 直接给文件；否则给中转下载页（iOS PWA 里直接下载会把页面顶掉）
    if request.args.get("raw") == "1":
        return send_file(matches[0], as_attachment=True, download_name=filename)
    from urllib.parse import quote
    return render_template("download.html", filename=filename,
                           raw_url=f"/files/{token}/{quote(filename)}?raw=1")


def is_atlas_host():
    """学科星图独立站点域名"""
    return request.host.split(":")[0] == "atlas.pingxu.xin"


@app.route("/")
def index():
    if is_atlas_host():
        return render_template("graphs.html", base="")
    return render_template("index.html")


# ========== 学科星图独立站点（atlas.pingxu.xin）==========
# 该域名下用短路径：/physics /star /physics?node=xx 等


@app.route("/star")
def atlas_star():
    if not is_atlas_host():
        return redirect("/graph/star")
    return render_template("star.html", base="")


@app.route("/<subject>")
def atlas_subject(subject):
    if not is_atlas_host():
        return redirect(f"/graph/{subject}")
    if subject not in GRAPH_SUBJECTS:
        return redirect("/")
    cfg = GRAPH_SUBJECTS[subject]
    return render_template("graph.html", subject=subject, base="", **cfg)


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


# ========== 票务提醒 ==========
REMINDER_DIR = Path(os.environ.get("MISC_REMINDER_DIR", str(BASE_DIR / "reminder-data")))
REMINDER_DIR.mkdir(exist_ok=True)
SUBS_FILE = REMINDER_DIR / "subscriptions.json"
_subs_lock = threading.Lock()


def _load_subs():
    with _subs_lock:
        if not SUBS_FILE.exists():
            return []
        try:
            return json.loads(SUBS_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []


def _save_subs(subs):
    with _subs_lock:
        SUBS_FILE.write_text(json.dumps(subs, ensure_ascii=False, indent=1), encoding="utf-8")


@app.route("/tickets")
def tickets():
    return render_template("tickets.html")


@app.route("/portal")
def portal():
    return render_template("portal.html")


# ========== 知识图谱（学科通用） ==========
GRAPH_SUBJECTS = {
    "physics": {"title": "物理", "icon": "⚛️", "prize": "物理学奖", "awardLabel": "相关诺贝尔奖", "awardDetail": "诺贝尔物理学奖"},
    "chemistry": {"title": "化学", "icon": "🧪", "prize": "化学奖", "awardLabel": "相关诺贝尔奖", "awardDetail": "诺贝尔化学奖"},
    "biology": {"title": "生物", "icon": "🧬", "prize": "生理学或医学奖", "awardLabel": "相关诺贝尔奖", "awardDetail": "诺贝尔生理学或医学奖"},
    "math": {"title": "数学", "icon": "📐", "prize": "奖项", "awardLabel": "菲尔兹奖与阿贝尔奖", "awardDetail": "菲尔兹奖或阿贝尔奖"},
    "cs": {"title": "计算机科学", "icon": "💻", "prize": "图灵奖", "awardLabel": "图灵奖", "awardDetail": "图灵奖"},
    "philosophy": {"title": "哲学", "icon": "💭", "prize": "", "awardLabel": "代表人物与著作", "awardDetail": "哲学代表人物与著作"},
    "astronomy": {"title": "天文学", "icon": "🔭", "prize": "物理学奖", "awardLabel": "相关诺贝尔奖（物理学）", "awardDetail": "诺贝尔物理学奖"},
    "geography": {"title": "地理与地质", "icon": "🌍", "prize": "", "awardLabel": "学科发展大事记", "awardDetail": "学科大事记"},
    "economics": {"title": "经济学", "icon": "💹", "prize": "经济学奖", "awardLabel": "诺贝尔经济学奖", "awardDetail": "诺贝尔经济学奖"},
    "medicine": {"title": "医学与药学", "icon": "🏥", "prize": "生理学或医学奖", "awardLabel": "相关诺贝尔奖", "awardDetail": "诺贝尔生理学或医学奖"},
    "history": {"title": "历史", "icon": "📜", "prize": "", "awardLabel": "历史大事记", "awardDetail": "历史大事记"},
    "law": {"title": "法学", "icon": "⚖️", "prize": "", "awardLabel": "法治里程碑", "awardDetail": "法治里程碑"},
    "engineering": {"title": "工程学", "icon": "⚙️", "prize": "", "awardLabel": "工程里程碑", "awardDetail": "工程里程碑"},
    "buddhism": {"title": "佛学", "icon": "🪷", "prize": "", "awardLabel": "佛学大事记", "awardDetail": "佛学大事记"},
    "psychology": {"title": "心理学", "icon": "🧠", "prize": "", "awardLabel": "心理学里程碑", "awardDetail": "心理学里程碑"},
}


@app.route("/graph")
def graph_home():
    return render_template("graphs.html", base="/graph")


@app.route("/graph/<subject>")
def graph_subject(subject):
    if subject not in GRAPH_SUBJECTS:
        return redirect("/graph")
    cfg = GRAPH_SUBJECTS[subject]
    return render_template("graph.html", subject=subject, base="/graph", **cfg)


@app.route("/physics")
def physics():
    # atlas 域名下 /physics 即学科页；oral 域名下兼容旧链接
    if is_atlas_host():
        cfg = GRAPH_SUBJECTS["physics"]
        return render_template("graph.html", subject="physics", base="", **cfg)
    return redirect("/graph/physics")


@app.route("/api/graph-map/<subject>")
def graph_map(subject):
    if subject not in GRAPH_SUBJECTS:
        return jsonify({"error": "未知学科"}), 404
    try:
        return jsonify(json.loads((BASE_DIR / "data" / f"{subject}_map.json").read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return jsonify({"error": "知识图谱数据缺失"}), 500


@app.route("/api/physics-map")
def physics_map():
    # 旧接口兼容
    return graph_map("physics")


@app.route("/graph/star")
def graph_star():
    return render_template("star.html", base="/graph")


@app.route("/api/graph-network")
def graph_network():
    """聚合全部学科为 节点+边 网络（树边 + related 跨学科关联）"""
    nodes = []
    links = []
    seen = set()
    for sub in GRAPH_SUBJECTS:
        try:
            data = json.loads((BASE_DIR / "data" / f"{sub}_map.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        def walk(node, parent_id, depth):
            nid = node.get("id")
            if nid and nid not in seen:
                seen.add(nid)
                nodes.append({
                    "id": nid,
                    "name": node["name"],
                    "subject": sub,
                    "desc": (node.get("desc") or "")[:60],
                    "depth": depth,
                    "kids": len(node.get("children", [])),
                })
            if nid and parent_id:
                links.append({"source": parent_id, "target": nid, "kind": "tree"})
            if nid:
                for rid in node.get("related", []):
                    links.append({"source": nid, "target": rid, "kind": "rel"})
            for c in node.get("children", []):
                walk(c, nid, depth + 1)

        walk(data, None, 0)
    # related 边只保留两端都存在的
    links = [l for l in links if l["kind"] == "tree" or (l["source"] in seen and l["target"] in seen)]
    return jsonify({"nodes": nodes, "links": links})


@app.route("/api/links")
def api_links():
    uid = request.args.get("uid", "")[:64]
    if uid:
        custom = _load_portal_custom().get(uid)
        if custom:
            return jsonify(custom)
    try:
        return jsonify(json.loads((BASE_DIR / "data" / "links.json").read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return jsonify({"categories": []})


PORTAL_FILE = REMINDER_DIR / "portal_custom.json"


def _load_portal_custom():
    try:
        return json.loads(PORTAL_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


@app.route("/api/portal/save", methods=["POST"])
def portal_save():
    """保存用户的自定义导航（整体覆盖该用户的配置）"""
    body = request.get_json(silent=True) or {}
    uid = str(body.get("uid", ""))[:64]
    cats = body.get("categories")
    if not uid or not isinstance(cats, list):
        return jsonify({"error": "参数不完整"}), 400
    # 基本校验
    clean = []
    for c in cats[:20]:
        sites = []
        for s in (c.get("sites") or [])[:100]:
            name = str(s.get("name", "")).strip()[:64]
            url = str(s.get("url", "")).strip()[:256]
            if not name or not url.startswith(("http://", "https://")):
                continue
            sites.append({
                "name": name, "url": url,
                "desc": str(s.get("desc", ""))[:128],
                "icon": str(s.get("icon", "🔗"))[:8],
            })
        name = str(c.get("name", "")).strip()[:32]
        if name:
            clean.append({"name": name, "icon": str(c.get("icon", "📂"))[:8], "sites": sites})
    data = _load_portal_custom()
    data[uid] = {"categories": clean}
    PORTAL_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return jsonify({"ok": True})


@app.route("/api/portal/reset", methods=["POST"])
def portal_reset():
    """恢复默认导航"""
    body = request.get_json(silent=True) or {}
    uid = str(body.get("uid", ""))[:64]
    data = _load_portal_custom()
    data.pop(uid, None)
    PORTAL_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return jsonify({"ok": True})


@app.route("/api/hospital-rules")
def hospital_rules():
    q = request.args.get("q", "").strip()
    try:
        data = json.loads((BASE_DIR / "data" / "hospital_rules.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return jsonify([])
    hospitals = data.get("hospitals", [])
    if q:
        hospitals = [h for h in hospitals
                     if q in h["name"] or any(q in k for k in h.get("keywords", []))]
    return jsonify(hospitals[:10])


@app.route("/api/tickets/subscribe", methods=["POST"])
def tickets_subscribe():
    body = request.get_json(silent=True) or {}
    uid = str(body.get("uid", ""))[:64]
    kind = body.get("kind")
    sendkey = str(body.get("sendkey", "")).strip()[:64]
    if not uid or not sendkey:
        return jsonify({"error": "缺少用户标识或 SendKey"}), 400

    sub = {"id": uuid.uuid4().hex[:12], "uid": uid, "kind": kind, "sendkey": sendkey}
    if kind == "hospital":
        hospital = str(body.get("hospital", "")).strip()[:64]
        release_time = str(body.get("release_time", "")).strip()[:5]
        if not hospital or not release_time:
            return jsonify({"error": "缺少医院名称或放号时间"}), 400
        sub.update({
            "hospital": hospital,
            "doctor": str(body.get("doctor", "")).strip()[:32],
            "release_time": release_time,
            "last_fired": "",
        })
    elif kind == "event":
        title = str(body.get("title", "")).strip()[:128]
        event_time = str(body.get("event_time", "")).strip()[:16]
        if not title or not event_time:
            return jsonify({"error": "缺少活动名称或开票时间"}), 400
        sub.update({
            "title": title,
            "event_time": event_time,
            "link": str(body.get("link", "")).strip()[:256],
            "fired": False,
        })
    else:
        return jsonify({"error": "未知类型"}), 400

    subs = _load_subs()
    subs.append(sub)
    _save_subs(subs)
    return jsonify({"ok": True, "id": sub["id"]})


@app.route("/api/tickets/list")
def tickets_list():
    uid = request.args.get("uid", "")
    subs = [s for s in _load_subs() if s.get("uid") == uid]
    # 不回传 sendkey
    for s in subs:
        s.pop("sendkey", None)
    return jsonify(subs)


@app.route("/api/tickets/delete", methods=["POST"])
def tickets_delete():
    body = request.get_json(silent=True) or {}
    uid, sub_id = body.get("uid", ""), body.get("id", "")
    subs = _load_subs()
    _save_subs([s for s in subs if not (s.get("uid") == uid and s.get("id") == sub_id)])
    return jsonify({"ok": True})


if __name__ == "__main__":
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("FLASK_PORT", "5000"))
    app.run(host=host, port=port, debug=False)
