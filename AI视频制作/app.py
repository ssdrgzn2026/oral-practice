# -*- coding: utf-8 -*-
"""AI 视频制作：图文视频合成器（Streamlit 单页应用）

流水线：主题 -> LLM 口播文案（可编辑）-> 分镜脚本（中文画面描述）-> 文生图(Kolors) -> TTS(CosyVoice2) -> ffmpeg 合成 mp4。
所有中间产物按内容 sha1 缓存在 data/video_cache/，重跑不重复调用 API。
"""
import base64
import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path

import requests
import streamlit as st
from PIL import Image, ImageDraw, ImageFont

MODULE_DIR = Path(__file__).resolve().parent
CACHE_DIR = Path(os.environ.get("VIDEO_CACHE_DIR", str(MODULE_DIR / "data" / "video_cache")))
IMG_DIR = CACHE_DIR / "images"
AUD_DIR = CACHE_DIR / "audio"
SUB_DIR = CACHE_DIR / "subtitled"  # 渲染了字幕条的图片
OUT_DIR = CACHE_DIR / "output"
SCRIPT_DIR = CACHE_DIR / "scripts"  # LLM 生成的口播文案
PHO_DIR = CACHE_DIR / "photo_desc"  # VLM 对参考照片的内容描述
KLING_DIR = CACHE_DIR / "kling"  # 可灵生成的视频片段
for d in (IMG_DIR, AUD_DIR, SUB_DIR, OUT_DIR, SCRIPT_DIR, PHO_DIR, KLING_DIR):
    d.mkdir(parents=True, exist_ok=True)


def _cleanup_cache(days: int = 30):
    """启动时清理可再生的缓存（output/成品、subtitled/字幕图）；images/audio 需重新调用 API，不删"""
    cutoff = time.time() - days * 86400
    removed = 0
    for d in (OUT_DIR, SUB_DIR):
        for f in d.rglob("*"):
            try:
                if f.is_file() and f.stat().st_mtime < cutoff:
                    f.unlink()
                    removed += 1
            except OSError:
                pass
    print(f"[video-cache] 已清理 {removed} 个超过 {days} 天的可再生缓存文件")


_cleanup_cache()

API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1").rstrip("/")
CHAT_MODEL = os.environ.get("OPENAI_MODEL", "Qwen/Qwen3-14B")
TTS_MODEL = os.environ.get("OPENAI_TTS_MODEL", "FunAudioLLM/CosyVoice2-0.5B")
TTS_VOICE = os.environ.get("OPENAI_TTS_VOICE", "FunAudioLLM/CosyVoice2-0.5B:alex")
IMAGE_MODEL = "Kwai-Kolors/Kolors"
VLM_MODEL = os.environ.get("OPENAI_VLM_MODEL", "Qwen/Qwen3-VL-8B-Instruct")
# 文生图统一风格后缀，保证多镜画面一致性
IMG_STYLE_SUFFIX = "，中国风写实插画，电影感光影，细节丰富，高质量"

SIZES = {"竖屏 576×1024": (576, 1024), "横屏 1024×576": (1024, 576)}

st.set_page_config(page_title="AI 视频制作", page_icon="🎬", layout="wide")
st.markdown("[← 返回杂具小栈首页](/)", unsafe_allow_html=False)
st.title("🎬 AI 视频制作 · 图文视频合成器")
st.caption("主题 → 口播文案 → 分镜脚本 → AI 配图 → AI 配音 → 自动合成视频。所有中间产物已缓存，重跑不重复消耗额度。")
st.markdown("<img src='/api/pv?p=video' style='display:none' alt=''>", unsafe_allow_html=True)

# ========== 登录与用户空间（nginx 传入 X-User-Phone；未开启时一切照旧） ==========
LOGIN_REQUIRED = os.environ.get("VIDEO_LOGIN_REQUIRED", "0") == "1"
ADMIN_PHONES = {p.strip() for p in os.environ.get("ADMIN_PHONES", "").split(",") if p.strip()}


def _user_phone() -> str:
    try:
        return st.context.headers.get("X-User-Phone", "").strip()
    except Exception:  # noqa: BLE001
        return ""


USER_PHONE = _user_phone()
if LOGIN_REQUIRED and not USER_PHONE:
    st.warning("🔒 生成功能需要登录。请先到门户登录后再回来。")
    st.markdown("[→ 去登录](/login?next=/video/)")
    st.stop()

# 用户空间：登录后角色库/提示词库/项目按手机号隔离；未登录走 _anon 公共目录
USER_DIR = CACHE_DIR / "users" / (USER_PHONE or "_anon")
CHAR_DIR = USER_DIR / "characters"
CHAR_DIR.mkdir(parents=True, exist_ok=True)
CHAR_FILE = CHAR_DIR / "characters.json"
TPL_FILE = USER_DIR / "prompt_templates.json"
PROJ_DIR = USER_DIR / "projects"
PROJ_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR = USER_DIR / "output"          # 作品按用户隔离
OUT_DIR.mkdir(parents=True, exist_ok=True)
SHARED_DIR = CACHE_DIR / "shared"      # 公共资产库（全站共享，只管理员可写）
SHARED_DIR.mkdir(parents=True, exist_ok=True)

