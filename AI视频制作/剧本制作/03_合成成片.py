# -*- coding: utf-8 -*-
"""合成成片：镜头视频 + 旁白 + 字幕 -> 最终 MP4。"""
import json
import os
import subprocess

from imageio_ffmpeg import get_ffmpeg_exe

FF = get_ffmpeg_exe()
HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "素材")
SEGS = os.path.join(ASSETS, "_segs")
os.makedirs(SEGS, exist_ok=True)
OUT = os.path.join(HERE, "持械入宋-样片.mp4")

with open(os.path.join(HERE, "分镜样片.json"), encoding="utf-8") as f:
    BOARD = json.load(f)


def srt_time(sec):
    h = int(sec // 3600)
    m = int(sec % 3600 // 60)
    s = int(sec % 60)
    ms = int((sec - int(sec)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def run(cmd):
    print(" ".join(cmd[:3]), "...")
    subprocess.run(cmd, check=True, capture_output=True)


def probe_duration(path):
    r = subprocess.run(
        [FF.replace("ffmpeg", "ffprobe") if "ffprobe" in FF else FF,
         "-i", path], capture_output=True, text=True, encoding="utf-8", errors="ignore")
    for line in r.stderr.splitlines():
        if "Duration" in line:
            t = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = t.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    raise RuntimeError("无法读取时长: " + path)


segs = []
cursor = 0.0
srt_lines = []
for i, shot in enumerate(BOARD["shots"]):
    video = os.path.join(ASSETS, f"{shot['id']}.mp4")
    audio = os.path.join(ASSETS, f"{shot['id']}_旁白.mp3")
    if not os.path.exists(video):
        raise SystemExit(f"缺失视频片段: {video}")
    # 时长取视频与旁白的较大值：旁白更长时用最后一帧静帧补齐视频
    v_dur = probe_duration(video)
    a_dur = probe_duration(audio)
    dur = max(v_dur, a_dur + 0.5)

    seg = os.path.join(SEGS, f"seg{i:02d}.mp4")
    run([FF, "-y", "-i", video, "-i", audio,
         "-filter_complex",
         f"[0:v]tpad=stop_mode=clone:stop={dur - v_dur + 0.1},fps=24[v];"
         f"[1:a]apad=whole_dur={dur}[a]",
         "-map", "[v]", "-map", "[a]",
         "-t", str(dur),
         "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-ar", "44100", seg])
    segs.append(seg)

    srt_lines += [str(i + 1),
                  f"{srt_time(cursor)} --> {srt_time(cursor + a_dur)}",
                  shot["narration"], ""]
    cursor += dur

# 拼接
lst = os.path.join(SEGS, "list.txt")
with open(lst, "w", encoding="utf-8") as f:
    for s in segs:
        f.write(f"file '{s}'\n")
merged = os.path.join(SEGS, "merged.mp4")
run([FF, "-y", "-f", "concat", "-safe", "0", "-i", lst,
     "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", merged])

# 烧字幕
srt_path = os.path.join(SEGS, "字幕.srt")
with open(srt_path, "w", encoding="utf-8") as f:
    f.write("\n".join(srt_lines))
srt_rel = os.path.relpath(srt_path, HERE).replace("\\", "/")
run([FF, "-y", "-i", merged,
     "-vf", f"subtitles='{srt_rel}':force_style='FontSize=14,Outline=2'",
     "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "copy", OUT])
print("成片:", OUT)
