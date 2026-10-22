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
for d in (IMG_DIR, AUD_DIR, SUB_DIR, OUT_DIR, SCRIPT_DIR, PHO_DIR):
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


def _sha(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()[:16]


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
                          "photo": photo})
    return shots


def _parse_manual_shots(text: str) -> list:
    """解析手工录入：优先 JSON（复用 _parse_shots），否则按行解析。
    行格式："画面描述 | 解说词 | 秒数"（秒数可省，默认5）；没有 | 时整行作为解说词，
    画面描述默认取解说词（配图 prompt 可直接用）。行首「镜1：」「镜头2.」「1.」等序号前缀会剥掉。
    """
    text = text.strip()
    if not text:
        return []
    if text[0] in "[{":
        return _parse_shots(text)
    shots = []
    for line in text.splitlines():
        line = re.sub(r"^\s*(?:第\s*)?(?:镜\s*头?\s*)?\d+\s*[：:.、．]\s*", "", line.strip())
        if not line:
            continue
        parts = [p.strip() for p in re.split(r"[|｜]", line)]
        if len(parts) < 2:
            desc, narration, sec_str = parts[0], parts[0], ""
        else:
            desc, narration = parts[0], parts[1]
            sec_str = parts[2] if len(parts) > 2 else ""
        if not narration:
            continue
        try:
            seconds = max(2.0, min(15.0, float(sec_str))) if sec_str else 5.0
        except ValueError:
            seconds = 5.0
        shots.append({"desc": desc, "narration": narration, "seconds": seconds})
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


# ========== 第 5 步：TTS 配音 ==========
def gen_audio(narration: str) -> Path:
    key = _sha(f"tts|{TTS_VOICE}|{narration}")
    out = AUD_DIR / f"{key}.mp3"
    if out.exists():
        return out
    last_err = None
    for attempt in range(4):
        try:
            r = requests.post(f"{BASE_URL}/audio/speech", headers=_api_headers(),
                              json={"model": TTS_MODEL, "input": narration,
                                    "voice": TTS_VOICE, "response_format": "mp3"}, timeout=300)
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


def render_subtitle(img_path: Path, narration: str, size_wh, bar_h_ratio=0.14) -> Path:
    key = _sha(f"sub|{img_path.name}|{narration}|{size_wh}")
    out = SUB_DIR / f"{key}.png"
    if out.exists():
        return out
    w, h = size_wh
    img = Image.open(img_path).convert("RGB").resize((w, h))
    draw = ImageDraw.Draw(img, "RGBA")
    bar_h = int(h * bar_h_ratio)
    draw.rectangle([0, h - bar_h, w, h], fill=(0, 0, 0, 150))
    font_size = max(24, int(h * 0.045))
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
    line_h = int(font_size * 1.35)
    y = h - bar_h + (bar_h - line_h * len(lines)) // 2
    for line in lines:
        lw = draw.textlength(line, font=font)
        draw.text(((w - lw) / 2, y), line, font=font, fill=(255, 255, 255, 255))
        y += line_h
    img.save(out)
    return out


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
    final = OUT_DIR / f"{key}.mp4"
    if final.exists():
        return final
    work.mkdir(parents=True, exist_ok=True)
    fps = 24
    segs = []
    for i, (img, aud) in enumerate(zip(images, audios)):
        dur = audio_duration(aud)
        seg = work / f"seg{i}.mp4"
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
    """📁 我的作品：列出 output 目录下所有已合成视频"""
    st.subheader("📁 我的作品")
    videos = sorted(OUT_DIR.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
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


# ========== 页面导航：制作 / 我的作品 ==========
nav1, nav2, _ = st.columns([1, 1, 4])
page = st.session_state.get("page", "make")
if nav1.button("🎬 视频制作", use_container_width=True,
               type="primary" if page == "make" else "secondary"):
    st.session_state.page = "make"
    st.rerun()
if nav2.button("📁 我的作品", use_container_width=True,
               type="primary" if page == "works" else "secondary"):
    st.session_state.page = "works"
    st.rerun()
if page == "works":
    render_works()
    st.stop()

# ========== 第 1 步：输入主题 ==========
with st.container(border=True):
    st.subheader("① 输入主题或文案")
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
            "每行一个镜头：画面描述 | 解说词 | 秒数（秒数可省，默认5）；"
            "行内没有 | 时整行作为解说词（画面描述自动取解说词）；也可直接粘贴分镜 JSON。"
            "「镜1：」「1.」等序号前缀会自动去掉",
            height=140, key="manual_shots_text",
            placeholder="谢安站在淝水岸边，东晋铠甲，远眺远方 | 公元383年，淝水之战一触即发 | 5")
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
        st.markdown(f"**镜头 {i+1}**（{s['seconds']}s）：{s['narration']}")
        st.caption(f"画面描述：{s['desc']}")
    if st.button("↻ 重新生成脚本", key="redo_script"):
        for k in ("shots", "images", "audios", "video", "seeds", "uploads", "audio_uploads"):
            st.session_state.pop(k, None)
        st.rerun()

