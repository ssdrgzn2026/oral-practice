# -*- coding: utf-8 -*-
"""AI 视频制作：图文视频合成器（Streamlit 单页应用）

流水线：主题 -> LLM 分镜脚本 -> 文生图(Kolors) -> TTS(CosyVoice2) -> ffmpeg 合成 mp4。
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
for d in (IMG_DIR, AUD_DIR, SUB_DIR, OUT_DIR):
    d.mkdir(parents=True, exist_ok=True)

API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1").rstrip("/")
CHAT_MODEL = os.environ.get("OPENAI_MODEL", "Qwen/Qwen3-14B")
TTS_MODEL = os.environ.get("OPENAI_TTS_MODEL", "FunAudioLLM/CosyVoice2-0.5B")
TTS_VOICE = os.environ.get("OPENAI_TTS_VOICE", "FunAudioLLM/CosyVoice2-0.5B:alex")
IMAGE_MODEL = "Kwai-Kolors/Kolors"

SIZES = {"竖屏 576×1024": (576, 1024), "横屏 1024×576": (1024, 576)}

st.set_page_config(page_title="AI 视频制作", page_icon="🎬", layout="wide")
st.title("🎬 AI 视频制作 · 图文视频合成器")
st.caption("主题 → 分镜脚本 → AI 配图 → AI 配音 → 自动合成视频。所有中间产物已缓存，重跑不重复消耗额度。")
st.markdown("<img src='/api/pv?p=video' style='display:none' alt=''>", unsafe_allow_html=True)


def _sha(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def _api_headers():
    return {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}


# ========== 第 2 步：LLM 分镜脚本 ==========
def gen_storyboard(topic: str, n: int) -> list:
    prompt = (
        f"你是一名短视频导演。请为主题「{topic}」写一个 {n} 个分镜的短视频脚本。\n"
        '只输出一个 JSON 对象，格式为 {"shots": [...]}，不要输出其他任何内容。shots 数组每个元素格式：\n'
        '{"desc": "该镜头的画面描述（英文，用于文生图模型，风格电影感、高质量）", '
        '"narration": "该镜头的中文解说词（20~40字）", "seconds": 秒数(数字,3~8)}\n'
        f"shots 数组共 {n} 个元素。"
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
        if desc and narration:
            shots.append({"desc": desc, "narration": narration, "seconds": seconds})
    return shots


# ========== 第 3 步：文生图 ==========
def gen_image(desc: str, size: str) -> Path:
    key = _sha(f"img|{IMAGE_MODEL}|{desc}|{size}")
    out = IMG_DIR / f"{key}.png"
    if out.exists():
        return out
    r = requests.post(f"{BASE_URL}/images/generations", headers=_api_headers(),
                      json={"model": IMAGE_MODEL, "prompt": desc, "size": size}, timeout=300)
    r.raise_for_status()
    item = r.json()["data"][0]
    if item.get("b64_json"):
        out.write_bytes(base64.b64decode(item["b64_json"]))
    else:
        img = requests.get(item["url"], timeout=300)
        img.raise_for_status()
        out.write_bytes(img.content)
    return out


# ========== 第 4 步：TTS 配音 ==========
def gen_audio(narration: str) -> Path:
    key = _sha(f"tts|{TTS_VOICE}|{narration}")
    out = AUD_DIR / f"{key}.mp3"
    if out.exists():
        return out
    r = requests.post(f"{BASE_URL}/audio/speech", headers=_api_headers(),
                      json={"model": TTS_MODEL, "input": narration,
                            "voice": TTS_VOICE, "response_format": "mp3"}, timeout=300)
    r.raise_for_status()
    out.write_bytes(r.content)
    return out


# ========== 第 5 步：字幕渲染 + ffmpeg 合成 ==========
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


def compose_video(shots: list, images: list, audios: list, size_wh, work: Path) -> Path:
    w, h = size_wh
    key = _sha("video|" + "|".join(f"{p.name}{a.name}" for p, a in zip(images, audios)) + f"{w}x{h}")
    final = OUT_DIR / f"{key}.mp4"
    if final.exists():
        return final
    work.mkdir(parents=True, exist_ok=True)
    fps = 25
    segs = []
    for i, (img, aud) in enumerate(zip(images, audios)):
        dur = audio_duration(aud)
        seg = work / f"seg{i}.mp4"
        frames = int(dur * fps) + 1
        # zoompan 缓慢推进 + 音频轨，按配音时长定该镜时长
        vf = (f"scale={w*2}:{h*2},"
              f"zoompan=z='min(1+0.15*on/{frames},1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
              f":d={frames}:s={w}x{h}:fps={fps}")
        subprocess.run(
            ["ffmpeg", "-y", "-loop", "1", "-i", str(img), "-i", str(aud),
             "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p",
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

# ========== 第 1 步：输入 ==========
with st.container(border=True):
    st.subheader("① 输入")
    c1, c2, c3 = st.columns([3, 1, 1])
    topic = c1.text_area("视频主题 / 文案", value=st.session_state.get("topic", ""),
                         height=100, placeholder="例如：三分钟带你看懂黑洞是什么")
    n_shots = c2.slider("分镜数", 3, 5, st.session_state.get("n_shots", 3))
    aspect_label = c3.radio("画幅", list(SIZES.keys()), index=st.session_state.get("aspect_idx", 0))
    if st.button("🚀 开始生成 / 重新运行全流程", type="primary", use_container_width=True):
        if not topic.strip():
            st.error("请先填写视频主题")
            st.stop()
        st.session_state.update(topic=topic, n_shots=n_shots, aspect_idx=list(SIZES).index(aspect_label))
        for k in ("shots", "images", "audios", "video"):
            st.session_state.pop(k, None)
        st.rerun()

if "topic" not in st.session_state:
    st.stop()

size_wh = SIZES[aspect_label]
size_str = f"{size_wh[0]}x{size_wh[1]}"
shots = st.session_state.get("shots")
images = st.session_state.get("images")
audios = st.session_state.get("audios")
video = st.session_state.get("video")

# ========== 第 2 步：分镜脚本 ==========
with st.container(border=True):
    st.subheader("② 分镜脚本")
    if shots is None:
        with st.spinner("LLM 正在撰写分镜脚本…"):
            try:
                shots = gen_storyboard(st.session_state.topic, st.session_state.n_shots)
                st.session_state.shots = shots
            except Exception as e:  # noqa: BLE001
                st.error(f"分镜脚本生成失败：{e}")
                if st.button("↻ 重试本步", key="retry_script"):
                    st.rerun()
                st.stop()
    for i, s in enumerate(shots):
        st.markdown(f"**镜头 {i+1}**（{s['seconds']}s）：{s['narration']}")
        st.caption(f"画面提示词：{s['desc']}")
    if st.button("↻ 重新生成脚本", key="redo_script"):
        for k in ("shots", "images", "audios", "video"):
            st.session_state.pop(k, None)
        st.rerun()

# ========== 第 3 步：文生图 ==========
with st.container(border=True):
    st.subheader("③ 分镜配图（Kolors）")
    if images is None:
        images = []
        prog = st.progress(0.0, text="生成配图中…")
        failed = None
        for i, s in enumerate(shots):
            try:
                images.append(str(gen_image(s["desc"], size_str)))
            except Exception as e:  # noqa: BLE001
                failed = f"镜头 {i+1} 配图失败：{e}"
                break
            prog.progress((i + 1) / len(shots), text=f"已生成 {i+1}/{len(shots)} 张")
        prog.empty()
        if failed:
            st.session_state.images = images or None
            st.error(failed)
            if st.button("↻ 重试本步", key="retry_img"):
                st.rerun()
            st.stop()
        st.session_state.images = images
    cols = st.columns(len(images))
    for i, p in enumerate(images):
        cols[i].image(p, caption=f"镜头 {i+1}", use_container_width=True)
    if st.button("↻ 重新生成配图", key="redo_img"):
        for k in ("images", "audios", "video"):
            st.session_state.pop(k, None)
        st.rerun()

# ========== 第 4 步：TTS 配音 ==========
with st.container(border=True):
    st.subheader("④ 分镜配音（CosyVoice2）")
    if audios is None:
        audios = []
        prog = st.progress(0.0, text="生成配音中…")
        failed = None
        for i, s in enumerate(shots):
            try:
                audios.append(str(gen_audio(s["narration"])))
            except Exception as e:  # noqa: BLE001
                failed = f"镜头 {i+1} 配音失败：{e}"
                break
            prog.progress((i + 1) / len(shots), text=f"已生成 {i+1}/{len(shots)} 段")
        prog.empty()
        if failed:
            st.session_state.audios = audios or None
            st.error(failed)
            if st.button("↻ 重试本步", key="retry_tts"):
                st.rerun()
            st.stop()
        st.session_state.audios = audios
    cols = st.columns(len(audios))
    for i, p in enumerate(audios):
        cols[i].audio(p)
    if st.button("↻ 重新生成配音", key="redo_tts"):
        for k in ("audios", "video"):
            st.session_state.pop(k, None)
        st.rerun()

# ========== 第 5 步：合成视频 ==========
with st.container(border=True):
    st.subheader("⑤ 合成视频")
    if video is None:
        with st.spinner("正在渲染字幕并合成视频（zoompan 运镜 + 配音），请稍候…"):
            try:
                sub_imgs = [render_subtitle(Path(images[i]), shots[i]["narration"], size_wh)
                            for i in range(len(shots))]
                work = OUT_DIR / ("work_" + _sha(st.session_state.topic + str(time.time())))
                video = str(compose_video(shots, sub_imgs, [Path(a) for a in audios], size_wh, work))
                st.session_state.video = video
            except subprocess.CalledProcessError as e:
                st.error(f"ffmpeg 合成失败：{e.stderr.decode(errors='ignore')[-500:] if e.stderr else e}")
                if st.button("↻ 重试本步", key="retry_compose"):
                    st.rerun()
                st.stop()
            except Exception as e:  # noqa: BLE001
                st.error(f"合成失败：{e}")
                if st.button("↻ 重试本步", key="retry_compose2"):
                    st.rerun()
                st.stop()
    st.video(video)
    with open(video, "rb") as f:
        st.download_button("⬇️ 下载视频 (mp4)", f, file_name="AI视频.mp4",
                           mime="video/mp4", use_container_width=True)
    if st.button("↻ 重新合成", key="redo_compose"):
        st.session_state.pop("video", None)
        st.rerun()