# 首次登录：把旧全局目录里的角色/模板自动迁移到个人空间（一次性）
if USER_PHONE:
    try:
        _legacy_chars = CACHE_DIR / "characters" / "characters.json"
        if _legacy_chars.exists() and not CHAR_FILE.exists():
            _data = json.loads(_legacy_chars.read_text(encoding="utf-8"))
            for _n, _info in _data.items():
                _src = Path(_info["face"])
                if _src.exists():
                    _dst = CHAR_DIR / _src.name
                    _dst.write_bytes(_src.read_bytes())
                    _data[_n]["face"] = str(_dst)
            CHAR_FILE.write_text(json.dumps(_data, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
        _legacy_tpl = CACHE_DIR / "prompt_templates.json"
        if _legacy_tpl.exists() and not TPL_FILE.exists():
            TPL_FILE.write_text(_legacy_tpl.read_text(encoding="utf-8"), encoding="utf-8")
        # 旧全局项目（如持械入宋）迁入个人项目空间
        import shutil as _shutil
        _legacy_proj = CACHE_DIR / "projects"
        if _legacy_proj.exists():
            for _pd in _legacy_proj.iterdir():
                if _pd.is_dir() and not (PROJ_DIR / _pd.name).exists():
                    _shutil.copytree(_pd, PROJ_DIR / _pd.name)
    except Exception:  # noqa: BLE001
        pass
    st.caption(f"👤 {USER_PHONE}　·　[退出登录](/logout)")


def _sha(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()[:16]


# ========== 可灵（Kling）文生/图生视频 ==========
KLING_KEY = os.environ.get("KLING_API_KEY", "")
KLING_BASE = "https://api-beijing.klingai.com"
KLING_MODEL = os.environ.get("KLING_MODEL", "kling-v2-5-turbo")
KLING_DAILY_LIMIT = int(os.environ.get("KLING_DAILY_LIMIT", "5"))
KLING_QUOTA_FILE = CACHE_DIR / "kling_quota.json"
# 站长 IP 白名单：豁免每日限额
KLING_ADMIN_IPS = {"103.233.163.150", "124.64.22.102", "183.241.219.4", "183.242.227.165"}


def _client_ip() -> str:
    try:
        xff = st.context.headers.get("X-Forwarded-For", "")
        return xff.split(",")[0].strip()
    except Exception:  # noqa: BLE001
        return ""


def is_kling_admin() -> bool:
    if USER_PHONE and USER_PHONE in ADMIN_PHONES:
        return True
    return _client_ip() in KLING_ADMIN_IPS


def kling_quota_left() -> int:
    """今日剩余可灵次数（按自然日封顶，防止超额消费）；站长白名单不限量"""
    if is_kling_admin():
        return KLING_DAILY_LIMIT
    try:
        q = json.loads(KLING_QUOTA_FILE.read_text(encoding="utf-8"))
    except Exception:
        q = {}
    today = time.strftime("%Y-%m-%d")
    used = q.get("count", 0) if q.get("date") == today else 0
    return max(0, KLING_DAILY_LIMIT - used)


def _kling_quota_inc():
    if is_kling_admin():
        return
    today = time.strftime("%Y-%m-%d")
    try:
        q = json.loads(KLING_QUOTA_FILE.read_text(encoding="utf-8"))
    except Exception:
        q = {}
    q = {"date": today, "count": (q.get("count", 0) if q.get("date") == today else 0) + 1}
    KLING_QUOTA_FILE.write_text(json.dumps(q), encoding="utf-8")


def gen_kling_video(desc: str, size_wh, image_path: str = None, salt: str = "") -> Path:
    """可灵生成 5 秒动态片段；有配图时用图生视频（以配图为首帧）。salt 用于重抽时绕过缓存"""
    prompt = desc.rstrip("，。") + IMG_STYLE_SUFFIX
    img_b64 = ""
    if image_path:
        img_b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
    key = _sha(f"kling|{KLING_MODEL}|{prompt}|{size_wh[0]}x{size_wh[1]}|{img_b64[:64]}|{salt}")
    out = KLING_DIR / f"{key}.mp4"
    if out.exists():
        return out
    if kling_quota_left() <= 0:
        raise RuntimeError(f"今日可灵额度已用完（每天 {KLING_DAILY_LIMIT} 次），明天再来")
    headers = {"Authorization": f"Bearer {KLING_KEY}", "Content-Type": "application/json"}
    body = {"model_name": KLING_MODEL, "prompt": prompt, "duration": "5",
            "aspect_ratio": "9:16" if size_wh[1] > size_wh[0] else "16:9"}
    if img_b64:
        body["image"] = img_b64
        url = f"{KLING_BASE}/v1/videos/image2video"
    else:
        url = f"{KLING_BASE}/v1/videos/text2video"
    r = requests.post(url, headers=headers, json=body, timeout=60)
    r.raise_for_status()
    resp = r.json()
    if resp.get("code") != 0:
        raise RuntimeError(f"可灵返回错误：{resp.get('message')}")
    task_id = resp["data"]["task_id"]
    _kling_quota_inc()
    # 轮询任务状态（异步生成，通常 1~5 分钟）
    qurl = f"{url}/{task_id}"
    for _ in range(36):
        time.sleep(10)
        q = requests.get(qurl, headers=headers, timeout=30).json()
        status = (q.get("data") or {}).get("task_status")
        if status == "succeed":
            vurl = q["data"]["task_result"]["videos"][0]["url"]
            v = requests.get(vurl, timeout=300)
            v.raise_for_status()
            out.write_bytes(v.content)
            return out
        if status == "failed":
            raise RuntimeError(f"可灵生成失败：{(q.get('data') or {}).get('task_status_msg')}")
    raise RuntimeError("可灵生成超时（6 分钟未完成）")


# ========== Wan2.2 本地图生视频（主力动态片段通道，走 ComfyUI/AutoDL） ==========
WAN_DIR = CACHE_DIR / "wan"
WAN_DIR.mkdir(parents=True, exist_ok=True)
WAN_WF_FILE = MODULE_DIR / "wan_i2v_workflow.json"  # ComfyUI「导出(API)」的 WanVideoWrapper I2V 工作流
# 工作流关键节点编号（从 875机 ComfyUI 实际跑通的 wanvideo2_2_I2V_A14B 提取）
WAN_NODE = {
    "prompt": "16",          # WanVideoTextEncode（字段 positive_prompt / negative_prompt）
    "image": "67",           # LoadImage 首帧
    "seed": ["27", "90"],    # 高噪 + 低噪两个 WanVideoSampler
    "size": "68",            # ImageResizeKJv2（首帧缩放到模型分辨率）
}


def wan_available() -> bool:
    """Wan 本地视频通道是否可用：ComfyUI 在线 + 工作流文件已部署"""
    return WAN_WF_FILE.exists() and comfy_online()


def _comfy_run_video(wf: dict, timeout_min: int = 25) -> bytes:
    """提交工作流并取回视频字节（VHS_VideoCombine 等节点的 gifs/videos 输出）"""
    r = requests.post(f"{COMFY_BASE}/prompt",
                      json={"prompt": wf, "client_id": _sha(str(time.time()))}, timeout=60)
    r.raise_for_status()
    pid = r.json()["prompt_id"]
    for _ in range(timeout_min * 20):
        time.sleep(3)
        h = requests.get(f"{COMFY_BASE}/history/{pid}", timeout=30).json()
        if pid not in h:
            continue
        status = h[pid].get("status", {})
        for node_out in h[pid].get("outputs", {}).values():
            vids = node_out.get("gifs") or node_out.get("videos") or []
            if vids:
                v = vids[0]
                r = requests.get(f"{COMFY_BASE}/view", params={
                    "filename": v["filename"],
                    "subfolder": v.get("subfolder", ""),
                    "type": v.get("type", "temp")}, timeout=300)
                r.raise_for_status()
                return r.content
        if status.get("status_str") == "error":
            raise RuntimeError(f"ComfyUI 执行出错: {status.get('messages')}")
        if status.get("completed"):
            raise RuntimeError("工作流跑完了但没有视频输出，请检查导出节点")
    raise RuntimeError(f"Wan 视频生成超时（{timeout_min} 分钟）")


def gen_wan_i2v(desc: str, image_path: str, size_wh, salt: str = "") -> Path:
    """Wan2.2 图生视频：以配图为首帧生成约 5 秒动态片段。Wan 原生支持中文提示词。
    salt 用于重抽时绕过缓存"""
    img_bytes = Path(image_path).read_bytes()
    key = _sha(f"wan|{desc}|{_sha_bytes(img_bytes)}|{size_wh[0]}x{size_wh[1]}|{salt}")
    out = WAN_DIR / f"{key}.mp4"
    if out.exists():
        return out
    with open(WAN_WF_FILE, encoding="utf-8") as f:
        wf = json.load(f)
    # 上传首帧图
    r = requests.post(f"{COMFY_BASE}/upload/image",
                      files={"image": ("wan_start.png", img_bytes)}, timeout=60)
    r.raise_for_status()
    wf[WAN_NODE["image"]]["inputs"]["image"] = r.json()["name"]
    wf[WAN_NODE["prompt"]]["inputs"]["positive_prompt"] = desc
    seed = int(time.time() * 1000) % (2**31)
    for nid in ([WAN_NODE["seed"]] if isinstance(WAN_NODE["seed"], str)
                else WAN_NODE["seed"]):
        if nid:
            wf[nid]["inputs"]["seed"] = seed
    if WAN_NODE.get("size"):
        w, h = (480, 832) if size_wh[1] > size_wh[0] else (832, 480)
        wf[WAN_NODE["size"]]["inputs"].update(width=w, height=h)
    out.write_bytes(_comfy_run_video(wf))
    return out


# ========== ComfyUI（PuLID 锁脸配图，可选；默认关，隧道连通即用） ==========
COMFY_BASE = os.environ.get("COMFYUI_BASE", "http://127.0.0.1:6006").rstrip("/")
COMFY_DIR = CACHE_DIR / "comfy"          # ComfyUI 生成的锁脸图缓存
COMFY_WF_FILE = MODULE_DIR / "pulid_workflow.json"  # PuLID_simple 导出的 API 格式工作流
LORA_WF_FILE = MODULE_DIR / "lora_workflow.json"    # LoRA 工作流（有 LoRA 的角色走这条）
COMFY_DIR.mkdir(parents=True, exist_ok=True)
# 角色库/提示词库/项目目录：登录后指向用户空间（见上方登录区块），未登录走共享目录
CHAR_DIR = globals().get("CHAR_DIR", CACHE_DIR / "characters")
CHAR_DIR.mkdir(parents=True, exist_ok=True)
CHAR_FILE = CHAR_DIR / "characters.json"
TPL_FILE = globals().get("TPL_FILE", CACHE_DIR / "prompt_templates.json")
PROJ_DIR = globals().get("PROJ_DIR", CACHE_DIR / "projects")
PROJ_DIR.mkdir(parents=True, exist_ok=True)
# PuLID 工作流节点编号（来自 pulid_workflow.json）
_WF_PROMPT, _WF_NEG, _WF_IMG, _WF_SEED, _WF_SIZE = "22", "23", "12", "3", "5"


def comfy_online() -> bool:
    """ComfyUI 是否可达（隧道连通才算在线）"""
    if not COMFY_WF_FILE.exists():
        return False
    try:
        return requests.get(f"{COMFY_BASE}/system_stats", timeout=2).status_code == 200
    except Exception:  # noqa: BLE001
        return False


def load_characters() -> dict:
    """角色库：个人库覆盖公共库。{名字: {"desc_en":..., "face": 主图, "faces": [全部定妆图], "public": bool}}"""
    chars = {}
    shared_file = SHARED_DIR / "characters.json"
    try:
        for n, v in json.loads(shared_file.read_text(encoding="utf-8")).items():
            v["public"] = True
            chars[n] = v
    except Exception:  # noqa: BLE001
        pass
    try:
        for n, v in json.loads(CHAR_FILE.read_text(encoding="utf-8")).items():
            v.setdefault("faces", [v["face"]] if v.get("face") else [])
            chars[n] = v
    except Exception:  # noqa: BLE001
        pass
    return chars


def save_character(name: str, desc_en: str, images: list, public: bool = False,
                   lora: str = "", trigger: str = ""):
    """新增/覆盖一个角色：多张定妆图（正面/侧面/全身）+ 元数据。public=存公共库（仅管理员）
    lora=LoRA 文件名（填了就走 LoRA 通道，无需参考脸）；trigger=LoRA 触发词"""
    target_file = (SHARED_DIR / "characters.json") if public else CHAR_FILE
    faces = []
    for j, b in enumerate(images):
        p = CHAR_DIR / f"{_sha(name)}_{j}.png"
        p.write_bytes(b)
        faces.append(str(p))
    try:
        chars = json.loads(target_file.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        chars = {}
    entry = {"desc_en": desc_en, "face": faces[0] if faces else "",
             "faces": faces}
    if lora.strip():
        entry["lora"] = lora.strip()
        entry["trigger"] = trigger.strip() or "lince"
    chars[name] = entry
    target_file.write_text(json.dumps(chars, ensure_ascii=False, indent=2), encoding="utf-8")


def delete_character(name: str, public: bool = False):
    """删除角色：public=True 删公共库（仅管理员调用），否则删个人库"""
    f = (SHARED_DIR / "characters.json") if public else CHAR_FILE
    try:
        chars = json.loads(f.read_text(encoding="utf-8"))
        chars.pop(name, None)
        f.write_text(json.dumps(chars, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


# ========== 项目存档（刷新不丢状态） ==========
PROJ_KEYS = ("topic", "script", "shots", "images", "audios", "video",
             "prompts_en", "pulid_history", "kling_history", "kling_src",
             "active_char", "n_shots", "aspect_idx", "making")


def save_project(name: str):
    """把当前制作状态存入项目文件夹"""
    name = name.strip()
    if not name:
        return
    d = PROJ_DIR / name
    d.mkdir(parents=True, exist_ok=True)
    state = {k: st.session_state.get(k) for k in PROJ_KEYS if st.session_state.get(k) is not None}
    (d / "project.json").write_text(json.dumps(state, ensure_ascii=False, indent=2),
                                    encoding="utf-8")


def load_project(name: str):
    """从项目文件夹恢复全部状态"""
    state = json.loads((PROJ_DIR / name / "project.json").read_text(encoding="utf-8"))
    for k, v in state.items():
        st.session_state[k] = v
    st.session_state.proj_name = name


def autosave():
    """每次页面重跑后自动落盘（有项目名才生效）；容错，绝不让保存失败拖垮页面"""
    name = st.session_state.get("proj_name", "")
    if name.strip() and st.session_state.get("shots"):
        try:
            save_project(name)
        except Exception:  # noqa: BLE001
            pass


# ========== 提示词模板库（分三类：画面/运镜/动作；公共种子+个人新增） ==========
TPL_CATS = {"image": "画面", "motion": "运镜", "action": "动作"}
SEED_TPL_FILE = MODULE_DIR / "资产库种子.json"


def _norm_tpl(v) -> dict:
    """统一模板格式：{text_en, text_zh, cat}，兼容旧版 text 字段/纯文本"""
    if isinstance(v, str):
        return {"text_en": v, "text_zh": "", "cat": "image"}
    return {"text_en": v.get("text_en") or v.get("text", ""),
            "text_zh": v.get("text_zh", ""),
            "cat": v.get("cat", "image")}


def load_templates() -> dict:
    """合并三级提示词：公共种子 < 公共库(管理员) < 个人库；{name: {text_en,text_zh,cat,public,seed}}"""
    tpls = {}
    try:
        for n, v in json.loads(SEED_TPL_FILE.read_text(encoding="utf-8")).get("templates", {}).items():
            t = _norm_tpl(v)
            t["seed"] = True
            tpls[n] = t
    except Exception:  # noqa: BLE001
        pass
    try:
        for n, v in json.loads((SHARED_DIR / "prompt_templates.json").read_text(encoding="utf-8")).items():
            t = _norm_tpl(v)
            t["public"] = True
            tpls[n] = t
    except Exception:  # noqa: BLE001
        pass
    try:
        for n, v in json.loads(TPL_FILE.read_text(encoding="utf-8")).items():
            tpls[n] = _norm_tpl(v)  # 个人库覆盖同名
    except Exception:  # noqa: BLE001
        pass
    return tpls


def save_template(name: str, text_en: str, text_zh: str = "", cat: str = "image",
                  public: bool = False):
    f = (SHARED_DIR / "prompt_templates.json") if public else TPL_FILE
    try:
        raw = json.loads(f.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        raw = {}
    raw[name.strip()] = {"text_en": text_en.strip(), "text_zh": text_zh.strip(), "cat": cat}
    f.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")


def delete_template(name: str, public: bool = False):
    f = (SHARED_DIR / "prompt_templates.json") if public else TPL_FILE
    try:
        raw = json.loads(f.read_text(encoding="utf-8"))
        raw.pop(name, None)
        f.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass



def gen_prompt_en(desc: str, char_desc_en: str) -> str:
    """把中文画面描述改写成英文 SDXL 电影感提示词（LLM，sha1 缓存）"""
    key = _sha(f"en-v4|{CHAT_MODEL}|{desc}|{char_desc_en}")
    cache = SCRIPT_DIR / f"{key}.txt"
    if cache.exists():
        return cache.read_text(encoding="utf-8")
    prompt = (
        "把下面的中文画面描述改写成一段英文 AI 绘图提示词（SDXL 用）。要求：\n"
        "1. 提示词的第一个短语必须是景别：特写→extreme close-up，近景→close-up，"
        "中景→medium shot，全景/远景→wide shot / establishing shot，无明确景别→medium shot；\n"
        "2. 电影感、具体、画面化，保留人物动作/场景/朝代元素；\n"
        f"3. 画面中的主角外貌固定描述为：{char_desc_en}，写进提示词里；\n"
        "4. 主角的服装必须与角色描述完全一致，逐字保留服装短语，严禁换成古装或任何其他服装；\n"
        "5. 关键道具必须原样保留并具体化（如手电筒→a glowing modern flashlight）；\n"
        "6. 若主角穿现代服装身处古代场景，必须强调 modern clothing contrasting with ancient surroundings；\n"
        "7. 若画面主体不是主角（如他人视角/反派特写镜头），写明主角只在背景中或不出镜；\n"
        "8. 只输出英文提示词本身，不要解释。\n\n"
        f"中文画面描述：{desc}"
    )
    r = requests.post(f"{BASE_URL}/chat/completions", headers=_api_headers(),
                      json={"model": CHAT_MODEL, "temperature": 0.3,
                            "messages": [{"role": "user", "content": prompt}]}, timeout=120)
    r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"].strip()
    text += (", photorealistic live-action film still, epic wide composition, dramatic volumetric lighting, "
             "rich intricate details, depth of field, 8k")
    cache.write_text(text, encoding="utf-8")
    return text


def gen_comfy_pulid(desc: str, char: dict, size_wh, seed: int = 0, prompt_en: str = None) -> Path:
    """调 ComfyUI 出定妆图：角色有 LoRA 走 LoRA 通道（定脸定装），否则走 PuLID 锁脸。sha1 缓存"""
    if prompt_en is None:
        prompt_en = gen_prompt_en(desc, char["desc_en"])
    lora_name = (char.get("lora") or "").strip()
    ckpt = os.environ.get("COMFY_CHECKPOINT", "").strip()
    face_key = ""
    face_bytes = b""
    if not lora_name:
        face_path = char.get("face") or (char.get("faces") or [None])[0]
        face_bytes = Path(face_path).read_bytes()
        face_key = _sha_bytes(face_bytes)
    key = _sha(f"pulid|{prompt_en}|{face_key}|{lora_name}|{size_wh[0]}x{size_wh[1]}|{seed}|{ckpt}")
    out = COMFY_DIR / f"{key}.png"
    if out.exists():
        return out

    if lora_name:
        # LoRA 通道：无需参考脸，触发词 + 场景描述
        with open(LORA_WF_FILE, encoding="utf-8") as f:
            wf = json.load(f)
        trigger = (char.get("trigger") or "lince").strip()
        wf["22"]["inputs"]["text"] = f"{trigger}, {prompt_en}"
        wf["40"]["inputs"]["lora_name"] = lora_name
        wf["3"]["inputs"]["seed"] = seed or int(time.time() * 1000) % (2**31)
        if ckpt:
            wf["4"]["inputs"]["ckpt_name"] = ckpt
        if size_wh[1] > size_wh[0]:
            wf["5"]["inputs"].update(width=768, height=1024)
        else:
            wf["5"]["inputs"].update(width=1152, height=640)
        out.write_bytes(_comfy_run(wf))
        return out

    with open(COMFY_WF_FILE, encoding="utf-8") as f:
        wf = json.load(f)
    # 上传参考脸（每次上传拿服务器文件名，小图很快）
    r = requests.post(f"{COMFY_BASE}/upload/image",
                      files={"image": ("face.png", face_bytes)}, timeout=60)
    r.raise_for_status()
    wf[_WF_IMG]["inputs"]["image"] = r.json()["name"]
    wf[_WF_PROMPT]["inputs"]["text"] = prompt_en
    wf[_WF_SEED]["inputs"]["seed"] = seed or int(time.time() * 1000) % (2**31)
    if ckpt:  # 覆盖默认底模（如换成写实模型 juggernaut）
        wf["4"]["inputs"]["ckpt_name"] = ckpt
    # SDXL 友好分辨率：竖屏 768x1024，横屏 1152x640
    if size_wh[1] > size_wh[0]:
        wf[_WF_SIZE]["inputs"].update(width=768, height=1024)
    else:
        wf[_WF_SIZE]["inputs"].update(width=1152, height=640)

    out.write_bytes(_comfy_run(wf))
    return out


def _comfy_run(wf: dict) -> bytes:
    """提交工作流并取回图片字节（供 PuLID/纯文生图共用）"""
    r = requests.post(f"{COMFY_BASE}/prompt",
                      json={"prompt": wf, "client_id": _sha(str(time.time()))}, timeout=60)
    r.raise_for_status()
    pid = r.json()["prompt_id"]
    for _ in range(100):
        time.sleep(3)
        h = requests.get(f"{COMFY_BASE}/history/{pid}", timeout=30).json()
        if pid not in h:
            continue
        for node_out in h[pid].get("outputs", {}).values():
            imgs = node_out.get("images", [])
            if imgs:
                img = imgs[0]
                r = requests.get(f"{COMFY_BASE}/view", params={
                    "filename": img["filename"],
                    "subfolder": img.get("subfolder", ""),
                    "type": img.get("type", "temp")}, timeout=120)
                r.raise_for_status()
                return r.content
    raise RuntimeError("ComfyUI 出图超时（5 分钟）")


def gen_comfy_txt2img(prompt_en: str, seed: int = 0, width: int = 768, height: int = 1024) -> Path:
    """纯文生图（绕过 PuLID）：群演面孔/场景定妆等批量出图"""
    key = _sha(f"t2i|{prompt_en}|{width}x{height}|{seed}|{os.environ.get('COMFY_CHECKPOINT', '')}")
    out = COMFY_DIR / f"{key}.png"
    if out.exists():
        return out
    with open(COMFY_WF_FILE, encoding="utf-8") as f:
        wf = json.load(f)
    wf["3"]["inputs"]["model"] = ["4", 0]  # 模型直连采样器，绕过 PuLID
    wf["22"]["inputs"]["text"] = prompt_en
    wf["3"]["inputs"]["seed"] = seed or int(time.time() * 1000) % (2**31)
    wf["5"]["inputs"].update(width=width, height=height)
    ckpt = os.environ.get("COMFY_CHECKPOINT", "").strip()
    if ckpt:
        wf["4"]["inputs"]["ckpt_name"] = ckpt
    out.write_bytes(_comfy_run(wf))
    return out


def _api_headers():
    return {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}


# ========== VLM 参考照片理解 ==========
def describe_photo(img_bytes: bytes) -> str:
    """用 VLM（Qwen2.5-VL-72B）生成照片内容描述，按图片字节 sha1 缓存。
    图片先缩到长边 768px 再 base64，省 token。"""
    key = _sha_bytes(img_bytes)
    cache = PHO_DIR / f"{key}.txt"
    if cache.exists():
        return cache.read_text(encoding="utf-8")
    from io import BytesIO
    im = Image.open(BytesIO(img_bytes)).convert("RGB")
    im.thumbnail((768, 768))
    buf = BytesIO()
    im.save(buf, format="JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    payload = {
        "model": VLM_MODEL,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": (
                "这是一张产品界面截图/照片。请描述：1) 这是什么系统/页面（念出可见的标题文字）"
                " 2) 界面上有哪些功能模块或元素 3) 整体风格。三句话以内，用中文。")},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        ]}],
        "max_tokens": 200,
    }
    r = requests.post(f"{BASE_URL}/chat/completions", headers=_api_headers(),
                      json=payload, timeout=120)
    r.raise_for_status()
    desc = r.json()["choices"][0]["message"]["content"].strip()
    cache.write_text(desc, encoding="utf-8")
    return desc


# ========== 第 2 步：LLM 口播文案 ==========
def gen_script(topic: str, photo_descs: list = None) -> str:
    """根据主题（可选结合参考照片描述）生成 1 分钟短视频口播文案（200~300 字），sha1 缓存"""
    photo_descs = [d for d in (photo_descs or []) if d]
    key = _sha(f"script|{CHAT_MODEL}|{topic}|{'|'.join(photo_descs)}")
    cache = SCRIPT_DIR / f"{key}.txt"
    if cache.exists():
        return cache.read_text(encoding="utf-8")
    photo_block = ""
    if photo_descs:
        listing = "\n".join(f"第{i+1}张：{d}" for i, d in enumerate(photo_descs))
        photo_block = (
            f"\n用户还提供了 {len(photo_descs)} 张参考照片，内容如下：\n{listing}\n"
            "这是一支介绍性视频，照片是真实界面截图/实拍素材，文案要像导游一样带领观众看这些画面，"
            "让观众听着解说就能对应看到截图内容。\n"
            "文案必须按照片展示顺序组织叙事：第几张照片讲了什么，对应段落就解说它。\n"
            "【硬性约束】文案只能围绕用户主题和上述照片的实际内容展开，"
            "严禁编造主题中未提及的人物、事件、历史故事或功能细节；不写与照片无关的内容。\n"
        )
    prompt = (
        f"你是一名短视频编剧。请为主题「{topic}」写一段适合 1 分钟左右短视频的中文口播文案。\n"
        "要求：200~300 字；口语化、有吸引力，开头一句要抓人；叙述有画面感，方便后续拆分成分镜；"
        "严格围绕主题，禁止编造主题中未提及的人物、事件、功能细节；"
        "涉及中国历史/人物题材时写清朝代与人物姓名。只输出文案正文，不要标题、不要解释。"
        + photo_block
    )
    r = requests.post(f"{BASE_URL}/chat/completions", headers=_api_headers(),
                      json={"model": CHAT_MODEL, "temperature": 0.8,
                            "messages": [{"role": "user", "content": prompt}]}, timeout=120)
    r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"].strip()
    cache.write_text(text, encoding="utf-8")
    return text


# ========== 第 3 步：LLM 分镜脚本 ==========
def gen_storyboard(script: str, n: int, photo_descs: list = None) -> list:
    photo_descs = [d for d in (photo_descs or []) if d]
    photo_block = ""
    photo_field = '"photo": 0（数字；0 表示此镜用 AI 生成配图）'
    if photo_descs:
        listing = "\n".join(f"第{i+1}张：{d}" for i, d in enumerate(photo_descs))
        photo_block = (
            f"\n用户提供了 {len(photo_descs)} 张参考照片，内容如下：\n{listing}\n"
            "【照片使用规则】照片是这个视频的主角素材，大多数镜头应该使用照片：\n"
            "1. 每镜 photo 字段默认填与该镜解说词最匹配的照片序号；只有照片实在无法覆盖该镜内容时才填 0（AI 生成配图）；\n"
            "2. photo 字段应尽量把每张切题照片都用到，允许多个镜头共用同一张照片（不同构图/时段/解说角度）；\n"
            "3. photo=0 的镜头，desc 仍需写具体的画面描述。\n"
        )
        photo_field = '"photo": 照片序号（1 起，默认优先选照片；0 表示此镜用 AI 生成配图）'
    prompt = (
        "你是一名短视频导演。请把下面的口播文案拆成 "
        f"{n} 个分镜的短视频脚本。\n"
        '只输出一个 JSON 对象，格式为 {"shots": [...]}，不要输出其他任何内容。shots 数组每个元素格式：\n'
        '{"desc": "该镜头的画面描述（中文，用于文生图模型）", '
        '"narration": "该镜头的中文解说词（从文案中截取或改写，20~40字）", "seconds": 秒数(数字,3~8), '
        + photo_field + "}\n"
        "对 desc 的硬性要求：\n"
        "1. 必须紧扣该镜解说词的具体内容——写清画面里的人物、朝代、场景、动作，禁止泛泛的「战场」「宫殿」这类空泛描述；\n"
        "2. 涉及中国历史/人物题材时，必须写明朝代与服饰约束，例如「中国南北朝时期服饰」「中国古代铠甲」「唐代圆领袍」，"
        "严禁出现欧洲骑士、西式盔甲、欧洲城堡等元素；\n"
        "3. 各镜头画面风格保持一致。\n"
        f"shots 数组共 {n} 个元素。\n" + photo_block + f"\n文案：\n{script}"
    )
    payload = {
        "model": CHAT_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "response_format": {"type": "json_object"},
    }
    last_err = None
    for attempt in range(2):  # 失败重试一次
        try:
            r = requests.post(f"{BASE_URL}/chat/completions", headers=_api_headers(),
                              json=payload, timeout=120)
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"]
            shots = _parse_shots(text)
            if shots and len(shots) == n:
                return shots
            last_err = ValueError(f"分镜数量不符或解析失败：得到 {len(shots or [])} 个，期望 {n} 个")
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt == 0:
                time.sleep(1)
    raise RuntimeError(f"分镜脚本生成失败（已重试一次）：{last_err}")


def _parse_shots(text: str) -> list:
    text = text.strip()
    text = re.sub(r"^```(json)?|```$", "", text, flags=re.MULTILINE).strip()
    data = None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\[.*\]", text, flags=re.DOTALL)
        if m:
            data = json.loads(m.group(0))
    if isinstance(data, dict):
        if "desc" in data:  # 模型只返回了单个分镜对象
            data = [data]
        else:
            for v in data.values():
                if isinstance(v, list):
                    data = v
                    break
    if not isinstance(data, list):
        return []
    shots = []
    for item in data:
        if not isinstance(item, dict):
            continue
        desc = str(item.get("desc", "")).strip()
        narration = str(item.get("narration", "")).strip()
        try:
            seconds = max(2.0, min(15.0, float(item.get("seconds", 5))))
        except (TypeError, ValueError):
            seconds = 5.0
        try:  # photo 字段：1-based 照片序号，0/null/越界视为 AI 生成
            photo = int(item.get("photo") or 0)
            if not 0 <= photo <= 8:
                photo = 0
        except (TypeError, ValueError):
            photo = 0
        if desc and narration:
            shots.append({"desc": desc, "narration": narration, "seconds": seconds,
                          "photo": photo, "speaker": str(item.get("speaker") or "旁白")})
    return shots


def _parse_manual_shots(text: str) -> list:
    """解析手工录入：优先 JSON（复用 _parse_shots），否则按行解析。
    行格式："画面描述 | 解说词 | 秒数"（秒数可省，默认5）；没有 | 时整行作为解说词，
    画面描述默认取解说词（配图 prompt 可直接用）。行首「镜1：」「镜头2.」「1.」等序号前缀会剥掉。
    断行容错：两行合并成一行时（出现多个「|纯数字」秒数边界），按边界切成多个镜头；
    只有 | 后跟纯数字才算秒数边界，解说词里的普通数字（如「3比2」）不会误拆。
    """
    text = text.strip()
    if not text:
        return []
    if text[0] in "[{":
        return _parse_shots(text)
    raw_lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        marks = list(re.finditer(r"[|｜]\s*\d+(?:\.\d+)?", line))
        cuts = [m for m in marks if m.end() < len(line)]  # 后面还有内容的才算断行边界
        if len(marks) >= 2 and cuts:
            pos = 0
            for m in cuts:
                raw_lines.append(line[pos:m.end()])
                pos = m.end()
            raw_lines.append(line[pos:])
        else:
            raw_lines.append(line)
    shots = []
    for line in raw_lines:
        line = re.sub(r"^\s*(?:第\s*)?(?:镜\s*头?\s*)?\d+\s*[：:.、．]\s*", "", line.strip())
        if not line:
            continue
        # 跳过表头行（如"画面描述|解说词|秒数|说话人"）
        cells = [c.strip() for c in re.split(r"[|｜]", line)]
        if cells[0] in ("画面描述", "描述", "镜头描述", "画面") and len(cells) >= 2:
            continue
        if "说话人" in cells and any(k in cells for k in ("解说词", "台词", "秒数")):
            continue
        parts = [p.strip() for p in re.split(r"[|｜]", line)]
        if len(parts) < 2:
            desc, narration, sec_str = parts[0], parts[0], ""
        else:
            desc, narration = parts[0], parts[1]
            sec_str = parts[2] if len(parts) > 2 else ""
        if not narration:
            continue
        speaker = parts[3] if len(parts) > 3 and parts[3] else "旁白"
        try:
            seconds = max(2.0, min(15.0, float(sec_str))) if sec_str else 5.0
        except ValueError:
            seconds = 5.0
        shots.append({"desc": desc, "narration": narration, "seconds": seconds,
                      "speaker": speaker})
    return shots


# ========== 第 4 步：文生图 ==========
def gen_image(desc: str, size: str, seed: int = 0) -> Path:
    """Kolors 中文原生模型，直接用中文描述；seed 用于单镜重跑时绕过缓存/换随机性"""
    prompt = desc.rstrip("，。") + IMG_STYLE_SUFFIX
    key = _sha(f"img|{IMAGE_MODEL}|{prompt}|{size}|{seed}")
    out = IMG_DIR / f"{key}.png"
    if out.exists():
        return out
    body = {"model": IMAGE_MODEL, "prompt": prompt, "size": size}
    if seed:
        body["seed"] = seed
    last_err = None
    for attempt in range(4):  # 429 限流时退避重试：20s/40s/60s
        try:
            r = requests.post(f"{BASE_URL}/images/generations", headers=_api_headers(),
                              json=body, timeout=300)
            if r.status_code == 429:
                raise RuntimeError("限流")
            r.raise_for_status()
            item = r.json()["data"][0]
            if item.get("b64_json"):
                out.write_bytes(base64.b64decode(item["b64_json"]))
            else:
                img = requests.get(item["url"], timeout=300)
                img.raise_for_status()
                out.write_bytes(img.content)
            time.sleep(6)  # 每镜之间间隔，避免触发限流
            return out
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt < 3:
                time.sleep(20 * (attempt + 1))
    raise RuntimeError(f"配图失败（已重试3次）：{last_err}")


# ========== 第 5 步：TTS 配音（支持分角色音色） ==========
# 预置音色（CosyVoice2 系统音色；配音步可为每个"说话人"指定）
VOICE_PRESETS = ["alex(男)", "benjamin(男)", "charles(男)", "david(男)",
                 "anna(女)", "bella(女)", "claire(女)", "emily(女)"]


def _voice_short(label: str) -> str:
    """"alex(男)" -> "alex"；已是短名则原样返回"""
    return label.split("(")[0] if "(" in label else label


def _voice_full(short: str) -> str:
    """alex -> FunAudioLLM/CosyVoice2-0.5B:alex；已是全名则原样返回"""
    return short if ":" in short else f"{TTS_MODEL}:{short}"


def gen_audio(narration: str, voice: str = None) -> Path:
    voice = _voice_full(voice) if voice else TTS_VOICE
    key = _sha(f"tts|{voice}|{narration}")
    out = AUD_DIR / f"{key}.mp3"
    if out.exists():
        return out
    last_err = None
    for attempt in range(4):
        try:
            r = requests.post(f"{BASE_URL}/audio/speech", headers=_api_headers(),
                              json={"model": TTS_MODEL, "input": narration,
                                    "voice": voice, "response_format": "mp3"}, timeout=300)
            if r.status_code == 429:
                raise RuntimeError("限流")
            r.raise_for_status()
            out.write_bytes(r.content)
            time.sleep(2)
            return out
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt < 3:
                time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"配音失败（已重试3次）：{last_err}")


# ========== 第 6 步：字幕渲染 + ffmpeg 合成 ==========
def find_cjk_font() -> str:
    try:
        out = subprocess.run(["fc-list", ":lang=zh", "file"], capture_output=True,
                             text=True, timeout=15).stdout
        for line in out.splitlines():
            path = line.split(":")[0].strip()
            if path and Path(path).exists():
                return path
    except Exception:  # noqa: BLE001
        pass
    for cand in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                 "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
                 "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"):
        if Path(cand).exists():
            return cand
    raise RuntimeError("未找到中文字体，请确认镜像已安装 fonts-noto-cjk")