# ========== 第 4 步：文生图 ==========
with st.container(border=True):
    st.subheader("④ 分镜配图（Kolors · 中文描述）")
    uploads = st.session_state.setdefault("uploads", {})  # 镜头序号(str) -> 自定义图片路径
    if images is None:
        images = []
        prog = st.progress(0.0, text="生成配图中…")
        failed = None
        for i, s in enumerate(shots):
            try:
                ph = s.get("photo", 0)
                if str(i) in uploads:  # 已上传自定义图片的镜头跳过 AI 生成
                    images.append(uploads[str(i)])
                elif ph >= 1 and ph <= len(photo_paths):  # 分镜指定用参考照片
                    images.append(photo_paths[ph - 1])
                elif not s["desc"].strip():  # 占位镜头（跳过分镜录入）：用占位图
                    images.append(str(placeholder_image(i, size_wh)))
                else:
                    images.append(str(gen_image(s["desc"], size_str)))
            except Exception as e:  # noqa: BLE001
                failed = f"镜头 {i+1} 配图失败：{e}"
                break
            prog.progress((i + 1) / len(shots), text=f"已生成 {i+1}/{len(shots)} 张")
        prog.empty()
        if failed:
            st.session_state.images = images or None
            st.error(failed)
            c1, c2 = st.columns(2)
            if c1.button("↻ 重试本步", key="retry_img"):
                st.rerun()
            if c2.button("⏭ 跳过失败镜头，用占位图继续", key="skip_img_on_fail"):
                while len(images) < len(shots):
                    images.append(str(placeholder_image(len(images), size_wh)))
                st.session_state.images = images
                st.rerun()
            st.stop()
        st.session_state.images = images
    seeds = st.session_state.setdefault("seeds", [0] * len(shots))
    cols = st.columns(len(images))
    for i, p in enumerate(images):
        ph = shots[i].get("photo", 0) if i < len(shots) else 0
        if str(i) in uploads:
            source = "自定义上传"
        elif ph >= 1 and ph <= len(photo_paths) and p == photo_paths[ph - 1]:
            source = "📷 上传照片"
        elif Path(p).name.startswith("ph_"):
            source = "占位图"
        else:
            source = "AI 生成"
        cols[i].image(p, caption=f"镜头 {i+1} · {source}", use_container_width=True)
        if cols[i].button("↻ 重生成此图", key=f"redo_img_{i}", use_container_width=True):
            seeds[i] = int(time.time() * 1000) % (2**31)
            with st.spinner(f"重新生成镜头 {i+1} 配图…"):
                images[i] = str(gen_image(shots[i]["desc"], size_str, seed=seeds[i]))
            uploads.pop(str(i), None)  # AI 重生成后恢复为 AI 来源
            st.session_state.images = images
            st.session_state.pop("video", None)
            st.rerun()
        up = cols[i].file_uploader("上传自定义图片", type=["png", "jpg", "jpeg"],
                                   key=f"upload_{i}", label_visibility="collapsed")
        if up is not None and st.session_state.get(f"uploaded_id_{i}") != up.file_id:
            data = up.getvalue()
            path = IMG_DIR / f"up_{_sha_bytes(data)}.png"
            if not path.exists():
                path.write_bytes(data)
            uploads[str(i)] = str(path)
            images[i] = str(path)
            st.session_state.images = images
            st.session_state[f"uploaded_id_{i}"] = up.file_id
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
                    audios.append(str(gen_audio(s["narration"])))
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
        if up is not None and st.session_state.get(f"uploaded_audio_id_{i}") != up.file_id:
            data = up.getvalue()
            ext = Path(up.name).suffix.lower() or ".mp3"
            path = AUD_DIR / f"up_{_sha_bytes(data)}{ext}"
            if not path.exists():
                path.write_bytes(data)
            audio_uploads[str(i)] = str(path)
            audios[i] = str(path)
            st.session_state.audios = audios
            st.session_state[f"uploaded_audio_id_{i}"] = up.file_id
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
    ph_images = sum(1 for p in (images or []) if Path(p).name.startswith("ph_"))
    ph_audios = sum(1 for p in (audios or []) if Path(p).name.startswith("silence_"))
    img_note = f"（{ph_images} 张占位）" if ph_images else ""
    aud_note = f"（{ph_audios} 段静音占位）" if ph_audios else ""
    st.markdown(
        f"{'✅' if ok_shots else '⬜'} {n} 个分镜　"
        f"{'✅' if ok_images else '⬜'} {len(images) if images else 0}/{n} 张配图{img_note}　"
        f"{'✅' if ok_audios else '⬜'} {len(audios) if audios else 0}/{n} 段配音{aud_note}")
    ready = ok_shots and ok_images and ok_audios
    motion = st.checkbox("启用运镜效果（zoompan 缓慢推进，低性能服务器可关闭提速）",
                         value=True, key="motion")
    if st.button("🎬 合成视频", type="primary", disabled=not ready,
                 use_container_width=True):
        with st.spinner("正在渲染字幕并合成视频，请稍候…"):
            try:
                sub_imgs = [render_subtitle(Path(images[i]), shots[i]["narration"], size_wh)
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
        with open(video, "rb") as f:
            st.download_button("⬇️ 下载视频 (mp4)", f, file_name="AI视频.mp4",
                               mime="video/mp4", use_container_width=True)
        if st.button("↻ 清除结果，重新合成", key="redo_compose"):
            st.session_state.pop("video", None)
            st.rerun()
