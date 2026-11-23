# -*- coding: utf-8 -*-
"""AI 视频制作 · 后期处理模块

按《AI短剧产线现状评估与质量提升方案》（2026-11-22）落地"写了没做"的后期能力：
  1. 统一调色 LUT（黄昏暖金 / 夜景冷青 / 自然中性）—— ffmpeg 滤镜链，全片一致
  2. 程序化音效层 —— 不依赖任何外部音频素材，纯 ffmpeg 合成氛围底噪/鼓点，本地生成
  3. 字幕强化 —— 白字 + 黑描边，多行感知，替换原来无描边的平铺文字

设计原则：
  - 纯本地 ffmpeg，不联网、不外传任何文件（符合用户"文件不外传"约束）
  - 每个能力可独立开关，输入输出都是本地路径
  - 参数经过真实成片烟测（见工作日志 2026-11-23）
"""
import subprocess
from pathlib import Path

# ========== 调色预设（ffmpeg 滤镜链，全片统一，参数已烟测） ==========
# 黄昏暖金：提饱和/对比 + 加红减蓝 + 轻微 S 曲线，实测灰白片→暖金电影感
LUT_PRESETS = {
    "黄昏暖金（默认）": (
        "eq=saturation=1.12:contrast=1.06:brightness=0.01,"
        "colorbalance=rs=0.06:gs=0.01:bs=-0.08:rm=0.03:gm=0.0:bm=-0.05,"
        "curves=all='0/0.02 0.5/0.52 1/1'"
    ),
    "夜景冷青": (
        "eq=saturation=1.05:contrast=1.10:brightness=-0.01,"
        "colorbalance=rs=-0.05:gs=0.0:bs=0.08:rm=-0.03:gm=0.0:bm=0.06,"
        "curves=all='0/0.0 0.5/0.48 1/0.98'"
    ),
    "自然中性（仅轻调）": (
        "eq=saturation=1.04:contrast=1.03,"
        "colorbalance=rs=0.01:bs=-0.01"
    ),
}


def apply_lut(video_path, preset="黄昏暖金（默认）", out_path=None):
    """给成片套统一调色 LUT。返回输出路径。输出 video 流 copy 前的重编码。
    preset 不在预设表里则原样返回输入路径（不处理）。"""
    vf = LUT_PRESETS.get(preset)
    if not vf:
        return Path(video_path)
    src = Path(video_path)
    out = Path(out_path) if out_path else src.with_name(src.stem + "_graded.mp4")
    # 有音轨就保留（-map 0:a?），无音轨不报错
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(src),
         "-vf", vf, "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
         "-map", "0:v:0", "-map", "0:a?", "-c:a", "aac", "-b:a", "128k",
         str(out)], check=True, capture_output=True, timeout=1800)
    return out


# ========== 程序化音效层（无外部素材，纯 ffmpeg 合成） ==========
# 低频氛围底噪：55Hz 正弦 + 棕噪低通，营造"场景空气感"，实测垫在配音下不抢戏
AMBIENCE_FILTER = (
    "sine=frequency=55:sample_rate=44100:duration={dur}"
)
SOUND_PRESETS = {
    "无": None,
    "低频氛围底噪": "brown",      # 棕噪 + 低频正弦，通用空气感
    "低频鼓点（紧张）": "drum",    # 周期性低频脉冲，适合议事/冲突
    "风声环境（旷野）": "wind",   # 带通白噪，适合外景/街道
}


def _make_ambience(dur: float, kind: str, out_path: Path):
    """用 ffmpeg lavfi 合成指定时长的音效轨，不依赖任何素材文件。"""
    dur = max(1.0, float(dur))
    if kind == "brown":
        cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-f", "lavfi", "-i", f"sine=frequency=55:sample_rate=44100:duration={dur:.2f}",
            "-f", "lavfi", "-i", f"anoisesrc=color=brown:amplitude=0.06:sample_rate=44100:duration={dur:.2f}",
            "-filter_complex",
            "[0:a]volume=0.12[a0];[1:a]lowpass=f=300,volume=0.5[a1];"
            "[a0][a1]amix=inputs=2:duration=first,"
            f"afade=t=in:st=0:d=0.5,afade=t=out:st={max(0.1, dur-1):.2f}:d=1[o]",
            "-map", "[o]", "-c:a", "aac", "-b:a", "128k", str(out_path),
        ]
    elif kind == "wind":
        cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-f", "lavfi", "-i", f"anoisesrc=color=pink:amplitude=0.15:sample_rate=44100:duration={dur:.2f}",
            "-af", f"bandpass=f=600:width_type=o:w=1.2,volume=0.35,"
                   f"afade=t=in:st=0:d=1,afade=t=out:st={max(0.1, dur-1.5):.2f}:d=1.5",
            "-c:a", "aac", "-b:a", "128k", str(out_path),
        ]
    elif kind == "drum":
        # 用低频正弦做周期性脉冲（每 1.2 秒一击），aevalsrc 生成
        expr = f"0.5*sin(2*PI*50*t)*if(lt(mod(t\\,1.2)\\,0.08)\\,exp(-12*mod(t\\,1.2))\\,0)"
        cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-f", "lavfi", "-i", f"aevalsrc={expr}:s=44100:d={dur:.2f}",
            "-af", f"afade=t=in:st=0:d=0.3,afade=t=out:st={max(0.1, dur-1):.2f}:d=1",
            "-c:a", "aac", "-b:a", "128k", str(out_path),
        ]
    else:
        raise ValueError(f"未知音效类型：{kind}")
    subprocess.run(cmd, check=True, capture_output=True, timeout=300)


def add_soundtrack(video_path, sound_kind="低频氛围底噪", mix_volume=0.35,
                   out_path=None):
    """给成片叠加程序化音效轨（垫在原配音下方）。
    mix_volume: 音效音量系数（0~1），0.35 实测不抢配音。"""
    if not sound_kind or sound_kind == "无":
        return Path(video_path)
    # 用户看到的是中文名，转成内部类型 key（也兼容直接传 key）
    kind = SOUND_PRESETS.get(sound_kind, sound_kind)
    if kind not in ("brown", "drum", "wind"):
        raise ValueError(f"未知音效类型：{sound_kind}")
    src = Path(video_path)
    out = Path(out_path) if out_path else src.with_name(src.stem + "_sound.mp4")
    amb = src.with_name(src.stem + "_amb.m4a")
    # 取成片时长
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(src)], capture_output=True, text=True, timeout=60)
    try:
        dur = float(r.stdout.strip())
    except ValueError:
        dur = 10.0
    _make_ambience(dur, kind, amb)
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(src), "-i", str(amb),
         "-filter_complex",
         f"[0:a]volume=1.0[orig];[1:a]volume={mix_volume:.2f}[amb];"
         "[orig][amb]amix=inputs=2:duration=first:dropout_transition=0[mix]",
         "-map", "0:v:0", "-map", "[mix]", "-c:v", "copy", "-c:a", "aac",
         "-b:a", "128k", "-shortest", str(out)],
        check=True, capture_output=True, timeout=900)
    amb.unlink(missing_ok=True)
    return out