def render_subtitle(img_path: Path, narration: str, size_wh, bar_h_ratio=0.12) -> Path:
    key = _sha(f"sub|v2|{img_path.name}|{narration}|{size_wh}")
    out = SUB_DIR / f"{key}.png"
    if out.exists():
        return out
    w, h = size_wh
    img = Image.open(img_path).convert("RGB").resize((w, h))
    draw = ImageDraw.Draw(img, "RGBA")
    bar_h = int(h * bar_h_ratio)
    draw.rectangle([0, h - bar_h, w, h], fill=(0, 0, 0, 150))
    font_size = max(20, h // 34)
    font = ImageFont.truetype(find_cjk_font(), font_size)
    # 简单按宽度换行
    lines, cur = [], ""
    for ch in narration:
        if draw.textlength(cur + ch, font=font) > w * 0.9:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    line_h = int(font_size * 1.3)
    total = line_h * len(lines)
    pad_bottom = int(h * 0.02)  # 离底边留 padding，防裁切
    y = h - bar_h + (bar_h - total) // 2  # 条内垂直居中
    y = min(y, h - pad_bottom - total)    # 底边 padding 优先，防裁切
    if total <= bar_h - pad_bottom:
        y = max(y, h - bar_h + 2)         # 放得下时保持不出字幕条上沿
    for line in lines:
        lw = draw.textlength(line, font=font)
        draw.text(((w - lw) / 2, y), line, font=font, fill=(255, 255, 255, 255))
        y += line_h
    img.save(out)
    return out


def _sub_text(shot: dict) -> str:
    """字幕文本：非旁白镜头加说话人前缀，如「士兵：站住！」"""
    n = (shot.get("narration") or "").strip()
    sp = (shot.get("speaker") or "旁白").strip()
    return f"{sp}：{n}" if n and sp not in ("", "旁白") else n


def audio_duration(audio: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(audio)], capture_output=True, text=True, timeout=30)
    try:
        return max(1.0, float(r.stdout.strip()))
    except ValueError:
        return 5.0


def placeholder_image(idx: int, size_wh) -> Path:
    """纯色深蓝底 + 白色镜头序号的占位图，供跳过配图时使用"""
    w, h = size_wh
    out = IMG_DIR / f"ph_{idx}_{w}x{h}.png"
    if not out.exists():
        img = Image.new("RGB", (w, h), (15, 32, 64))
        d = ImageDraw.Draw(img)
        font = ImageFont.truetype(find_cjk_font(), max(40, int(h * 0.08)))
        t = f"镜头 {idx + 1}"
        tw = d.textlength(t, font=font)
        d.text(((w - tw) / 2, h / 2), t, font=font, fill=(255, 255, 255))
        img.save(out)
    return out


def silent_audio(seconds: float) -> Path:
    """静音 wav 占位音频，供跳过配音时使用"""
    out = AUD_DIR / f"silence_{seconds:.1f}.wav"
    if not out.exists():
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
             "-t", f"{seconds:.2f}", str(out)], check=True, capture_output=True, timeout=60)
    return out


def compose_video(shots: list, images: list, audios: list, size_wh, work: Path,
                  motion: bool = True) -> Path:
    w, h = size_wh
    key = _sha("video|" + "|".join(f"{p.name}{a.name}" for p, a in zip(images, audios))
               + f"{w}x{h}|motion={int(motion)}")
    tmp_dir = OUT_DIR / "_tmp"          # 合成先落临时区，用户确认后才存入作品
    tmp_dir.mkdir(parents=True, exist_ok=True)
    final = tmp_dir / f"{key}.mp4"
    if final.exists():
        return final
    work.mkdir(parents=True, exist_ok=True)
    fps = 24
    segs = []
    for i, (img, aud) in enumerate(zip(images, audios)):
        dur = audio_duration(aud)
        seg = work / f"seg{i}.mp4"
        if str(img).lower().endswith(".mp4"):
            # 可灵动态片段：循环/截断到配音时长，字幕用 drawtext 烧制
            vf = f"scale={w}:{h},fps={fps}"
            narration = _sub_text(shots[i])
            if narration:
                txt = work / f"sub{i}.txt"
                txt.write_text(narration, encoding="utf-8")
                bar_h = int(h * 0.12)
                pad_bottom = int(h * 0.02)  # 离底边留 padding，防裁切
                fontsize = max(18, h // 34)
                text_h = int(fontsize * 1.3)  # 单行文字估算高度
                # y 坐标在 Python 里算好（min 表达式里的逗号会被 ffmpeg 误解析）
                y_pos = min(h - bar_h + (bar_h - text_h) // 2, h - pad_bottom - text_h)
                vf += (f",drawbox=y={h - bar_h}:w={w}:h={bar_h}:color=black@0.45:t=fill"
                       f",drawtext=fontfile='{find_cjk_font()}':textfile='{txt}':"
                       f"fontcolor=white:fontsize={fontsize}:"
                       f"x=(w-text_w)/2:y={y_pos}")
            subprocess.run(
                ["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(img), "-i", str(aud),
                 "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-b:a", "128k", "-shortest", "-t", f"{dur:.2f}",
                 str(seg)], check=True, capture_output=True, timeout=600)
            segs.append(seg)
            continue
        if motion:
            # zoompan 缓慢推进 + 音频轨，按配音时长定该镜时长
            frames = int(dur * fps) + 1
            vf = (f"scale={w*2}:{h*2},"
                  f"zoompan=z='min(1+0.15*on/{frames},1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                  f":d={frames}:s={w}x{h}:fps={fps}")
        else:
            # 低性能服务器：静态图 + 音频，直接输出画幅分辨率
            vf = f"scale={w}:{h}"
        subprocess.run(
            ["ffmpeg", "-y", "-loop", "1", "-i", str(img), "-i", str(aud),
             "-vf", vf, "-r", str(fps), "-c:v", "libx264", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "128k", "-shortest", "-t", f"{dur:.2f}",
             str(seg)], check=True, capture_output=True, timeout=600)
        segs.append(seg)
    list_file = work / "concat.txt"
    list_file.write_text("".join(f"file '{s.as_posix()}'\n" for s in segs), encoding="utf-8")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
         "-c", "copy", str(final)], check=True, capture_output=True, timeout=600)
    return final


# ========== 无 API Key 提示 ==========
if not API_KEY:
    st.warning("⚠️ 未配置 OPENAI_API_KEY。请在服务器 .env 中设置 SiliconFlow 的密钥（OPENAI_API_KEY / OPENAI_BASE_URL）后重启服务。")
    st.stop()


def render_works():
    """📁 我的作品：列出 output 目录下所有已合成视频（按手机号隔离）"""
    st.subheader("📁 我的作品")
    ups = st.file_uploader("⬆️ 上传已有作品（mp4，可多选，如《林策入宋》原版和修复版）",
                           type=["mp4"], accept_multiple_files=True, key="works_upload")
    if ups:
        for f in ups:
            (OUT_DIR / f.name).write_bytes(f.getvalue())
        st.success(f"已上传 {len(ups)} 个作品")
        st.rerun()
    videos = sorted(OUT_DIR.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    if videos and st.button("🧹 清空我的全部作品", key="works_clear"):
        for v in videos:
            v.unlink()
        st.rerun()
    if not videos:
        st.info("暂无作品，合成完成的视频会自动出现在这里。")
        return
    from datetime import datetime
    playing = st.session_state.get("works_playing")
    for v in videos:
        stt = v.stat()
        dur = audio_duration(v)
        with st.container(border=True):
            c1, c2 = st.columns([2, 3])
            c1.markdown(f"**{v.name}**")
            c1.caption(f"创建时间：{datetime.fromtimestamp(stt.st_mtime):%Y-%m-%d %H:%M}　"
                       f"大小：{stt.st_size/1024/1024:.1f} MB　时长：{dur:.1f}s")
            # 懒加载：点「▶ 播放」才渲染播放器，避免列表页同时缓冲所有视频
            if playing == v.name:
                st.video(str(v))
                if st.button("▲ 收起", key=f"close_{v.name}", use_container_width=True):
                    st.session_state.works_playing = None
                    st.rerun()
            elif st.button("▶ 播放", key=f"play_{v.name}", use_container_width=True):
                st.session_state.works_playing = v.name
                st.rerun()
            d1, d2 = st.columns(2)
            with open(v, "rb") as f:
                d1.download_button("⬇️ 下载", f, file_name=v.name, mime="video/mp4",
                                   key=f"dl_{v.name}", use_container_width=True)
            if d2.button("🗑 删除", key=f"del_{v.name}", use_container_width=True):
                v.unlink()
                if st.session_state.get("works_playing") == v.name:
                    st.session_state.works_playing = None
                st.rerun()


# ========== 通用资产存取（角色/场景/群演/道具共用一套结构） ==========
def _asset_file(kind: str) -> Path:
    return CHAR_DIR / f"{kind}.json"


def _asset_store(kind: str) -> dict:
    try:
        return json.loads(_asset_file(kind).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _asset_save(kind: str, name: str, desc_en: str, img_bytes: bytes = None):
    face = ""
    if img_bytes:
        face_path = CHAR_DIR / f"{kind}_{_sha(name)}.png"
        face_path.write_bytes(img_bytes)
        face = str(face_path)
    items = _asset_store(kind)
    items[name] = {"desc_en": desc_en, "face": face}
    _asset_file(kind).write_text(json.dumps(items, ensure_ascii=False, indent=2),
                                 encoding="utf-8")


def _asset_delete(kind: str, name: str):
    items = _asset_store(kind)
    items.pop(name, None)
    _asset_file(kind).write_text(json.dumps(items, ensure_ascii=False, indent=2),
                                 encoding="utf-8")


def _seed_assets(kind: str) -> dict:
    """种子资产（公共只读）：来自 资产库种子.json 的 assets 区"""
    try:
        seeds = json.loads(SEED_TPL_FILE.read_text(encoding="utf-8")).get("assets", {})
        out = {}
        for n, v in seeds.get(kind, {}).items():
            if isinstance(v, str):
                v = {"desc_en": v}
            v["seed"] = True
            out[n] = v
        return out
    except Exception:  # noqa: BLE001
        return {}


def _asset_tab(kind: str, title: str, desc_ph: str):
    items = _seed_assets(kind) | _asset_store(kind)  # 用户同名覆盖种子
    with st.popover(f"➕ 新建{title}"):
        n = st.text_input(f"{title}名", key=f"{kind}_new_name")
        d = st.text_area("英文描述", key=f"{kind}_new_desc", placeholder=desc_ph, height=90)
        f = st.file_uploader("定妆图/参考图（可选，可后补）", type=["png", "jpg", "jpeg"],
                             key=f"{kind}_new_face")
        if st.button("保存入库", key=f"{kind}_save", use_container_width=True):
            if n.strip() and d.strip():
                _asset_save(kind, n.strip(), d.strip(),
                            f.getvalue() if f is not None else None)
                st.success(f"「{n}」已入库")
                st.rerun()
            else:
                st.error("名称和描述要填")
    if not items:
        st.info(f"暂无{title}，点上方按钮新建")
        return
    cols = st.columns(8)  # 小图平铺
    for j, (name, info) in enumerate(items.items()):
        c = cols[j % 8]
        face = info.get("face") or ""
        if face and Path(face).exists():
            c.image(face, use_container_width=True)
        else:
            c.markdown("🖼️")
        c.caption(name)
        with c.popover("🔍"):
            if face and Path(face).exists():
                st.image(face, caption=name)
            st.caption(info.get("desc_en", ""))
        if not info.get("seed"):
            if c.button("🗑", key=f"{kind}_del_{j}", use_container_width=True):
                _asset_delete(kind, name)
                st.rerun()


def render_assets():
    """🎭 资产库页：角色卡/场景库/群演库/道具库"""
    st.subheader("🎭 资产库")
    st.caption("角色、场景、群演、道具——建在这里，制作页直接调用")
    t1, t2, t3, t4 = st.tabs(["👤 角色卡", "🏯 场景库", "👥 群演库", "🗡 道具库"])
    with t1:
        st.caption("🟢 ComfyUI 在线" if comfy_online() else "⚪ ComfyUI 离线（锁脸生成不可用）")
        # 角色卡：支持一人多面（正面/侧面/全身多张定妆图）
        with st.popover("➕ 新建角色"):
            n = st.text_input("角色名", key="char_new_name", placeholder="如：林策")
            d = st.text_area("外貌描述（英文）", key="char_new_desc",
                             placeholder="a 25 years old Chinese young man, short black hair, dark grey outdoor jacket, camo backpack",
                             height=90)
            fs = st.file_uploader("定妆图（可传多张：正面/侧面/全身；有 LoRA 的角色可空）",
                                  type=["png", "jpg", "jpeg"],
                                  accept_multiple_files=True, key="char_new_faces")
            ln = st.text_input("LoRA 文件名（可选，有 LoRA 就走 LoRA 通道）",
                               key="char_new_lora", placeholder="如：lince_v1.safetensors")
            tg = st.text_input("触发词（可选，默认 lince）", key="char_new_trigger",
                               placeholder="lince")
            is_public = False
            if USER_PHONE and USER_PHONE in ADMIN_PHONES:
                is_public = st.checkbox("存为公共资产（所有人可用）", key="char_public")
            if st.button("保存入库", key="char_save", use_container_width=True):
                if n.strip() and d.strip() and (fs or ln.strip()):
                    save_character(n.strip(), d.strip(),
                                   [f.getvalue() for f in (fs or [])], public=is_public,
                                   lora=ln, trigger=tg)
                    st.success(f"「{n}」已入库")
                    st.rerun()
                else:
                    st.error("角色名、外貌描述要填，定妆图或 LoRA 至少给一样")
        chars = load_characters()
        if not chars:
            st.info("暂无角色，点上方按钮新建")
        else:
            cols = st.columns(8)
            is_admin = USER_PHONE and USER_PHONE in ADMIN_PHONES
            for j, (name, info) in enumerate(chars.items()):
                c = cols[j % 8]
                badge = "🏛" if info.get("public") else "👤"
                n_faces = len(info.get("faces") or ([info.get("face")] if info.get("face") else []))
                face = info.get("face") or ""
                if face and Path(face).exists():
                    c.image(face, use_container_width=True)
                else:
                    c.markdown("🖼️")
                c.caption(f"{name}{badge}·{n_faces}图")
                with c.popover("🔍"):
                    for fp in (info.get("faces") or [face]):
                        if fp and Path(fp).exists():
                            st.image(fp, use_container_width=True)
                    st.caption(info.get("desc_en", ""))
                can_del = not info.get("public") or is_admin
                if can_del and c.button("🗑", key=f"char_del_{j}", use_container_width=True):
                    delete_character(name, public=info.get("public", False))
                    st.rerun()
    with t2:
        _asset_tab("scenes", "场景", "ancient Chinese city gate at dusk, stone walls, torches")
    with t3:
        _asset_tab("extras", "群演面孔", "an ordinary Song dynasty townsfolk face, weathered, hanfu")
        if comfy_online():
            if st.button("🎲 批量生成 5 张群演面孔（ComfyUI，约3分钟）",
                         key="extras_batch", use_container_width=True):
                batch = [
                    ("市井老者2", "portrait photo of an elderly Song dynasty Chinese townsman, weathered wrinkled face, grey beard, plain hanfu, neutral expression, film still, 8k"),
                    ("商贩妇人2", "portrait photo of a middle-aged Song dynasty Chinese market vendor woman, commoner dress, headscarf, neutral expression, film still, 8k"),
                    ("账房先生", "portrait photo of a thin Song dynasty Chinese clerk, small mustache, plain robe, shrewd eyes, film still, 8k"),
                    ("年轻脚夫", "portrait photo of a young Song dynasty Chinese laborer, suntanned skin, coarse linen clothes, honest face, film still, 8k"),
                    ("茶肆老板娘", "portrait photo of a Song dynasty Chinese teahouse owner woman, warm smile, simple elegant dress, film still, 8k"),
                ]
                prog = st.progress(0.0, text="批量生成群演面孔中…")
                for j, (nm, prompt) in enumerate(batch):
                    try:
                        img = gen_comfy_txt2img(prompt, seed=int(time.time()) + j)
                        _asset_save("extras", nm, prompt, img.read_bytes())
                    except Exception as e:  # noqa: BLE001
                        st.error(f"{nm} 生成失败：{e}")
                    prog.progress((j + 1) / len(batch), text=f"已生成 {j+1}/{len(batch)} 张")
                prog.empty()
                st.rerun()
    with t4:
        _asset_tab("props", "道具", "a black modern tactical flashlight, rugged, metal body")


def render_prompts():
    """📝 提示词库页：画面/运镜/动作三类，中英双文，公共/个人"""
    st.subheader("📝 提示词库")
    st.caption("英文用于锁脸/配图，中文用于可灵动态片段。🏛公共=全站共享（管理员维护），👤我的=个人库")
    tpls = load_templates()
    is_admin = USER_PHONE and USER_PHONE in ADMIN_PHONES
    tabs = st.tabs([f"{label}（{sum(1 for v in tpls.values() if v['cat'] == k)}）"
                    for k, label in TPL_CATS.items()])
    for tab, (k, label) in zip(tabs, TPL_CATS.items()):
        with tab:
            items = [(n, v) for n, v in tpls.items() if v["cat"] == k]
            for n, v in items:
                badge = "🌱种子" if v.get("seed") else ("🏛公共" if v.get("public") else "👤我的")
                c1, c2 = st.columns([6, 1])
                c1.markdown(f"**{n}**　`{badge}`")
                if v["text_en"]:
                    c1.caption(f"EN：{v['text_en']}")
                if v["text_zh"]:
                    c1.caption(f"中：{v['text_zh']}")
                can_del = (not v.get("seed")) and (not v.get("public") or is_admin)
                if can_del and c2.button("🗑 删除", key=f"tpld_{k}_{n}"):
                    delete_template(n, public=v.get("public", False))
                    st.rerun()
            if not items:
                st.info("暂无内容")
            st.divider()
            n1 = st.text_input("名称", key=f"tpln_{k}", placeholder="如：逆光剪影")
            t_en = st.text_area("英文提示词（锁脸/配图用）", key=f"tplen_{k}", height=68)
            t_zh = st.text_area("中文提示词（可灵动态用，可空）", key=f"tplzh_{k}", height=68)
            to_public = False
            if is_admin:
                to_public = st.checkbox("存为公共库（所有人可用）", key=f"tplpub_{k}")
            if st.button(f"💾 存入{label}库", key=f"tpls_{k}", use_container_width=True):
                if n1.strip() and (t_en.strip() or t_zh.strip()):
                    save_template(n1, t_en, t_zh, k, public=to_public)
                    st.success("已保存" + ("（公共库）" if to_public else ""))
                    st.rerun()


def render_projects():
    """🗂 我的项目：制作过程存档（分镜/配图/抽卡历史），区别于最终作品"""
    st.subheader("🗂 我的项目")
    st.caption("项目 = 制作过程的全部进度；最终成片在「我的作品」里")
    projs = sorted((p for p in PROJ_DIR.iterdir() if p.is_dir()),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    if not projs:
        st.info("暂无项目。在「视频制作」页填写项目名后，进度会自动保存到这里。")
        return
    for p in projs:
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 1, 1])
            c1.markdown(f"**{p.name}**")
            from datetime import datetime
            c1.caption(f"更新于 {datetime.fromtimestamp(p.stat().st_mtime):%Y-%m-%d %H:%M}")
            if c2.button("📂 打开", key=f"proj_open_{p.name}", use_container_width=True):
                load_project(p.name)
                st.session_state.page = "make"
                st.rerun()
            if c3.button("🗑 删除", key=f"proj_del_{p.name}", use_container_width=True):
                import shutil
                shutil.rmtree(p, ignore_errors=True)
                st.rerun()


# ========== 页面导航：制作 / 我的项目 / 资产库 / 提示词库 / 我的作品 ==========
NAV = [("make", "🎬 视频制作"), ("projects", "🗂 我的项目"), ("assets", "🎭 资产库"),
       ("prompts", "📝 提示词库"), ("works", "📁 我的作品")]
nav_cols = st.columns(len(NAV))
page = st.session_state.get("page", "make")
for col, (pid, label) in zip(nav_cols, NAV):
    if col.button(label, use_container_width=True,
                  type="primary" if page == pid else "secondary"):
        st.session_state.page = pid
        st.rerun()
if page == "works":
    render_works()
    st.stop()
if page == "projects":
    render_projects()
    st.stop()
if page == "assets":
    render_assets()
    st.stop()
if page == "prompts":
    render_prompts()
    st.stop()

# ========== 第 1 步：输入主题 ==========
with st.container(border=True):
    st.subheader("① 输入主题或文案")
    # ---- 项目存档 ----
    proj_names = sorted(p.name for p in PROJ_DIR.iterdir() if p.is_dir())
    pj1, pj2, pj3 = st.columns([2, 1, 1])
    pj1.text_input("📁 项目名（启用后所有进度自动保存，刷新/换电脑不丢）",
                   value=st.session_state.get("proj_name", ""), key="proj_name_input",
                   placeholder="如：持械入宋-01")
    st.session_state.proj_name = st.session_state.proj_name_input  # 输入即绑定项目
    if pj2.button("💾 保存项目", use_container_width=True):
        st.session_state.proj_name = st.session_state.proj_name_input
        save_project(st.session_state.proj_name)
        st.success("已保存")
    if pj3.button("📂 打开项目", use_container_width=True, disabled=not proj_names):
        st.session_state.show_proj_list = True
    if st.session_state.get("show_proj_list") and proj_names:
        pick = st.selectbox("选择要打开的项目", proj_names, key="proj_pick")
        if st.button("加载这个项目", key="proj_load_btn"):
            load_project(pick)
            st.session_state.show_proj_list = False
            st.rerun()
    if st.session_state.get("proj_name"):
        st.caption(f"当前项目：{st.session_state.proj_name}（自动保存中）")

    c1, c2, c3 = st.columns([3, 1, 1])
    topic = c1.text_area("视频主题 / 提示词 / 完整文案",
                         value=st.session_state.get("topic", ""),
                         height=140,
                         key="topic_input",
                         placeholder="两种用法：\n· 写主题（如：三分钟讲清淝水之战）→ 点「生成文案」\n· 直接粘贴完整口播文案 → 点「直接手写/粘贴文案」")
    n_shots = c2.slider("分镜数", 3, 8, st.session_state.get("n_shots", 5))
    aspect_label = c3.radio("画幅", list(SIZES.keys()), index=st.session_state.get("aspect_idx", 0))
    bc1, bc2 = st.columns(2)
    gen_clicked = bc1.button("✍️ 生成文案", use_container_width=True)
    if gen_clicked:
        if not topic.strip():
            st.error("请先填写视频主题")
            st.stop()
        st.session_state.update(topic=topic, n_shots=n_shots,
                                aspect_idx=list(SIZES).index(aspect_label))
        with st.spinner("LLM 正在撰写口播文案…"):
            try:
                st.session_state.script = gen_script(
                    topic.strip(),
                    [p["desc"] for p in st.session_state.get("photos", []) if p.get("desc")])
            except Exception as e:  # noqa: BLE001
                st.error(f"文案生成失败：{e}")
                st.stop()
        for k in ("shots", "images", "audios", "video"):
            st.session_state.pop(k, None)
        st.rerun()
    if bc2.button("📝 直接手写/粘贴文案", use_container_width=True):
        if not topic.strip():
            st.error("请先把完整文案粘贴到上方文本框，再点此按钮")
            st.stop()
        st.session_state.update(topic=topic, n_shots=n_shots,
                                aspect_idx=list(SIZES).index(aspect_label))
        st.session_state.setdefault("script", topic.strip())
        st.rerun()
    # ---- 参考照片（可选，最多 8 张）----
    photo_files = st.file_uploader(
        "📷 上传参考照片（可选，最多 8 张；AI 会看图生成文案/分镜，被选中的照片直接用作配图）",
        type=["png", "jpg", "jpeg"], accept_multiple_files=True, key="photo_files")
    photo_files = (photo_files or [])[:8]
    ids = [f.file_id for f in photo_files]
    if ids != st.session_state.get("photo_ids"):
        photos, vlm_failed = [], False
        if photo_files:
            prog = st.progress(0.0, text="AI 正在识别照片…")
            for i, f in enumerate(photo_files):
                data = f.getvalue()
                path = IMG_DIR / f"up_{_sha_bytes(data)}.png"
                if not path.exists():
                    path.write_bytes(data)
                try:
                    desc = describe_photo(data)
                except Exception:  # noqa: BLE001 —— VLM 不可用时降级为纯文字流程
                    desc, vlm_failed = "", True
                photos.append({"path": str(path), "desc": desc})
                prog.progress((i + 1) / len(photo_files), text=f"已识别 {i+1}/{len(photo_files)} 张")
            prog.empty()
        st.session_state.update(photos=photos, photo_ids=ids, vlm_failed=vlm_failed)
        st.rerun()
    photos = st.session_state.get("photos", [])
    if st.session_state.get("vlm_failed") and photos:
        st.warning("⚠️ VLM 暂不可用，已按纯文字流程继续（照片仍可作为分镜配图使用）")
    if photos:
        pcols = st.columns(len(photos))
        for i, p in enumerate(photos):
            pcols[i].image(p["path"], use_container_width=True)
            edited_desc = pcols[i].text_area(
                f"第{i+1}张描述（可编辑）", value=p["desc"], height=90,
                key=f"photo_desc_{i}",
                placeholder="（VLM 未识别，可手填这张照片的内容）")
            if edited_desc.strip() != p["desc"]:
                st.session_state.photos[i]["desc"] = edited_desc.strip()

photo_descs = [p["desc"] for p in st.session_state.get("photos", []) if p.get("desc")]
photo_paths = [p["path"] for p in st.session_state.get("photos", [])]

if "script" not in st.session_state:
    st.stop()

# ========== 第 2 步：文案确认 / 编辑 ==========
with st.container(border=True):
    st.subheader("② 口播文案（可编辑）")
    edited = st.text_area("分镜脚本将基于这份文案拆分", value=st.session_state.script,
                          height=180, label_visibility="collapsed")
    cc1, cc2 = st.columns([1, 3])
    if cc1.button("🚀 用此文案开始制作", type="primary", use_container_width=True):
        if not edited.strip():
            st.error("文案不能为空")
            st.stop()
        st.session_state.script = edited.strip()
        st.session_state.making = True
        for k in ("shots", "images", "audios", "video", "seeds", "uploads", "audio_uploads"):
            st.session_state.pop(k, None)
        st.rerun()
    if cc2.button("↻ 重新生成文案", key="redo_script_text"):
        st.session_state.pop("script", None)
        st.session_state.pop("making", None)
        for k in ("shots", "images", "audios", "video", "seeds", "uploads", "audio_uploads"):
            st.session_state.pop(k, None)
        st.rerun()

size_wh = SIZES[aspect_label]
size_str = f"{size_wh[0]}x{size_wh[1]}"
shots = st.session_state.get("shots")
images = st.session_state.get("images")
audios = st.session_state.get("audios")
video = st.session_state.get("video")

# ========== 第 3 步：分镜脚本 ==========
with st.container(border=True):
    st.subheader("③ 分镜脚本")
    with st.expander("✍️ 直接录入分镜（跳过 AI 生成脚本）"):
        manual = st.text_area(
            "每行一个镜头：画面描述 | 解说词/台词 | 秒数 | 说话人（秒数、说话人可省，默认5秒+旁白）；"
            "行内没有 | 时整行作为解说词（画面描述自动取解说词）；也可直接粘贴分镜 JSON。"
            "「镜1：」「1.」等序号前缀会自动去掉",
            height=140, key="manual_shots_text",
            placeholder="谢安站在淝水岸边，东晋铠甲，远眺远方 | 公元383年，淝水之战一触即发 | 5 | 旁白")
        if st.button("✅ 使用这份分镜", key="use_manual_shots"):
            parsed = _parse_manual_shots(manual)
            if not parsed:
                st.error("未能解析出任何镜头，请检查格式")
                st.stop()
            st.session_state.shots = parsed
            st.session_state.making = True
            for k in ("images", "audios", "video", "seeds", "uploads", "audio_uploads"):
                st.session_state.pop(k, None)
            st.rerun()
    if shots is None:
        if not st.session_state.get("making"):
            st.info("确认上方文案后点击「用此文案开始制作」，或使用下方任一跳过通道")
        if st.button("⏭ 跳过，直接去配图", key="skip_shots",
                     help="按分镜数生成空白占位镜头，之后在配图步逐镜上传或生成"):
            st.session_state.shots = [{"desc": "", "narration": "", "seconds": 5.0}
                                      for _ in range(st.session_state.get("n_shots", 5))]
            st.session_state.making = True
            for k in ("images", "audios", "video", "seeds", "uploads", "audio_uploads"):
                st.session_state.pop(k, None)
            st.rerun()
        if not st.session_state.get("making"):
            st.stop()
        with st.spinner("LLM 正在拆分分镜脚本…"):
            try:
                shots = gen_storyboard(st.session_state.script, st.session_state.n_shots,
                                       photo_descs)
                st.session_state.shots = shots
            except Exception as e:  # noqa: BLE001
                st.error(f"分镜脚本生成失败：{e}")
                if st.button("↻ 重试本步", key="retry_script"):
                    st.rerun()
                st.stop()
    for i, s in enumerate(shots):
        s.setdefault("speaker", "旁白")
        st.markdown(f"**镜头 {i+1}**（{s['seconds']}s）")
        nc1, nc2, nc3 = st.columns([2, 1, 0.7])
        new_desc = nc1.text_area("画面描述", value=s["desc"], height=68,
                                 key=f"shot_desc_{i}", label_visibility="collapsed",
                                 placeholder="画面描述")
        def _fill_desc(i=i):
            pick = st.session_state.get(f"desc_tpl_sel_{i}", "")
            if pick and pick != "套提示词…":
                tv = load_templates()[pick]
                fill = tv["text_zh"] or tv["text_en"]
                if fill:
                    st.session_state.shots[i]["desc"] = fill
                    st.session_state[f"shot_desc_{i}"] = fill
                st.session_state[f"desc_tpl_sel_{i}"] = "套提示词…"

        nc1.selectbox("套提示词", ["套提示词…"] + list(load_templates().keys()),
                      key=f"desc_tpl_sel_{i}", on_change=_fill_desc,
                      label_visibility="collapsed")
        new_narr = nc2.text_area("解说词/台词", value=s["narration"], height=68,
                                 key=f"shot_narr_{i}", label_visibility="collapsed",
                                 placeholder="解说词或角色台词")
        new_spk = nc3.text_input("说话人", value=s["speaker"], key=f"shot_spk_{i}",
                                 placeholder="旁白")
        if new_desc.strip() != s["desc"] or new_narr.strip() != s["narration"] or new_spk.strip() != s["speaker"]:
            narr_changed = new_narr.strip() != s["narration"] or new_spk.strip() != s["speaker"]
            s["desc"], s["narration"] = new_desc.strip(), new_narr.strip()
            s["speaker"] = new_spk.strip() or "旁白"
            st.session_state.shots = shots
            st.session_state.pop("video", None)      # 内容变了，成片作废
            if narr_changed:
                st.session_state.pop("audios", None)  # 解说词变了，配音重生成
    if st.button("↻ 重新生成脚本", key="redo_script"):
        for k in ("shots", "images", "audios", "video", "seeds", "uploads", "audio_uploads"):
            st.session_state.pop(k, None)
        st.rerun()

# ========== 第 4 步：文生图 ==========
with st.container(border=True):
    st.subheader("④ 分镜配图（Kolors · ComfyUI 锁脸）")
    uploads = st.session_state.setdefault("uploads", {})  # 镜头序号(str) -> 自定义图片路径

    # ---- 锁脸角色选择（角色卡在「资产库」页管理）----
    chars = load_characters()
    is_online = comfy_online()
    sel1, sel2 = st.columns([2, 1])
    sel1.selectbox("🎭 当前锁脸角色（到「资产库」页新建/管理角色卡）",
                   ["（不使用）"] + list(chars.keys()), key="active_char")
    sel2.caption("")
    sel2.caption("🟢 ComfyUI 在线" if is_online else "⚪ ComfyUI 离线")
    active_char = st.session_state.get("active_char", "（不使用）")
    active_char = chars.get(active_char) if active_char != "（不使用）" else None

    if images is None:
        # 懒生成：不自动消耗 Kolors 额度，先用参考照片/占位图就位，AI 配图由按钮触发
        images = []
        for i, s in enumerate(shots):
            ph = s.get("photo", 0)
            if str(i) in uploads:  # 已上传自定义图片的镜头
                images.append(uploads[str(i)])
            elif ph >= 1 and ph <= len(photo_paths):  # 分镜指定用参考照片
                images.append(photo_paths[ph - 1])
            else:
                images.append(str(placeholder_image(i, size_wh)))
        st.session_state.images = images
    ph_count = sum(1 for p in images if Path(p).name.startswith("ph_"))
    if ph_count:
        st.info(f"当前 {ph_count} 个镜头为占位图/照片，点下方按钮生成 AI 配图（消耗 Kolors 额度）")
        if st.button("✨ 生成全部 AI 配图", type="primary", key="gen_all_images",
                     use_container_width=True):
            prog = st.progress(0.0, text="生成 AI 配图中…")
            todo = [i for i, p in enumerate(images)
                    if Path(p).name.startswith("ph_") and shots[i]["desc"].strip()]
            for j, i in enumerate(todo):
                try:
                    images[i] = str(gen_image(shots[i]["desc"], size_str))
                    uploads.pop(str(i), None)
                except Exception as e:  # noqa: BLE001
                    st.error(f"镜头 {i+1} 配图失败：{e}")
                prog.progress((j + 1) / max(1, len(todo)),
                              text=f"已生成 {j+1}/{len(todo)} 张")
            prog.empty()
            st.session_state.images = images
            st.session_state.pop("video", None)
            st.rerun()
    seeds = st.session_state.setdefault("seeds", [0] * len(shots))
    cols = st.columns(len(images))
    for i, p in enumerate(images):
        ph = shots[i].get("photo", 0) if i < len(shots) else 0
        is_video = str(p).lower().endswith(".mp4")
        if is_video:
            source = "🎬 动态片段"
        elif str(i) in uploads:
            source = "自定义上传"
        elif ph >= 1 and ph <= len(photo_paths) and p == photo_paths[ph - 1]:
            source = "📷 上传照片"
        elif Path(p).name.startswith("ph_"):
            source = "占位图"
        else:
            source = "AI 生成"
        if is_video:
            src = st.session_state.get("kling_src", {}).get(str(i))
            if src and Path(src).exists():
                with cols[i].expander("🖼 定脸首帧（此视频由此图生成）"):
                    st.image(src, use_container_width=True)
                    if st.button("⏪ 回到定脸帧（视频保留在抽片历史）",
                                 key=f"backstill_{i}", use_container_width=True):
                        images[i] = src
                        st.session_state.images = images
                        st.session_state.pop("video", None)
                        st.rerun()
            cols[i].video(p)
            cols[i].caption(f"镜头 {i+1} · {source}")
        else:
            cols[i].image(p, caption=f"镜头 {i+1} · {source}", use_container_width=True)
        if Path(p).name.startswith("ph_") and shots[i]["desc"].strip():
            if cols[i].button("✨ 生成此图（AI）", key=f"gen_img_{i}", use_container_width=True):
                with st.spinner(f"生成镜头 {i+1} AI 配图…"):
                    try:
                        images[i] = str(gen_image(shots[i]["desc"], size_str))
                        uploads.pop(str(i), None)
                        st.session_state.images = images
                        st.session_state.pop("video", None)
                    except Exception as e:  # noqa: BLE001
                        st.error(f"镜头 {i+1} 配图失败：{e}")
                st.rerun()
        if not is_video and wan_available():
            if cols[i].button("🎞 本地动态片段（Wan·主力）", key=f"wan_{i}",
                              use_container_width=True):
                with st.spinner(f"Wan 正在生成镜头 {i+1} 动态片段（4090 约5~15分钟）…"):
                    try:
                        st.session_state.setdefault("kling_src", {})[str(i)] = p  # 记住首帧
                        images[i] = str(gen_wan_i2v(shots[i]["desc"], p, size_wh,
                                                    salt=str(time.time())))
                        st.session_state.setdefault("kling_history", {}).setdefault(
                            str(i), []).append(images[i])
                        st.session_state.images = images
                        st.session_state.pop("video", None)
                        autosave()
                        st.rerun()
                    except Exception as e:  # noqa: BLE001
                        st.error(f"镜头 {i+1} Wan 生成失败：{e}")
        if KLING_KEY and not is_video:
            left = kling_quota_left()
            admin = is_kling_admin()
            quota_note = "站长不限量" if admin else f"今日余 {left}"
            if cols[i].button(f"✨ 可灵片段（备选·{quota_note}）", key=f"kling_{i}",
                              use_container_width=True, disabled=(not admin and left <= 0)):
                with st.spinner(f"可灵正在生成镜头 {i+1} 动态片段（约1~5分钟）…"):
                    try:
                        st.session_state.setdefault("kling_src", {})[str(i)] = p  # 记住首帧，供重抽用
                        images[i] = str(gen_kling_video(shots[i]["desc"], size_wh, image_path=p))
                        st.session_state.setdefault("kling_history", {}).setdefault(
                            str(i), []).append(images[i])
                        st.session_state.images = images
                        st.session_state.pop("video", None)
                        autosave()
                        st.rerun()
                    except Exception as e:  # noqa: BLE001
                        st.error(f"镜头 {i+1} 可灵生成失败：{e}")
        # 视频片段的重抽 + 抽片历史（Wan 主力 / 可灵备选共用历史与首帧记录）
        khist = st.session_state.get("kling_history", {}).get(str(i), [])
        if is_video and khist and wan_available():
            if cols[i].button("↻ 重抽本地片段（Wan）", key=f"wan_re_{i}",
                              use_container_width=True):
                with st.spinner(f"Wan 正在重抽镜头 {i+1}（约5~15分钟）…"):
                    try:
                        src = st.session_state.get("kling_src", {}).get(str(i))
                        images[i] = str(gen_wan_i2v(shots[i]["desc"], src, size_wh,
                                                    salt=str(time.time())))
                        khist.append(images[i])
                        st.session_state.images = images
                        st.session_state.pop("video", None)
                        autosave()
                        st.rerun()
                    except Exception as e:  # noqa: BLE001
                        st.error(f"镜头 {i+1} 重抽失败：{e}")
        if KLING_KEY and is_video and khist:
            left = kling_quota_left()
            admin = is_kling_admin()
            quota_note = "站长不限量" if admin else f"今日余 {left}"
            if cols[i].button(f"↻ 重抽可灵片段（备选·{quota_note}）", key=f"kling_re_{i}",
                              use_container_width=True, disabled=(not admin and left <= 0)):
                with st.spinner(f"可灵正在重抽镜头 {i+1}（约1~5分钟）…"):
                    try:
                        src = st.session_state.get("kling_src", {}).get(str(i))
                        images[i] = str(gen_kling_video(
                            shots[i]["desc"], size_wh, image_path=src,
                            salt=str(time.time())))
                        khist.append(images[i])
                        st.session_state.images = images
                        st.session_state.pop("video", None)
                        autosave()
                        st.rerun()
                    except Exception as e:  # noqa: BLE001
                        st.error(f"镜头 {i+1} 重抽失败：{e}")
            with cols[i].expander(f"🎬 抽片历史（{len(khist)} 段，点击选用）"):
                for j, vp in enumerate(khist):
                    st.video(vp)
                    cur = "（当前使用）" if p == vp else ""
                    if st.button(f"选用第 {j+1} 版{cur}", key=f"khist_{i}_{j}"):
                        images[i] = vp
                        st.session_state.images = images
                        st.session_state.pop("video", None)
                        st.rerun()
        if active_char and not is_video:
            # 英文提示词可见可改：手动改过就用手动的，否则自动翻译（LLM 缓存，不重复消耗）
            pe = st.session_state.setdefault("prompts_en", {})
            if str(i) not in pe and shots[i]["desc"].strip():
                try:
                    pe[str(i)] = gen_prompt_en(shots[i]["desc"], active_char["desc_en"])
                except Exception:  # noqa: BLE001
                    pe[str(i)] = ""
            if shots[i]["desc"].strip():
                pe[str(i)] = cols[i].text_area("英文提示词（可改）", value=pe.get(str(i), ""),
                                               key=f"pen_{i}", height=68,
                                               label_visibility="collapsed",
                                               placeholder="英文提示词")
                img_tpls = {n: v["text_en"] for n, v in load_templates().items()
                            if v["cat"] == "image" and v["text_en"]}
                if img_tpls:
                    with cols[i].popover("📋 套模板", use_container_width=True):
                        for tname, ttext in img_tpls.items():
                            if st.button(tname, key=f"tpl_apply_{i}_{tname}",
                                         use_container_width=True):
                                st.session_state.prompts_en[str(i)] = ttext
                                st.session_state.pop(f"pen_{i}", None)
                                st.rerun()
            if not is_online:
                cols[i].button("🔒 锁脸生成（离线）", key=f"pulid_{i}",
                               use_container_width=True, disabled=True)
            elif cols[i].button(f"🔒 锁脸生成（{st.session_state.active_char}）",
                                key=f"pulid_{i}", use_container_width=True):
                with st.spinner(f"ComfyUI 正在锁脸生成镜头 {i+1}（约1分钟）…"):
                    try:
                        seeds[i] = int(time.time() * 1000) % (2**31)  # 每次点击换新种子（抽卡）
                        images[i] = str(gen_comfy_pulid(shots[i]["desc"], active_char,
                                                        size_wh, seed=seeds[i],
                                                        prompt_en=pe.get(str(i)) or None))
                        st.session_state.setdefault("pulid_history", {}).setdefault(
                            str(i), []).append(images[i])
                        st.session_state.images = images
                        st.session_state.pop("video", None)
                        autosave()
                        st.rerun()
                    except Exception as e:  # noqa: BLE001
                        st.error(f"镜头 {i+1} 锁脸生成失败：{e}")
        if cols[i].button("↻ 重生成此图", key=f"redo_img_{i}", use_container_width=True):
            seeds[i] = int(time.time() * 1000) % (2**31)
            with st.spinner(f"重新生成镜头 {i+1} 配图…"):
                images[i] = str(gen_image(shots[i]["desc"], size_str, seed=seeds[i]))
            uploads.pop(str(i), None)  # AI 重生成后恢复为 AI 来源
            st.session_state.images = images
            st.session_state.pop("video", None)
            st.rerun()
        # 抽卡历史：该镜头所有锁脸生成版本，点击选用
        hist = st.session_state.get("pulid_history", {}).get(str(i), [])
        if hist and not is_video:
            with cols[i].expander(f"🎰 抽卡历史（{len(hist)} 张，点击选用）"):
                hcols = st.columns(4)
                for j, hp in enumerate(hist):
                    hcols[j % 4].image(hp, use_container_width=True)
                    if hcols[j % 4].button("选用", key=f"hist_{i}_{j}",
                                           use_container_width=True):
                        images[i] = hp
                        st.session_state.images = images
                        st.session_state.pop("video", None)
                        st.rerun()
        if cols[i].button("↺ 重做此镜配图", key=f"rebuild_{i}", use_container_width=True,
                          help="清空该镜配图和提示词缓存，回到占位图重新生成"):
            images[i] = str(placeholder_image(i, size_wh))
            st.session_state.get("prompts_en", {}).pop(str(i), None)
            st.session_state.pop(f"pen_{i}", None)
            st.session_state.images = images
            st.session_state.pop("video", None)
            st.rerun()
        up = cols[i].file_uploader("上传自定义图片", type=["png", "jpg", "jpeg"],
                                   key=f"upload_{i}", label_visibility="collapsed")
        if up is not None:
            data = up.getvalue()
            path = IMG_DIR / f"up_{_sha_bytes(data)}.png"
            # 按内容 hash 幂等判断：状态被重置（uploads 清空）后重跑也能重新生效
            if uploads.get(str(i)) != str(path) or not path.exists():
                if not path.exists():
                    path.write_bytes(data)
                uploads[str(i)] = str(path)
                images[i] = str(path)
                st.session_state.images = images
                st.session_state.pop("video", None)
                st.rerun()
    if st.button("↻ 重新生成全部配图", key="redo_img"):
        for k in ("images", "audios", "video", "seeds"):
            st.session_state.pop(k, None)
        st.rerun()
    if st.button("⏭ 全部用占位图，直接去配音", key="skip_all_images"):
        st.session_state.images = [str(placeholder_image(i, size_wh)) for i in range(len(shots))]
        st.session_state.pop("video", None)
        st.rerun()

# ========== 第 5 步：TTS 配音 ==========
with st.container(border=True):
    st.subheader("⑤ 分镜配音（CosyVoice2 / 自定义音频）")
    audio_uploads = st.session_state.setdefault("audio_uploads", {})  # 镜头序号(str) -> 自定义音频路径
    # 对话模式：给每个说话人分配音色
    speakers = sorted({s.get("speaker", "旁白") for s in shots})
    vmap = st.session_state.setdefault("voice_map", {})
    if speakers != ["旁白"]:
        with st.expander("🗣 角色音色分配（对话模式）", expanded=True):
            vcols = st.columns(min(len(speakers), 4))
            for j, sp in enumerate(speakers):
                idx = 0 if sp == "旁白" else (j % len(VOICE_PRESETS))
                vmap[sp] = vcols[j % 4].selectbox(sp, VOICE_PRESETS, index=idx,
                                                  key=f"voice_{sp}")
    if audios is None:
        audios = []
        prog = st.progress(0.0, text="生成配音中…")
        failed = None
        for i, s in enumerate(shots):
            try:
                if str(i) in audio_uploads:  # 已上传自定义音频的镜头跳过 TTS
                    audios.append(audio_uploads[str(i)])
                elif not s["narration"].strip():  # 占位镜头：用静音音频
                    audios.append(str(silent_audio(s["seconds"])))
                else:
                    audios.append(str(gen_audio(s["narration"],
                                                voice=_voice_short(vmap.get(s.get("speaker"), "")) or None)))
            except Exception as e:  # noqa: BLE001
                failed = f"镜头 {i+1} 配音失败：{e}"
                break
            prog.progress((i + 1) / len(shots), text=f"已生成 {i+1}/{len(shots)} 段")
        prog.empty()
        if failed:
            st.session_state.audios = audios or None
            st.error(failed)
            c1, c2 = st.columns(2)
            if c1.button("↻ 重试本步", key="retry_tts"):
                st.rerun()
            if c2.button("⏭ 跳过失败镜头，用静音占位继续", key="skip_tts_on_fail"):
                while len(audios) < len(shots):
                    audios.append(str(silent_audio(shots[len(audios)]["seconds"])))
                st.session_state.audios = audios
                st.rerun()
            st.stop()
        st.session_state.audios = audios
    cols = st.columns(len(audios))
    for i, p in enumerate(audios):
        source = "自定义上传" if str(i) in audio_uploads else "AI 配音"
        cols[i].caption(f"镜头 {i+1} · {source}")
        cols[i].audio(p)
        up = cols[i].file_uploader("上传自定义音频", type=["mp3", "wav"],
                                   key=f"upload_audio_{i}", label_visibility="collapsed")
        if up is not None:
            data = up.getvalue()
            ext = Path(up.name).suffix.lower() or ".mp3"
            path = AUD_DIR / f"up_{_sha_bytes(data)}{ext}"
            if audio_uploads.get(str(i)) != str(path) or not path.exists():
                if not path.exists():
                    path.write_bytes(data)
                audio_uploads[str(i)] = str(path)
                audios[i] = str(path)
                st.session_state.audios = audios
                st.session_state.pop("video", None)
                st.rerun()
    if st.button("↻ 重新生成配音", key="redo_tts"):
        for k in ("audios", "video"):
            st.session_state.pop(k, None)
        st.rerun()
    if st.button("⏭ 全部用静音占位，直接去合成", key="skip_all_tts"):
        st.session_state.audios = [str(silent_audio(s["seconds"])) for s in shots]
        st.session_state.pop("video", None)
        st.rerun()

# ========== 第 6 步：合成视频（手动触发） ==========
with st.container(border=True):
    st.subheader("⑥ 合成视频")
    n = len(shots)
    ok_shots = n >= 1
    ok_images = bool(images) and len(images) == n
    ok_audios = bool(audios) and len(audios) == n
    ph_shots = [i + 1 for i, p in enumerate(images or []) if Path(p).name.startswith("ph_")]
    ph_images = len(ph_shots)
    ph_audios = sum(1 for p in (audios or []) if Path(p).name.startswith("silence_"))
    img_note = f"（{ph_images} 张占位，可升级为 AI 图）" if ph_images else ""
    aud_note = f"（{ph_audios} 段静音占位）" if ph_audios else ""
    st.markdown(
        f"{'✅' if ok_shots else '⬜'} {n} 个分镜　"
        f"{'✅' if ok_images else '⬜'} {len(images) if images else 0}/{n} 张配图{img_note}　"
        f"{'✅' if ok_audios else '⬜'} {len(audios) if audios else 0}/{n} 段配音{aud_note}")
    ready = ok_shots and ok_images and ok_audios
    if ph_shots:
        st.warning("⚠️ 以下镜头仍是占位图（无实际画面）："
                   + "、".join(f"镜头{i}" for i in ph_shots)
                   + "。建议回到第 ④ 步生成或上传配图。")
    motion = st.checkbox("启用运镜效果（zoompan 缓慢推进，低性能服务器可关闭提速）",
                         value=True, key="motion")
    confirm_ph = st.session_state.get("confirm_compose_with_ph", False)
    if st.button("🎬 合成视频", type="primary", disabled=not ready,
                 use_container_width=True):
        if ph_shots and not confirm_ph:
            st.session_state.confirm_compose_with_ph = True
            st.rerun()
        else:
            st.session_state.confirm_compose_with_ph = False
            st.session_state.do_compose = True
            st.rerun()
    if ph_shots and confirm_ph:
        st.warning("⚠️ 确认包含占位图镜头也要合成吗？占位镜头将显示为纯色背景。")
        if st.button("仍要合成（含占位图）", key="confirm_compose_ph", use_container_width=True):
            st.session_state.confirm_compose_with_ph = False
            st.session_state.do_compose = True
            st.rerun()
    if st.session_state.pop("do_compose", False):
        with st.spinner("正在渲染字幕并合成视频，请稍候…"):
            try:
                sub_imgs = [Path(images[i]) if str(images[i]).lower().endswith(".mp4")
                            else render_subtitle(Path(images[i]), _sub_text(shots[i]), size_wh)
                            for i in range(n)]
                work = OUT_DIR / ("work_" + _sha(st.session_state.get("topic", "") + str(time.time())))
                st.session_state.video = str(
                    compose_video(shots, sub_imgs, [Path(a) for a in audios], size_wh, work,
                                  motion=motion))
                video = st.session_state.video
            except subprocess.CalledProcessError as e:
                st.error(f"ffmpeg 合成失败：{e.stderr.decode(errors='ignore')[-500:] if e.stderr else e}")
                st.stop()
            except Exception as e:  # noqa: BLE001
                st.error(f"合成失败：{e}")
                st.stop()
        st.rerun()
    if video:
        st.video(video)
        vc1, vc2 = st.columns(2)
        with open(video, "rb") as f:
            vc1.download_button("⬇️ 下载视频 (mp4)", f, file_name="AI视频.mp4",
                                mime="video/mp4", use_container_width=True)
        if vc2.button("💾 存入我的作品", key="save_to_works",
                      use_container_width=True, type="primary"):
            import shutil
            dst = OUT_DIR / f"{st.session_state.get('proj_name') or '未命名'}_{int(time.time())}.mp4"
            shutil.copy2(video, dst)
            st.success(f"已存入我的作品：{dst.name}")
        if st.button("↻ 清除结果，重新合成", key="redo_compose"):
            st.session_state.pop("video", None)
            st.rerun()

# 每次页面渲染结束自动保存项目（有项目名且有分镜时）
autosave()
