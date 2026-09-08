"""文件格式转换核心模块"""
import os
import re
import io
import zipfile
from collections import Counter
from pathlib import Path
from typing import List, Tuple, Optional
import tempfile
import shutil

# PDF
import fitz  # PyMuPDF
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.enum.table import WD_ROW_HEIGHT_RULE, WD_ALIGN_VERTICAL
from docx.enum.section import WD_SECTION

# pdf2docx 延迟导入（避免 OpenCV 在云端初始化失败导致整个系统崩溃）
_Converter = None
def _get_pdf2docx_converter():
    global _Converter
    if _Converter is None:
        from pdf2docx import Converter
        _Converter = Converter
    return _Converter

# Image
from PIL import Image

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def _ensure_tesseract():
    """确保 Tesseract 路径已配置（每次调用前执行）"""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        candidates = [
            r"D:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]
        for path in candidates:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                return True
        return False

_init_ok = _ensure_tesseract()


def _clean_filename(name: str) -> str:
    """清理文件名中的非法字符"""
    for ch in ['\\', '/', ':', '*', '?', '"', '<', '>', '|']:
        name = name.replace(ch, '_')
    return name


def _sanitize_xml_text(text: str) -> str:
    """移除 XML 不兼容的字符，防止 python-docx 报错。
    XML 1.0 合法字符：\\t \\n \\r、U+0020–U+D7FF、U+E000–U+FFFD、U+10000 以上。
    （NULL、控制字符、U+FFFE/U+FFFF 等非字符都会被剔除）"""
    out = []
    for ch in text:
        o = ord(ch)
        if ch in "\t\n\r" or 0x20 <= o <= 0xD7FF or 0xE000 <= o <= 0xFFFD or 0x10000 <= o <= 0x10FFFF:
            out.append(ch)
    return "".join(out)


def _is_cjk_char(ch: str) -> bool:
    """判断是否为中日韩字符或全角标点（跨行拼接时不加空格）"""
    return ('一' <= ch <= '鿿' or
            '　' <= ch <= '〿' or
            '＀' <= ch <= '￯')


def _line_join_sep(prev_text: str, next_text: str) -> str:
    """跨行拼接的分隔符：中文之间直接拼接，西文单词之间保留空格"""
    if prev_text and next_text and (_is_cjk_char(prev_text[-1]) or _is_cjk_char(next_text[0])):
        return ""
    return " "


def _map_cjk_font(pdf_font_name: str) -> str:
    """把 PDF 字体名映射为常见的中文 Word 字体。
    PDF 内嵌字体名常带子集前缀（如 ABCDEE+FangSong_GB2312），用子串匹配。"""
    name = pdf_font_name.lower()
    if "fangsong" in name or "仿宋" in pdf_font_name or "仿" in pdf_font_name:
        return "仿宋"
    if "kai" in name or "楷" in pdf_font_name:
        return "楷体"
    if "hei" in name or "黑" in pdf_font_name:
        return "黑体"
    return "宋体"


def _set_run_scale(run, scale_pct: int):
    """设置 run 的横向缩放百分比（w:w），用于还原窄体字体的实际宽度"""
    rPr = run._element.get_or_add_rPr()
    w = OxmlElement("w:w")
    w.set(qn("w:val"), str(scale_pct))
    rPr.append(w)


def _split_by_stroke(text: str, x0: float, x1: float, y_mid: float, stroked_boxes: list) -> list:
    """按描边区域把 span 文本拆成 (子串, 是否加粗) 列表。
    用于识别 PDF 的假粗体（填充+描边）；CJK 等宽，按字符中心位置判断。"""
    n = len(text)
    if n == 0:
        return [(text, False)]
    cw = (x1 - x0) / n
    flags = []
    for i in range(n):
        pt = fitz.Point(x0 + (i + 0.5) * cw, y_mid)
        flags.append(any(rb.contains(pt) for rb in stroked_boxes))
    if not any(flags):
        return [(text, False)]
    if all(flags):
        return [(text, True)]
    runs = []
    cur = flags[0]
    buf = ""
    for ch, f in zip(text, flags):
        if f == cur:
            buf += ch
        else:
            runs.append((buf, cur))
            buf = ch
            cur = f
    runs.append((buf, cur))
    return runs


def _cluster_edges(values, tol=3.0):
    """把相近的坐标值聚成一条表格边线（容差 tol 磅）"""
    edges = []
    for v in sorted(values):
        if not edges or v - edges[-1] > tol:
            edges.append(float(v))
    return edges


def _edge_index(edges, v, tol=3.0):
    """坐标 v 落在第几条边线"""
    for i, e in enumerate(edges):
        if abs(e - v) <= tol:
            return i
    return min(range(len(edges)), key=lambda i: abs(edges[i] - v))


def _get_unique_path(filename: str) -> Path:
    """生成唯一输出路径，避免覆盖"""
    base = OUTPUT_DIR / filename
    if not base.exists():
        return base
    stem = base.stem
    suffix = base.suffix
    counter = 1
    while True:
        new_name = f"{stem}_{counter}{suffix}"
        new_path = OUTPUT_DIR / new_name
        if not new_path.exists():
            return new_path
        counter += 1


# ==================== PDF → 图像 ====================

def pdf_to_images(
    pdf_bytes: bytes,
    output_format: str = "png",
    dpi: int = 200,
    page_range: str = "all"
) -> List[Path]:
    """
    将PDF页面转换为图像
    page_range: "all" 或 "1,3,5" 或 "1-5"
    返回生成的文件路径列表
    """
    fmt = output_format.lower()
    ext_map = {"png": "png", "jpg": "jpg", "jpeg": "jpg", "webp": "webp",
               "tiff": "tiff", "tif": "tiff", "bmp": "bmp"}
    ext = ext_map.get(fmt, "png")
    
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    output_paths = []
    
    # 解析页码范围
    if page_range.strip().lower() == "all":
        pages = list(range(len(doc)))
    else:
        pages = _parse_page_range(page_range, len(doc))
    
    for page_num in pages:
        page = doc[page_num]
        # 使用矩阵提高分辨率
        mat = fitz.Matrix(dpi/72, dpi/72)
        pix = page.get_pixmap(matrix=mat)
        
        # 转换为PIL图像以支持更多格式
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        if ext == "jpg":
            img = img.convert("RGB")
        
        filename = f"page_{page_num + 1}.{ext}"
        out_path = _get_unique_path(filename)
        img.save(out_path, quality=95 if ext == "jpg" else None)
        output_paths.append(out_path)
    
    doc.close()
    return output_paths


def pdf_to_images_zip(
    pdf_bytes: bytes,
    output_format: str = "png",
    dpi: int = 200,
    page_range: str = "all"
) -> Path:
    """将PDF页面转为图像并打包为ZIP"""
    paths = pdf_to_images(pdf_bytes, output_format, dpi, page_range)
    if not paths:
        return None
    
    zip_path = _get_unique_path("converted_images.zip")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for p in paths:
            zf.write(p, p.name)
    
    # 清理单独的图片文件，只保留zip
    for p in paths:
        p.unlink()
    
    return zip_path


# ==================== 图像 → PDF ====================

def images_to_pdf(
    image_files: List[bytes],
    image_names: List[str],
    output_mode: str = "merge"
) -> Path:
    """
    将图像转为PDF
    output_mode: "merge" 合并为单PDF, "separate" 各自独立
    """
    if output_mode == "separate":
        # 各自独立输出，打包zip
        pdf_paths = []
        for img_bytes, name in zip(image_files, image_names):
            img = Image.open(io.BytesIO(img_bytes))
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            stem = Path(name).stem
            out_path = _get_unique_path(f"{stem}.pdf")
            img.save(out_path, "PDF", resolution=100.0)
            pdf_paths.append(out_path)
        
        if len(pdf_paths) == 1:
            return pdf_paths[0]
        
        zip_path = _get_unique_path("converted_pdfs.zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for p in pdf_paths:
                zf.write(p, p.name)
                p.unlink()
        return zip_path
    else:
        # 合并为单个PDF
        doc = fitz.open()
        for img_bytes, name in zip(image_files, image_names):
            img = Image.open(io.BytesIO(img_bytes))
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            # 临时保存为PNG再插入PDF（保持质量）
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                img.save(tmp.name, "PNG")
                tmp_path = tmp.name
            
            rect = fitz.Rect(0, 0, img.width, img.height)
            page = doc.new_page(width=img.width, height=img.height)
            page.insert_image(rect, filename=tmp_path)
            os.unlink(tmp_path)
        
        out_path = _get_unique_path("merged_images.pdf")
        doc.save(out_path)
        doc.close()
        return out_path


# ==================== PDF → Word ====================

def _extract_text_rebuild(pdf_bytes: bytes) -> tuple[str, Path]:
    """
    用 PyMuPDF 提取文本并用 python-docx 重建文档。
    按行提取后根据缩进和行距把视觉行合并成自然段，保留加粗等样式，
    使 Word 中的版式（首行缩进、行距、加粗条款号）贴近原文。
    返回 (提取到的文本总内容, 输出文件路径)。
    如果提取到的文本太少，返回 ("", None) 让调用方 fallback 到图片模式。
    """
    # 匹配页脚页码，如 "- 1 -"、"— 12 —"
    pn_pattern = re.compile(r"^[-—–\s]*\d{1,4}[-—–\s]*$")

    doc_pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_text = ""
    pages_lines = []  # 每页: [行信息dict]
    page_size = None
    footer_info = []  # 页脚页码: [{page, num, text, y1, size}]
    tables_found = []  # 表格: [{page, y0, y1, rows, cols, xs, ys, cells}]
    images_found = []  # 图形区域（流程图等）: [{page, y0, y1, x0, w, png}]
    page_pitches = []  # 每页正文行距中位数
    page_sizes = []  # 每页 (宽, 高)，横版页与竖版页可能不同

    for page_idx, page in enumerate(doc_pdf):
        if page_size is None:
            page_size = (page.rect.width, page.rect.height)
        page_h = page.rect.height
        lines = []
        # 描边加粗（假粗体）检测：texttrace 中带线宽的描边 span
        stroked_boxes = []
        try:
            for ts in page.get_texttrace():
                if ts.get("linewidth"):
                    stroked_boxes.append(fitz.Rect(ts["bbox"]))
        except Exception:
            pass
        # 流程图/示意图检测：页面含斜线、贝塞尔曲线或小面积填充（箭头头部）
        # 的矢量图形时，判定为图形区域，整体渲染为图片插入，不走文字/表格流程
        # （流程图的方框会被表格识别误判成表格，拆散后完全错乱）
        diagram_rect = None
        try:
            drawings = page.get_drawings()
        except Exception:
            drawings = []
        if drawings:
            complex_found = False
            for d in drawings:
                for it in d["items"]:
                    op = it[0]
                    if op in ("c", "qu"):  # 曲线 / 四边形
                        complex_found = True
                        break
                    if op == "l":  # 非水平/垂直的斜线
                        p1, p2 = it[1], it[2]
                        if abs(p1.x - p2.x) > 1 and abs(p1.y - p2.y) > 1:
                            complex_found = True
                            break
                    # 小面积填充（箭头头部）；大面积填充是表格底纹，不算
                    if op == "re" and d.get("type") in ("f", "fs") and it[1].get_area() < 50:
                        complex_found = True
                        break
                if complex_found:
                    break
            if complex_found:
                diagram_rect = None
                for d in drawings:
                    # 线条的 bbox 宽/高为 0，fitz 视为空矩形会被并集忽略，先膨胀
                    r = fitz.Rect(d["rect"]) + (-1, -1, 1, 1)
                    diagram_rect = r if diagram_rect is None else diagram_rect | r
                # 向外扩展一圈，把图形旁边的标注文字（如“是/否/修改”）也纳入
                diagram_rect = (diagram_rect + (-20, -10, 20, 10)) & page.rect
        for b in page.get_text("dict").get("blocks", []):
            if b.get("type") != 0:  # 跳过图片块
                continue
            for line in b.get("lines", []):
                spans = []  # [(文本, 字号, 加粗, 中文字体, 横向缩放%)]
                max_size = 0
                prev_span_x1 = None
                for span in line.get("spans", []):
                    t = _sanitize_xml_text(span.get("text", ""))
                    if not t.strip():
                        continue
                    size = span.get("size", 11)
                    flags = span.get("flags", 0)
                    font_name = span.get("font", "")
                    bold = bool(flags & 16) or "bold" in font_name.lower()
                    cjk_font = _map_cjk_font(font_name)
                    sx0, sy0, sx1, sy1 = span.get("bbox", (0, 0, 0, 0))
                    # 原字体的横向缩放率：PDF 里有窄体字体（如小标宋约 0.9em），
                    # 替换成 Word 字体会变宽导致折行，需要等比压缩还原。
                    # 注意：只压缩不放大——两端对齐的行在 PDF 里被拉伸过，
                    # 若按实测宽度放大，Word 里每行会少排几个字、页面对不上
                    stripped = t.strip()
                    n_cjk = sum(1 for ch in stripped if ord(ch) > 0x2E7F)
                    n_other = len(stripped) - n_cjk
                    est = (n_cjk + n_other * 0.55) * size
                    scale = int(round((sx1 - sx0) / est * 100)) if est > 0 else 100
                    scale = max(min(scale, 100), 60)
                    # 相邻 span 之间有明显空隙时补一个空格（如“第三条 本办法”的间隔）
                    if (prev_span_x1 is not None and spans
                            and sx0 - prev_span_x1 > size * 0.25
                            and not spans[-1][0].endswith((" ", "　"))
                            and not t.startswith((" ", "　"))):
                        prev_t = spans[-1]
                        spans[-1] = (prev_t[0] + " ", prev_t[1], prev_t[2], prev_t[3], prev_t[4])
                    # 假粗体（描边）按字符位置拆分加粗/普通子段
                    if not bold and stroked_boxes:
                        for sub_t, sub_bold in _split_by_stroke(t, sx0, sx1, (sy0 + sy1) / 2, stroked_boxes):
                            if sub_t:
                                spans.append((sub_t, size, sub_bold, cjk_font, scale))
                    else:
                        spans.append((t, size, bold, cjk_font, scale))
                    prev_span_x1 = sx1
                    max_size = max(max_size, size)
                if not spans:
                    continue
                line_text = "".join(s[0] for s in spans).strip()
                if not line_text:
                    continue
                x0, y0 = line["bbox"][0], line["bbox"][1]
                # 页码（如 "- 1 -"）：记录样式后从正文剔除，改由 Word 页脚实现。
                # 带装饰符号（- — –）的在页面任意位置都识别；
                # 纯数字的只认页面中下部，避免误伤正文里的独立数字行
                if pn_pattern.match(line_text) and (
                    y0 > page_h * 0.5 or re.search(r"[-—–]", line_text)
                ):
                    m = re.search(r"\d{1,4}", line_text)
                    footer_info.append({
                        "page": page_idx, "num": int(m.group()),
                        "text": line_text,
                        "y1": line["bbox"][3], "size": max_size,
                    })
                    continue
                lines.append({
                    "spans": spans, "text": line_text,
                    "x0": x0, "x1": line["bbox"][2],
                    "y0": y0, "y1": line["bbox"][3], "size": max_size,
                })
                total_text += line_text + "\n"
        # 识别表格区域：表格内的文字行不走段落流程，单独生成 Word 表格。
        # 与图形区域（流程图等）重叠的"表格"是误识别，跳过
        page_tables = []
        try:
            for tab in page.find_tables().tables:
                if diagram_rect is not None and fitz.Rect(tab.bbox).intersects(diagram_rect):
                    continue
                page_tables.append(tab)
        except Exception:
            pass
        if page_tables or diagram_rect is not None:
            kept = []
            for ln in lines:
                cx = (ln["x0"] + ln["x1"]) / 2
                cy = (ln["y0"] + ln["y1"]) / 2
                pt = fitz.Point(cx, cy)
                in_special = any(
                    fitz.Rect(tab.bbox).contains(pt)
                    for tab in page_tables
                )
                if not in_special and diagram_rect is not None:
                    in_special = diagram_rect.contains(pt)
                if not in_special:
                    kept.append(ln)
            lines = kept
            for tab in page_tables:
                # 用单元格矩形重建网格，保留合并单元格信息
                rects = [fitz.Rect(r) for r in tab.cells]
                xs = _cluster_edges([r.x0 for r in rects] + [r.x1 for r in rects])
                ys = _cluster_edges([r.y0 for r in rects] + [r.y1 for r in rects])
                cells_out = []
                for rect in rects:
                    c1 = _edge_index(xs, rect.x0)
                    c2 = _edge_index(xs, rect.x1) - 1
                    r1 = _edge_index(ys, rect.y0)
                    r2 = _edge_index(ys, rect.y1) - 1
                    # 逐单元格提取文字和字号（表格字号常比正文小）；
                    # 同一水平位置的碎片横向拼接（如“姓 名”），不同行才换行
                    clines = []
                    for cb in page.get_text("dict", clip=rect).get("blocks", []):
                        if cb.get("type") != 0:
                            continue
                        for cl in cb.get("lines", []):
                            lt = "".join(cs.get("text", "") for cs in cl.get("spans", []))
                            if lt.strip():
                                clines.append((cl["bbox"][1], cl["bbox"][0],
                                               _sanitize_xml_text(lt).strip(),
                                               max(cs.get("size", 11) for cs in cl["spans"])))
                    clines.sort()
                    ctexts = []
                    csize = 0
                    for y0, x0, lt, sz in clines:
                        if ctexts and abs(y0 - ctexts[-1][0]) < sz * 0.5:
                            ctexts[-1][2] += " " + lt
                        else:
                            ctexts.append([y0, x0, lt, sz])
                        csize = max(csize, sz)
                    # 每行记录 (文本, x0)，供还原行级缩进
                    cell_lines = [(ct[2], ct[1]) for ct in ctexts]
                    cells_out.append((r1, c1, r2, c2, rect.x0, cell_lines, csize))
                tables_found.append({
                    "page": page_idx,
                    "y0": tab.bbox[1], "y1": tab.bbox[3],
                    "rows": max(len(ys) - 1, 0), "cols": max(len(xs) - 1, 0),
                    "xs": xs, "ys": ys,
                    "cells": cells_out,
                })
        # 图形区域（流程图等）整体渲染为图片，插入 Word 保持原样
        if diagram_rect is not None:
            clip = (diagram_rect + (-4, -4, 4, 4)) & page.rect
            pix = page.get_pixmap(dpi=200, clip=clip)
            images_found.append({
                "page": page_idx, "y0": clip.y0, "y1": clip.y1,
                "x0": clip.x0, "w": clip.width, "png": pix.tobytes("png"),
            })
        lines.sort(key=lambda l: (l["y0"], l["x0"]))
        # 合并同一水平位置的行碎片（同行的不同字体片段会被 PyMuPDF 拆成多个
        # 行对象，如“第一条”+正文；不合并会导致段落被切碎、居中误判）
        merged_lines = []
        for ln in lines:
            if merged_lines and abs(ln["y0"] - merged_lines[-1]["y0"]) < merged_lines[-1]["size"] * 0.5:
                m = merged_lines[-1]
                left, right = (m, ln) if ln["x0"] >= m["x0"] else (ln, m)
                gap = right["x0"] - left["x1"]
                lspans = list(left["spans"])
                if (gap > left["size"] * 0.25
                        and not lspans[-1][0].endswith((" ", "　"))
                        and not right["spans"][0][0].startswith((" ", "　"))):
                    t = lspans[-1]
                    lspans[-1] = (t[0] + " ", t[1], t[2], t[3], t[4])
                m["spans"] = lspans + list(right["spans"])
                m["x0"] = left["x0"]
                m["x1"] = max(m["x1"], ln["x1"])
                m["y1"] = max(m["y1"], ln["y1"])
                m["size"] = max(m["size"], ln["size"])
                m["text"] = "".join(s[0] for s in m["spans"]).strip()
            else:
                merged_lines.append(dict(ln, spans=list(ln["spans"])))
        pages_lines.append(merged_lines)
        page_sizes.append((page.rect.width, page.rect.height))
        # 本页行距中位数（不同页的行距可能不同，按页还原避免高度累积误差）
        pg_pitches = []
        for prev_ln, cur_ln in zip(merged_lines, merged_lines[1:]):
            dy = cur_ln["y0"] - prev_ln["y0"]
            if 0 < dy < prev_ln["size"] * 2.5:
                pg_pitches.append(dy)
        pg_pitches.sort()
        page_pitches.append(pg_pitches[len(pg_pitches) // 2] if pg_pitches else 0)
    doc_pdf.close()

    # 阈值：如果总字符数太少，认为是扫描件，回退到图片模式
    if len(total_text.strip()) < 100:
        return "", None

    all_lines = [ln for pg in pages_lines for ln in pg]

    # 正文左右边界取众数（按 2pt 分桶）：避免横向表格页等少数页
    # 的极值坐标把页边距带偏；横版页与竖版页分开统计
    def _mode_edges(lines):
        if not lines:
            return None
        x0b = Counter(round(l["x0"] / 2) * 2 for l in lines)
        x1b = Counter(round(l["x1"] / 2) * 2 for l in lines)
        return x0b.most_common(1)[0][0], x1b.most_common(1)[0][0]

    port_lines = [ln for i, pg in enumerate(pages_lines)
                  if page_sizes[i][0] <= page_sizes[i][1] for ln in pg]
    land_lines = [ln for i, pg in enumerate(pages_lines)
                  if page_sizes[i][0] > page_sizes[i][1] for ln in pg]
    port_edges = _mode_edges(port_lines) or (0, 0)
    left_margin = port_edges[0]
    # 右边界取 97 分位：两端对齐的行右缘有波动且有标点悬挂，
    # 众数会偏左，导致 Word 版心比原文窄、每行少排 1-2 个字
    port_x1 = sorted(ln["x1"] for ln in port_lines)
    text_right = port_x1[min(int(len(port_x1) * 0.97), len(port_x1) - 1)] if port_x1 else port_edges[1]
    # 横版页行数少，众数不可靠，直接取内容（含表格）的最左/最右
    land_x0 = [ln["x0"] for ln in land_lines]
    land_x1 = [ln["x1"] for ln in land_lines]
    for t in tables_found:
        if page_sizes[t["page"]][0] > page_sizes[t["page"]][1]:
            land_x0.append(t["xs"][0])
            land_x1.append(t["xs"][-1])
    land_left = min(land_x0) if land_x0 else left_margin
    land_right = max(land_x1) if land_x1 else text_right

    # 正文字号：所有行字号的中位数
    sorted_size = sorted(ln["size"] for ln in all_lines)
    body_size = sorted_size[len(sorted_size) // 2]

    # 正常行距：同页相邻行 y 间距的中位数
    pitches = []
    for pg in pages_lines:
        for prev, cur in zip(pg, pg[1:]):
            dy = cur["y0"] - prev["y0"]
            if 0 < dy < prev["size"] * 2.5:
                pitches.append(dy)
    pitches.sort()
    median_pitch = pitches[len(pitches) // 2] if pitches else body_size * 1.5

    # ---- 把视觉行合并为自然段 ----
    # 新段落的判定：首行缩进（x0 明显大于左边界）、行距明显变大、跨页。
    # 为保证 PDF 一页对应 Word 一页，跨页的行不并入上一段。
    paragraphs = []  # [{spans, size, indented, cx, pw, page, y0, last_y0}]
    prev = None  # (行dict, 页码索引)
    for page_idx, pg in enumerate(pages_lines):
        for ln in pg:
            indented = ln["x0"] > left_margin + body_size * 0.8
            # 大字号行（标题）不按缩进拆分，多行标题本就是一个段落
            is_big = ln["size"] > body_size * 1.3
            new_para = True
            if prev is not None and prev[1] == page_idx:
                gap = ln["y0"] - prev[0]["y0"]
                size_changed = abs(ln["size"] - prev[0]["size"]) > 2
                new_para = ((indented and not is_big)
                            or gap > median_pitch * 1.6
                            or size_changed)
            if new_para:
                # 去掉段首的全角空格，改用 Word 首行缩进实现
                spans = list(ln["spans"])
                first = spans[0][0].lstrip("　 ")
                if first != spans[0][0]:
                    indented = True
                spans[0] = (first, spans[0][1], spans[0][2], spans[0][3], spans[0][4])
                paragraphs.append({
                    "spans": spans, "size": ln["size"],
                    "indented": indented,
                    "x0": ln["x0"],
                    "cx": (ln["x0"] + ln["x1"]) / 2,
                    "lw": ln["x1"] - ln["x0"],
                    "pw": page_sizes[page_idx][0] if page_sizes else 0,
                    "page": page_idx,
                    "y0": ln["y0"], "last_y0": ln["y0"],
                })
            else:
                para = paragraphs[-1]
                cur_text = "".join(s[0] for s in para["spans"])
                sep = _line_join_sep(cur_text, ln["text"])
                spans = list(ln["spans"])
                if sep:
                    spans[0] = (sep + spans[0][0], spans[0][1], spans[0][2], spans[0][3], spans[0][4])
                para["spans"].extend(spans)
                para["size"] = max(para["size"], ln["size"])
                para["last_y0"] = ln["y0"]
            prev = (ln, page_idx)

    # ---- 重建 Word 文档 ----
    docx = Document()

    # 页面尺寸、页边距与 PDF 实际内容区域保持一致（保证一页对应一页）
    if page_size:
        section = docx.sections[0]
        section.page_width = Pt(page_size[0])
        section.page_height = Pt(page_size[1])
        top_y = min(ln["y0"] for ln in all_lines)
        bottom_y = max(ln["y1"] for ln in all_lines)
        # 固定行距的行盒比文字高（行距-字号），文字在行盒中偏下：
        # 顶边距要减去这部分偏移的一半，底边距要预留一个完整行盒
        line_extra = median_pitch - body_size
        top_margin_pt = max(top_y - line_extra * 0.5 - 1, 0)
        bottom_margin_pt = max(page_size[1] - bottom_y - line_extra - 1, 0)
        left_margin_pt = max(left_margin - 2, 0)
        right_margin_pt = max(page_size[0] - text_right - 2, 0)
        section.top_margin = Pt(top_margin_pt)
        section.bottom_margin = Pt(bottom_margin_pt)
        section.left_margin = Pt(left_margin_pt)
        section.right_margin = Pt(right_margin_pt)
        # 页眉页脚距离调小，避免挤压正文区域
        section.header_distance = Pt(5)
        section.footer_distance = Pt(5)
        content_top = top_y
    else:
        top_margin_pt = bottom_margin_pt = left_margin_pt = right_margin_pt = 0
        content_top = 0

    # ---- 页脚页码：样式与 PDF 一致（如 "- 1 -"），用 Word 页码域自动编号 ----
    footer_dist_pt = 5
    page_offset = 0
    footer_by_page = {}

    def _fill_footer(footer_obj, fentry):
        """按 PDF 页脚样式填充 Word 页脚：装饰字符 + 页码域"""
        m = re.search(r"\d{1,4}", fentry["text"])
        prefix = fentry["text"][:m.start()]
        suffix = fentry["text"][m.end():]
        fp = footer_obj.paragraphs[0]
        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        fp.paragraph_format.space_before = Pt(0)
        fp.paragraph_format.space_after = Pt(0)

        def _style(run):
            run.font.size = Pt(round(fentry["size"] * 2) / 2)
            run.font.name = "Times New Roman"
            run._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")

        if prefix:
            _style(fp.add_run(prefix))
        fld = fp.add_run()
        b = OxmlElement("w:fldChar")
        b.set(qn("w:fldCharType"), "begin")
        ins = OxmlElement("w:instrText")
        ins.set(qn("xml:space"), "preserve")
        ins.text = "PAGE"
        e = OxmlElement("w:fldChar")
        e.set(qn("w:fldCharType"), "end")
        fld._r.append(b)
        fld._r.append(ins)
        fld._r.append(e)
        _style(fld)
        if suffix:
            _style(fp.add_run(suffix))

    if footer_info and page_size:
        section = docx.sections[0]
        first_footer = footer_info[0]
        # 起始页号偏移：PDF 第 N 个物理页显示 num，则偏移 = num - N
        # （例如封面不编号、第 2 物理页显示 "- 1 -" 时偏移为 0）
        page_offset = first_footer["num"] - first_footer["page"]
        footer_by_page = {f["page"]: f for f in footer_info}
        pg_num_type = OxmlElement("w:pgNumType")
        pg_num_type.set(qn("w:start"), str(page_offset))
        section._sectPr.append(pg_num_type)
        # PDF 首页无页码时，Word 首页也不显示页脚
        if first_footer["page"] > 0:
            section.different_first_page_header_footer = True
        # 页脚位置尽量与原文一致，但不能侵入正文区域
        # （否则 Word 会压缩正文高度，导致每页内容错位跨页）
        dist = page_size[1] - first_footer["y1"]
        max_dist = bottom_margin_pt - first_footer["size"] * 1.5
        footer_dist_pt = max(min(dist, max_dist), 5)
        section.footer_distance = Pt(footer_dist_pt)
        _fill_footer(section.footer, first_footer)

    # 统计字号分布，找出标题和正文的分界线
    all_sizes = sorted(p["size"] for p in paragraphs)
    if all_sizes:
        avg_size = sum(all_sizes) / len(all_sizes)
        max_size = all_sizes[-1]
        # 大于平均 + 20% 且接近最大值的认为是标题
        title_threshold = max(avg_size * 1.2, max_size * 0.75)
    else:
        title_threshold = 14

    # 正文字体：所有 span 中出现最多的中文字体（用于表格单元格）
    font_counter = Counter(s[3] for p in paragraphs for s in p["spans"])
    body_cjk_font = font_counter.most_common(1)[0][0] if font_counter else "宋体"

    # 段落、表格、图形按 (页码, 纵向位置) 统一排序，保持原版式顺序
    items = ([("para", p) for p in paragraphs]
             + [("table", t) for t in tables_found]
             + [("image", i) for i in images_found])
    items.sort(key=lambda it: (it[1]["page"], it[1]["y0"]))

    prev_page = 0
    prev_last_y0 = None
    cur_size = page_sizes[0] if page_sizes else None
    cur_sec_left = left_margin_pt  # 当前分节的左边距（表格定位以此为基准）
    for kind, item in items:
        # 页面方向/尺寸变化（如横向表格页）→ 新建对应设置的分节
        section_added = False
        if page_sizes:
            w, h = page_sizes[item["page"]]
            if cur_size and abs(w - cur_size[0]) > 5:
                new_sec = docx.add_section(WD_SECTION.NEW_PAGE)
                # add_section 会在前文末尾留下一个空段落承载分节符，
                # 压到最小行高，避免把上一页内容挤到下一页
                brp = docx.paragraphs[-1]
                brpf = brp.paragraph_format
                brpf.space_before = Pt(0)
                brpf.space_after = Pt(0)
                brpf.line_spacing_rule = WD_LINE_SPACING.EXACTLY
                brpf.line_spacing = Pt(1)
                new_sec.page_width = Pt(w)
                new_sec.page_height = Pt(h)
                new_sec.top_margin = Pt(top_margin_pt)
                new_sec.bottom_margin = Pt(bottom_margin_pt)
                if w > h:  # 横版页：用横版内容边界
                    sec_left = max(land_left - 2, 0)
                    sec_right = max(w - land_right - 2, 0)
                else:
                    sec_left = left_margin_pt
                    sec_right = right_margin_pt
                new_sec.left_margin = Pt(sec_left)
                new_sec.right_margin = Pt(sec_right)
                new_sec.header_distance = Pt(5)
                new_sec.footer_distance = Pt(footer_dist_pt)
                # 每个分节显式设定起始页号（延续原始编号），并按该节首页
                # 的页脚样式设置页脚；该页无页脚则本节不显示页脚
                if footer_info and page_size:
                    pg = OxmlElement("w:pgNumType")
                    pg.set(qn("w:start"), str(item["page"] + page_offset))
                    new_sec._sectPr.append(pg)
                    new_sec.footer.is_linked_to_previous = False
                    fentry = footer_by_page.get(item["page"])
                    if fentry:
                        _fill_footer(new_sec.footer, fentry)
                cur_size = (w, h)
                cur_sec_left = sec_left
                section_added = True
        if kind == "image":
            # 图形区域（流程图等）：按原位置插入渲染图片
            need_break = (item["page"] != prev_page
                          or (prev_last_y0 is None and item["page"] > 0)) and not section_added
            p = docx.add_paragraph()
            if need_break:
                p.add_run().add_break(WD_BREAK.PAGE)
            if prev_last_y0 is None or item["page"] != prev_page:
                space_before = max(item["y0"] - content_top, 0)
            else:
                space_before = max(item["y0"] - prev_last_y0 - median_pitch, 0)
            pf = p.paragraph_format
            pf.space_before = Pt(space_before)
            pf.space_after = Pt(0)
            pf.left_indent = Pt(max(item["x0"] - cur_sec_left, 0))
            p.add_run().add_picture(io.BytesIO(item["png"]), width=Pt(item["w"]))
            prev_page = item["page"]
            prev_last_y0 = item["y1"] - median_pitch
            continue
        if kind == "table":
            n_rows, n_cols = item["rows"], item["cols"]
            if n_rows and n_cols and item["cells"]:
                need_break = (item["page"] != prev_page
                              or (prev_last_y0 is None and item["page"] > 0)) and not section_added
                if need_break:
                    # 表格无法内嵌分页符，用一个极小的空段落换页
                    br = docx.add_paragraph()
                    br.add_run().add_break(WD_BREAK.PAGE)
                    brpf = br.paragraph_format
                    brpf.space_before = Pt(0)
                    brpf.space_after = Pt(0)
                    brpf.line_spacing_rule = WD_LINE_SPACING.EXACTLY
                    brpf.line_spacing = Pt(2)
                tbl = docx.add_table(rows=n_rows, cols=n_cols)
                tbl.style = "Table Grid"
                # 固定布局，列宽直接写入 tblGrid（Word 只认 gridCol，单元格
                # 宽度设置会被忽略）；表格左缘与 PDF 对齐（可超出正文左边界）
                tbl.autofit = False
                xs, ys = item["xs"], item["ys"]
                tblPr = tbl._tbl.tblPr
                layout = OxmlElement("w:tblLayout")
                layout.set(qn("w:type"), "fixed")
                tblPr.append(layout)
                total_w = int(round(xs[-1] - xs[0])) * 20  # 磅 → 缇
                tblW = tblPr.find(qn("w:tblW"))
                if tblW is None:
                    tblW = OxmlElement("w:tblW")
                    tblPr.append(tblW)
                tblW.set(qn("w:w"), str(total_w))
                tblW.set(qn("w:type"), "dxa")
                tbl_ind = OxmlElement("w:tblInd")
                tbl_ind.set(qn("w:w"), str(int(round(xs[0] - cur_sec_left)) * 20))
                tbl_ind.set(qn("w:type"), "dxa")
                tblPr.append(tbl_ind)
                # 缩小单元格左右内边距（PDF 文字紧贴格线，默认内边距会导致换行撑高行）
                cell_mar = OxmlElement("w:tblCellMar")
                for side in ("left", "right"):
                    el = OxmlElement(f"w:{side}")
                    el.set(qn("w:w"), "40")  # 2pt
                    el.set(qn("w:type"), "dxa")
                    cell_mar.append(el)
                tblPr.append(cell_mar)
                grid_cols = tbl._tbl.tblGrid.findall(qn("w:gridCol"))
                for ci, gc in enumerate(grid_cols):
                    if ci < len(xs) - 1:
                        gc.set(qn("w:w"), str(int(round(xs[ci + 1] - xs[ci])) * 20))
                for ri, trow in enumerate(tbl.rows):
                    trow.height = Pt(ys[ri + 1] - ys[ri])
                    trow.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
                cell_size = min(max(round(body_size * 2) / 2, 9), 16)
                for r1, c1, r2, c2, cell_x0, cell_lines, csize in item["cells"]:
                    cell = tbl.cell(r1, c1)
                    if (r2, c2) != (r1, c1):
                        cell = cell.merge(tbl.cell(r2, c2))
                    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
                    # 短文本（表头、栏目名）居中，长内容左对齐
                    cell_align = (WD_ALIGN_PARAGRAPH.CENTER
                                  if all(len(lt) <= 15 for lt, _ in cell_lines)
                                  else WD_ALIGN_PARAGRAPH.LEFT)
                    # 字号取单元格实际字号，取不到则用正文字号
                    run_size = min(max(round(csize * 2) / 2, 8), 16) if csize else cell_size
                    # 每个视觉行一个段落，按行在单元格内的实际位置设置左缩进
                    for k, (lt, lx0) in enumerate(cell_lines):
                        cp = cell.paragraphs[0] if k == 0 else cell.add_paragraph()
                        pf = cp.paragraph_format
                        pf.space_before = Pt(0)
                        pf.space_after = Pt(0)
                        cp.alignment = cell_align
                        if cell_align == WD_ALIGN_PARAGRAPH.LEFT:
                            pf.left_indent = Pt(max(lx0 - cell_x0 - 2, 0))
                        r = cp.add_run(lt)
                        r.font.size = Pt(run_size)
                        r.font.name = "Times New Roman"
                        r._element.rPr.rFonts.set(qn("w:eastAsia"), body_cjk_font)
            prev_page = item["page"]
            prev_last_y0 = item["y1"] - median_pitch
            continue
        para = item
        text = "".join(s[0] for s in para["spans"])
        if not text.strip():
            continue
        # 启发式：大字体 + 短文本 = 标题
        is_title = para["size"] >= title_threshold and len(text) < 80

        # 行距用固定值精确匹配原文（优先取本页行距；行盒需容纳最大字号）
        page_pitch = page_pitches[para["page"]] if para["page"] < len(page_pitches) else 0
        pitch = page_pitch or median_pitch
        exact_spacing = max(pitch, para["size"] * 1.2)
        # 段前距：还原该段与上一段之间的实际垂直间隔
        if prev_last_y0 is None or para["page"] != prev_page:
            space_before = max(para["y0"] - content_top, 0)
        else:
            space_before = max(para["y0"] - prev_last_y0 - pitch, 0)
        # 换了页要在段首插入分页符（不用 add_page_break，避免多出空行）；
        # 刚新建分节时页面已切换，不需要分页符
        need_break = (para["page"] != prev_page
                      or (prev_last_y0 is None and para["page"] > 0)) and not section_added
        # 居中的短行（如章标题）：行明显短于版心，且左右留白基本相等
        # （用两侧留白对称判断，而不是行中心是否接近页面中心——
        # 首行缩进的满行中心天然右偏半个缩进，会被误判）
        if page_sizes:
            pg_w, pg_h = page_sizes[para["page"]]
            lm, tr = (land_left, land_right) if pg_w > pg_h else (left_margin, text_right)
        else:
            lm, tr = left_margin, text_right
        text_width = tr - lm
        left_gap = para["x0"] - lm
        right_gap = tr - (para["x0"] + para["lw"])
        is_centered = (text_width > 0
                       and para["lw"] < text_width * 0.75
                       and (abs(left_gap - right_gap) < 15
                            or abs(para["cx"] - para["pw"] / 2) < 12))

        if is_title:
            # 根据字体大小判断标题级别
            if para["size"] >= title_threshold + 4:
                level = 1
            elif para["size"] >= title_threshold + 2:
                level = 2
            else:
                level = 3
            heading = docx.add_heading("", level=level)
            if need_break:
                heading.add_run().add_break(WD_BREAK.PAGE)
            heading.add_run(text)
            pf = heading.paragraph_format
            pf.space_before = Pt(space_before)
            pf.space_after = Pt(0)
            pf.line_spacing_rule = WD_LINE_SPACING.EXACTLY
            pf.line_spacing = Pt(exact_spacing)
            # 原文居中的标题在 Word 中也居中
            if is_centered:
                heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
            # 标题用黑色黑体，字号取原文实际大小；窄体字体同样横向压缩
            title_scale = min((s[4] for s in para["spans"]), default=100)
            for run in heading.runs:
                run.font.color.rgb = RGBColor(0, 0, 0)
                run.font.size = Pt(round(para["size"] * 2) / 2)
                run.font.name = "黑体"
                run._element.rPr.rFonts.set(qn("w:eastAsia"), "黑体")
                if title_scale < 97:
                    _set_run_scale(run, title_scale)
        else:
            p = docx.add_paragraph()
            if need_break:
                p.add_run().add_break(WD_BREAK.PAGE)
            pf = p.paragraph_format
            pf.space_before = Pt(space_before)
            pf.space_after = Pt(0)
            pf.line_spacing_rule = WD_LINE_SPACING.EXACTLY
            pf.line_spacing = Pt(exact_spacing)
            # 居中的短行（章标题等）居中显示；其余正文两端对齐
            if is_centered:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            # 首行缩进按原文实际偏移量设置（公文通常正好是 2 字符，
            # 特殊行如表单大标题则按其实际位置，避免多算缩进导致折行）
            if para["indented"] and not is_centered:
                pf.first_line_indent = Pt(max(para["x0"] - (left_margin - 2), 0))
            # 逐 span 写入，保留原文的字体、字号、加粗、横向缩放
            for t, size, bold, cjk_font, scale in para["spans"]:
                run = p.add_run(t)
                # 黑体本身已是粗体效果，不再叠加 bold 避免过粗
                run.bold = bold and cjk_font != "黑体"
                # 字号取 PDF 实际值，四舍五入到 0.5 磅
                run.font.size = Pt(min(max(round(size * 2) / 2, 9), 16))
                run.font.name = "Times New Roman"
                run._element.rPr.rFonts.set(qn("w:eastAsia"), cjk_font)
                # 窄体字体（如小标宋）按实测宽度横向压缩，防止替换字体变宽折行
                if scale < 97:
                    _set_run_scale(run, scale)

        prev_page = para["page"]
        prev_last_y0 = para["last_y0"]

    out_path = _get_unique_path("converted.docx")
    docx.save(out_path)
    return total_text, out_path


def _pdf_to_word_pdf2docx(pdf_bytes: bytes) -> Path:
    """用 pdf2docx 做版式还原转换（保留表格、图表、排版位置）"""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
        tmp_pdf.write(pdf_bytes)
        tmp_pdf_path = tmp_pdf.name

    out_path = _get_unique_path("converted.docx")

    try:
        Converter = _get_pdf2docx_converter()
        cv = Converter(tmp_pdf_path)
        cv.convert(str(out_path), start=0, end=None)
        cv.close()
    finally:
        os.unlink(tmp_pdf_path)

    return out_path


def pdf_to_word_page_images(pdf_bytes: bytes, dpi: int = 150) -> Path:
    """
    整页图片模式：每页 PDF 渲染为图片，按原始页面尺寸铺满 Word 页面。
    版式与 PDF 完全一致（居中、不会一页变两页），但内容不可编辑。
    """
    doc_pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
    docx = Document()
    zoom = dpi / 72.0

    for i, page in enumerate(doc_pdf):
        # Word 节页面尺寸与 PDF 页面一致，零边距 → 图片铺满整页
        sec = docx.sections[0] if i == 0 else docx.add_section(WD_SECTION.NEW_PAGE)
        sec.page_width = Pt(page.rect.width)
        sec.page_height = Pt(page.rect.height)
        sec.left_margin = sec.right_margin = sec.top_margin = sec.bottom_margin = Pt(0)

        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        img_path = _get_unique_path("page.png")
        pix.save(img_path)

        p = docx.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pf = p.paragraph_format
        pf.space_before = pf.space_after = Pt(0)
        pf.line_spacing = 1.0
        run = p.add_run()
        run.add_picture(str(img_path), width=Pt(page.rect.width), height=Pt(page.rect.height))
        img_path.unlink()  # 🔒 图片已嵌入 docx，删除临时文件

    out_path = _get_unique_path("converted.docx")
    docx.save(out_path)
    return out_path


def pdf_to_word(pdf_bytes: bytes, mode: str = "auto") -> tuple[Path, str]:
    """
    PDF 转换为 Word 文档。
    mode:
      - auto    文字多的用文本重建（可编辑），扫描件 fallback 到 pdf2docx
      - rebuild 强制文本提取重建（纯文字文档效果最好，完全可编辑）
      - layout  强制 pdf2docx 版式还原（报表/图文混排/带图表的文档选这个）
      - images  整页图片模式，版式与 PDF 完全一致，内容不可编辑
    返回 (输出路径, 模式说明)。
    """
    if mode == "images":
        return pdf_to_word_page_images(pdf_bytes), "整页图片模式（版式完全一致，不可编辑）"

    if mode == "layout":
        return _pdf_to_word_pdf2docx(pdf_bytes), "版式还原模式（保留表格/图表/排版）"

    if mode == "rebuild":
        text_content, text_path = _extract_text_rebuild(pdf_bytes)
        if text_path:
            return text_path, "文字提取模式（可编辑）"
        return _pdf_to_word_pdf2docx(pdf_bytes), "版式还原模式（文本过少自动切换）"

    # auto：先尝试文本提取重建
    text_content, text_path = _extract_text_rebuild(pdf_bytes)

    if text_path and len(text_content.strip()) >= 100:
        return text_path, "文字提取模式（可编辑）"

    # Fallback: 扫描件/图片 PDF
    return _pdf_to_word_pdf2docx(pdf_bytes), "版式还原模式（扫描件/图片PDF）"


# ==================== 图像格式互转 ====================

def convert_image(
    image_bytes: bytes,
    input_name: str,
    output_format: str
) -> Path:
    """图像格式互转"""
    fmt_map = {
        "png": "PNG", "jpg": "JPEG", "jpeg": "JPEG",
        "webp": "WEBP", "bmp": "BMP", "tiff": "TIFF", "gif": "GIF"
    }
    pil_fmt = fmt_map.get(output_format.lower(), "PNG")
    ext = output_format.lower()
    
    img = Image.open(io.BytesIO(image_bytes))
    
    # 处理透明通道
    if pil_fmt == "JPEG" and img.mode in ("RGBA", "P"):
        # 创建白色背景
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1])
        img = background
    
    stem = Path(input_name).stem
    out_path = _get_unique_path(f"{stem}.{ext}")
    
    save_kwargs = {}
    if pil_fmt == "JPEG":
        save_kwargs["quality"] = 95
    elif pil_fmt == "WEBP":
        save_kwargs["quality"] = 90
    
    img.save(out_path, pil_fmt, **save_kwargs)
    return out_path


# ==================== 图像 → Word ====================

def image_to_word(
    image_bytes: bytes,
    image_name: str,
    mode: str = "embed"
) -> tuple[Path, str]:
    """
    图像转 Word
    mode: "embed"  图片嵌入（保留原图，不可编辑文字）
          "ocr"    OCR文字提取（可编辑，需安装Tesseract）
          "hybrid" 图片+文字混合（第1页原图，第2页可编辑文字）
    返回 (输出路径, 模式说明)
    """
    if mode == "ocr":
        return _image_to_word_ocr(image_bytes, image_name)
    elif mode == "hybrid":
        return _image_to_word_hybrid(image_bytes, image_name)
    else:
        return _image_to_word_embed(image_bytes, image_name), "图片嵌入模式（保留原图）"


def _image_to_word_embed(image_bytes: bytes, image_name: str) -> Path:
    """将图片直接嵌入 Word 文档"""
    doc = Document()
    
    # python-docx 的 add_picture 需要文件路径，先写临时文件
    suffix = Path(image_name).suffix or ".png"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name
    
    try:
        # 计算合适的显示宽度（最大 6 英寸）
        img = Image.open(io.BytesIO(image_bytes))
        width_inch = min(img.width / 150, 6.0)  # 按 150 DPI 估算，不超过 6 英寸
        doc.add_picture(tmp_path, width=Inches(width_inch))
    finally:
        os.unlink(tmp_path)
    
    stem = Path(image_name).stem
    out_path = _get_unique_path(f"{stem}.docx")
    doc.save(out_path)
    return out_path


# RapidOCR 单例（避免每次调用重复加载模型）
_rapidocr_engine = None

def _get_rapidocr_engine():
    """获取 RapidOCR 单例引擎"""
    global _rapidocr_engine
    if _rapidocr_engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _rapidocr_engine = RapidOCR()
    return _rapidocr_engine


def _try_rapidocr(img: Image.Image) -> list:
    """尝试用 RapidOCR 识别，返回统一格式的 words 列表（纯 Python，无需 Tesseract）"""
    import numpy as np
    import sys
    
    # 大图预缩放（RapidOCR 对高分辨率图片处理极慢）
    MAX_WIDTH = 2000
    if img.width > MAX_WIDTH:
        ratio = MAX_WIDTH / img.width
        new_h = int(img.height * ratio)
        img = img.resize((MAX_WIDTH, new_h), Image.LANCZOS)
    
    try:
        engine = _get_rapidocr_engine()
        result, _ = engine(np.array(img))
        if not result:
            return []
        words = []
        for item in result:
            bbox, text, conf = item[0], item[1], item[2]
            if not text or not text.strip():
                continue
            xs = [p[0] for p in bbox]
            ys = [p[1] for p in bbox]
            words.append({
                'text': text.strip(),
                'left': min(xs),
                'top': min(ys),
                'width': max(xs) - min(xs),
                'height': max(ys) - min(ys),
                'conf': conf,
            })
        return words
    except Exception as e:
        print(f"[RapidOCR Error] {e}", file=sys.stderr)
        return []


def _try_pytesseract(img: Image.Image, lang: str) -> list:
    """尝试用 pytesseract 识别，返回统一格式的 words 列表（需要本地 Tesseract）"""
    if not _ensure_tesseract():
        return []
    try:
        import pytesseract
        data = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT)
        words = []
        for i in range(len(data['text'])):
            conf = int(data['conf'][i])
            if conf < 30:
                continue
            text = data['text'][i].strip()
            if not text:
                continue
            words.append({
                'text': text,
                'left': data['left'][i],
                'top': data['top'][i],
                'width': data['width'][i],
                'height': data['height'][i],
                'conf': conf,
            })
        return words
    except Exception:
        return []


def _build_docx_from_words(words: list, img_width: int) -> Document:
    """根据 words 列表构建 Word 文档（共用排版分析逻辑）"""
    if not words:
        return None
    
    avg_height_global = sum(w['height'] for w in words) / len(words)
    title_threshold = max(avg_height_global * 1.3, 20)
    
    # 按行分组（y 坐标接近的归为一行）
    words_sorted = sorted(words, key=lambda w: w['top'])
    lines = []
    current_line = [words_sorted[0]]
    
    for w in words_sorted[1:]:
        avg_height = sum(x['height'] for x in current_line) / len(current_line)
        if abs(w['top'] - current_line[0]['top']) < avg_height * 0.8:
            current_line.append(w)
        else:
            current_line.sort(key=lambda x: x['left'])
            lines.append(current_line)
            current_line = [w]
    current_line.sort(key=lambda x: x['left'])
    lines.append(current_line)
    
    doc = Document()
    for line_words in lines:
        line_text = ''.join(w['text'] for w in line_words)
        avg_height = sum(w['height'] for w in line_words) / len(line_words)
        leftmost = line_words[0]['left']
        rightmost = line_words[-1]['left'] + line_words[-1]['width']
        line_center = (leftmost + rightmost) / 2
        
        is_center = abs(line_center - img_width / 2) < img_width * 0.12
        is_title = avg_height >= title_threshold and len(line_text) < 60
        
        if is_title:
            level = 1 if avg_height >= title_threshold * 1.2 else 2
            p = doc.add_heading(line_text, level=level)
        else:
            p = doc.add_paragraph(line_text)
        
        if is_center:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    return doc


def _ocr_with_layout(image_bytes: bytes, image_name: str, lang: str = "chi_sim+eng") -> tuple[Document, str]:
    """
    OCR + 版面分析，返回 (Document对象, 模式说明)。
    优先 RapidOCR（云端友好），回退 pytesseract（本地）。
    """
    img = Image.open(io.BytesIO(image_bytes))
    img_width = img.width
    
    # 先尝试 RapidOCR（纯 Python ONNX，无需 Tesseract，适合 Streamlit Cloud）
    words = _try_rapidocr(img)
    engine_name = "RapidOCR"
    
    # 失败则尝试 pytesseract（需要本地安装 Tesseract）
    if not words:
        words = _try_pytesseract(img, lang)
        engine_name = "Tesseract"
    
    if not words:
        return None, "OCR未识别到文字"
    
    doc = _build_docx_from_words(words, img_width)
    if doc is None:
        return None, "OCR未识别到文字"
    
    return doc, f"{engine_name}版面分析模式（可编辑）"


def _image_to_word_ocr(image_bytes: bytes, image_name: str, lang: str = "chi_sim+eng") -> tuple[Path, str]:
    """OCR 提取文字生成可编辑 Word（带版面分析）"""
    doc, info = _ocr_with_layout(image_bytes, image_name, lang)
    
    if doc is None:
        path = _image_to_word_embed(image_bytes, image_name)
        return path, f"图片嵌入模式（{info}）"
    
    stem = Path(image_name).stem
    out_path = _get_unique_path(f"{stem}_ocr.docx")
    doc.save(out_path)
    return out_path, info


def _image_to_word_hybrid(image_bytes: bytes, image_name: str, lang: str = "chi_sim+eng") -> tuple[Path, str]:
    """
    混合模式：第1页嵌入原图（保留格式+图片），第2页附上OCR可编辑文字（带版面分析）
    """
    doc, info = _ocr_with_layout(image_bytes, image_name, lang)
    
    out_doc = Document()
    
    # ===== 第1页：嵌入原图 =====
    suffix = Path(image_name).suffix or ".png"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name
    
    try:
        img_obj = Image.open(io.BytesIO(image_bytes))
        width_inch = min(img_obj.width / 150, 6.0)
        out_doc.add_picture(tmp_path, width=Inches(width_inch))
    finally:
        os.unlink(tmp_path)
    
    # ===== 第2页：OCR 文字 =====
    if doc is not None:
        out_doc.add_page_break()
        out_doc.add_heading("【OCR 文字提取结果 - 可编辑】", level=1)
        
        # 复制段落
        for element in doc.element.body:
            out_doc.element.body.append(element)
    
    stem = Path(image_name).stem
    out_path = _get_unique_path(f"{stem}_hybrid.docx")
    out_doc.save(out_path)
    return out_path, f"图片+文字混合模式（{info}）"


# ==================== 图像合并 ====================

def merge_images_vertical(
    image_files: List[bytes],
    image_names: List[str],
    spacing: int = 0,
    bg_color: tuple = (255, 255, 255),
    align: str = "center",
    max_width: int = None
) -> Path:
    """
    将多张图片垂直拼接为一张长图
    spacing: 图片间距（像素）
    bg_color: 背景色 (R, G, B)
    align: left/center/right
    max_width: 最大宽度，超出则等比缩放
    """
    images = []
    for img_bytes in image_files:
        img = Image.open(io.BytesIO(img_bytes))
        if img.mode in ("RGBA", "P"):
            # 转成 RGB，透明部分用背景色填充
            background = Image.new("RGB", img.size, bg_color)
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")
        images.append(img)
    
    # 确定目标宽度
    target_width = max(img.width for img in images)
    if max_width and target_width > max_width:
        target_width = max_width
    
    # 缩放所有图片到统一宽度（保持比例）
    scaled = []
    for img in images:
        if img.width != target_width:
            ratio = target_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((target_width, new_height), Image.LANCZOS)
        scaled.append(img)
    
    # 计算总高度
    total_height = sum(img.height for img in scaled) + spacing * (len(scaled) - 1)
    
    # 创建画布
    result = Image.new("RGB", (target_width, total_height), bg_color)
    
    # 逐张粘贴
    y = 0
    for img in scaled:
        x = 0
        if align == "center":
            x = (target_width - img.width) // 2
        elif align == "right":
            x = target_width - img.width
        result.paste(img, (x, y))
        y += img.height + spacing
    
    out_path = _get_unique_path("merged_long_image.png")
    result.save(out_path, "PNG", quality=95)
    return out_path


# ==================== PDF 合并 ====================

def merge_pdfs(pdf_files: List[bytes], pdf_names: List[str]) -> Path:
    """合并多个PDF为一个"""
    doc = fitz.open()
    tmp_files = []
    
    try:
        for pdf_bytes in pdf_files:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(pdf_bytes)
                tmp_files.append(tmp.name)
            
            src = fitz.open(tmp.name)
            doc.insert_pdf(src)
            src.close()
        
        out_path = _get_unique_path("merged.pdf")
        doc.save(out_path)
        return out_path
    finally:
        doc.close()
        for f in tmp_files:
            if os.path.exists(f):
                os.unlink(f)


# ==================== PDF 拆分 ====================

def split_pdf(pdf_bytes: bytes, split_mode: str, ranges: str = "") -> Path:
    """
    拆分PDF
    split_mode: "single" 每页单独, "range" 按范围
    ranges: 如 "1-3,5,7-9"
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total = len(doc)
    output_files = []
    
    try:
        if split_mode == "single":
            for i in range(total):
                new_doc = fitz.open()
                new_doc.insert_pdf(doc, from_page=i, to_page=i)
                out_path = _get_unique_path(f"page_{i+1}.pdf")
                new_doc.save(out_path)
                new_doc.close()
                output_files.append(out_path)
        else:
            ranges_list = _parse_split_ranges(ranges, total)
            for idx, (start, end) in enumerate(ranges_list):
                new_doc = fitz.open()
                new_doc.insert_pdf(doc, from_page=start-1, to_page=end-1)
                out_path = _get_unique_path(f"part_{idx+1}.pdf")
                new_doc.save(out_path)
                new_doc.close()
                output_files.append(out_path)
        
        if len(output_files) == 1:
            return output_files[0]
        
        # 打包为zip
        zip_path = _get_unique_path("split_pdfs.zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for p in output_files:
                zf.write(p, p.name)
                p.unlink()
        return zip_path
    finally:
        doc.close()


# ==================== PDF 提取文本 ====================

def extract_pdf_text(pdf_bytes: bytes) -> Path:
    """提取PDF文本保存为txt"""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    texts = []
    for page in doc:
        texts.append(f"--- 第 {page.number + 1} 页 ---\n")
        texts.append(page.get_text())
        texts.append("\n")
    doc.close()
    
    out_path = _get_unique_path("extracted_text.txt")
    out_path.write_text("\n".join(texts), encoding="utf-8")
    return out_path


# ==================== 工具函数 ====================

def _parse_page_range(page_range: str, total_pages: int) -> List[int]:
    """解析页码范围字符串，返回0-based页码列表"""
    pages = set()
    parts = page_range.split(",")
    for part in parts:
        part = part.strip()
        if "-" in part:
            start, end = part.split("-")
            start = max(1, int(start.strip()))
            end = min(total_pages, int(end.strip()))
            pages.update(range(start - 1, end))
        else:
            p = int(part.strip())
            if 1 <= p <= total_pages:
                pages.add(p - 1)
    return sorted(list(pages))


def _parse_split_ranges(ranges: str, total_pages: int) -> List[Tuple[int, int]]:
    """解析拆分范围，返回 (start, end) 列表，1-based"""
    result = []
    parts = ranges.split(",")
    for part in parts:
        part = part.strip()
        if "-" in part:
            start, end = part.split("-")
            start = max(1, int(start.strip()))
            end = min(total_pages, int(end.strip()))
            result.append((start, end))
        else:
            p = int(part.strip())
            if 1 <= p <= total_pages:
                result.append((p, p))
    return result


def cleanup_old_files(max_age_hours: int = 24):
    """清理超过指定时间的旧文件"""
    import time
    now = time.time()
    max_age = max_age_hours * 3600
    for f in OUTPUT_DIR.iterdir():
        if f.is_file() and (now - f.stat().st_mtime) > max_age:
            f.unlink()


# ==================== 视频转长图 ====================

def video_to_long_image(
    video_bytes: bytes,
    interval_sec: float = 1.0,
    max_frames: int = 50,
    direction: str = "vertical"
) -> Path:
    """提取视频关键帧拼接为长图"""
    import cv2
    
    suffix = ".mp4"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(video_bytes)
        tmp_path = tmp.name
    
    try:
        cap = cv2.VideoCapture(tmp_path)
        if not cap.isOpened():
            return None
        
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        frame_interval = max(1, int(fps * interval_sec))
        if total_frames > 0:
            max_frames = min(max_frames, total_frames // frame_interval + 1)
        
        frames = []
        frame_idx = 0
        while len(frames) < max_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                break
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frames.append(Image.fromarray(frame_rgb))
            frame_idx += frame_interval
        
        cap.release()
        
        if not frames:
            return None
        
        # 统一宽度
        target_width = min(max(f.width for f in frames), 1200)
        scaled = []
        for f in frames:
            if f.width != target_width:
                ratio = target_width / f.width
                f = f.resize((target_width, int(f.height * ratio)), Image.LANCZOS)
            scaled.append(f)
        
        if direction == "vertical":
            total_height = sum(f.height for f in scaled)
            result = Image.new("RGB", (target_width, total_height), (255, 255, 255))
            y = 0
            for f in scaled:
                result.paste(f, (0, y))
                y += f.height
        else:
            total_width = sum(f.width for f in scaled)
            max_height = max(f.height for f in scaled)
            result = Image.new("RGB", (total_width, max_height), (255, 255, 255))
            x = 0
            for f in scaled:
                result.paste(f, (x, (max_height - f.height) // 2))
                x += f.width
        
        out_path = _get_unique_path("video_long_image.png")
        result.save(out_path, "PNG")
        return out_path
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ==================== 视频转 GIF ====================

def video_to_gif(
    video_bytes: bytes,
    start_sec: float = 0,
    duration_sec: float = 5,
    fps: int = 10,
    width: int = 480
) -> Path:
    """视频片段转 GIF"""
    import cv2
    
    suffix = ".mp4"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(video_bytes)
        tmp_path = tmp.name
    
    try:
        cap = cv2.VideoCapture(tmp_path)
        if not cap.isOpened():
            return None
        
        video_fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        start_frame = int(start_sec * video_fps)
        end_frame = min(int((start_sec + duration_sec) * video_fps), total_frames)
        
        frames = []
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        frame_step = max(1, int(video_fps / fps))
        
        for frame_idx in range(start_frame, end_frame, frame_step):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                break
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            if img.width > width:
                ratio = width / img.width
                img = img.resize((width, int(img.height * ratio)), Image.LANCZOS)
            frames.append(img)
        
        cap.release()
        
        if not frames:
            return None
        
        out_path = _get_unique_path("converted.gif")
        frames[0].save(
            out_path,
            save_all=True,
            append_images=frames[1:],
            duration=int(1000 / fps),
            loop=0
        )
        return out_path
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ==================== 音频格式转换 ====================

def convert_audio(
    audio_bytes: bytes,
    input_name: str,
    output_format: str,
    bitrate: str = "192k"
) -> Path:
    """音频格式转换"""
    try:
        from pydub import AudioSegment
    except ImportError:
        return None
    
    fmt_map = {
        "mp3": "mp3", "wav": "wav", "flac": "flac",
        "ogg": "ogg", "aac": "aac", "m4a": "mp4"
    }
    out_fmt = fmt_map.get(output_format.lower(), "mp3")
    
    suffix = Path(input_name).suffix or ".mp3"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_in:
        tmp_in.write(audio_bytes)
        in_path = tmp_in.name
    
    try:
        audio = AudioSegment.from_file(in_path)
        stem = Path(input_name).stem
        out_path = _get_unique_path(f"{stem}.{out_fmt}")
        
        export_kwargs = {"format": out_fmt}
        if out_fmt == "mp3":
            export_kwargs["bitrate"] = bitrate
        
        audio.export(str(out_path), **export_kwargs)
        return out_path
    except Exception:
        return None
    finally:
        if os.path.exists(in_path):
            os.unlink(in_path)


# ==================== 图片压缩 ====================

def compress_image(
    image_bytes: bytes,
    input_name: str,
    quality: int = 85,
    max_width: int = None,
    max_height: int = None
) -> Path:
    """图片压缩"""
    img = Image.open(io.BytesIO(image_bytes))
    
    # 缩放
    if max_width or max_height:
        img.thumbnail(
            (max_width or img.width, max_height or img.height),
            Image.LANCZOS
        )
    
    # 处理模式和格式
    if img.mode in ("RGBA", "P"):
        fmt = "PNG"
        ext = "png"
        save_kwargs = {}
    else:
        fmt = "JPEG"
        ext = "jpg"
        save_kwargs = {"quality": quality, "optimize": True}
        if img.mode != "RGB":
            img = img.convert("RGB")
    
    stem = Path(input_name).stem
    out_path = _get_unique_path(f"{stem}_compressed.{ext}")
    img.save(out_path, fmt, **save_kwargs)
    return out_path


# ==================== PDF 压缩/优化 ====================

def compress_pdf(pdf_bytes: bytes) -> Path:
    """PDF 优化压缩（去除冗余数据、压缩流）"""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    out_path = _get_unique_path("compressed.pdf")
    doc.save(out_path, garbage=4, deflate=True, clean=True)
    doc.close()
    return out_path


# ==================== 二维码生成 ====================

def generate_qr(data: str, size: int = 10, error_correction: str = "M") -> Path:
    """生成二维码"""
    import qrcode
    from qrcode.constants import ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_H
    
    ec_map = {"L": ERROR_CORRECT_L, "M": ERROR_CORRECT_M, "H": ERROR_CORRECT_H}
    ec = ec_map.get(error_correction, ERROR_CORRECT_M)
    
    qr = qrcode.QRCode(version=1, error_correction=ec, box_size=size, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    out_path = _get_unique_path("qrcode.png")
    img.save(out_path)
    return out_path


# ==================== 图片去背景 ====================

def remove_background(image_bytes: bytes, input_name: str) -> Path:
    """图片去背景（OpenCV GrabCut 算法）"""
    import cv2
    import numpy as np
    
    img = Image.open(io.BytesIO(image_bytes))
    img_np = np.array(img)
    
    if len(img_np.shape) == 2:
        img_np = cv2.cvtColor(img_np, cv2.COLOR_GRAY2RGB)
    elif img_np.shape[2] == 4:
        img_np = cv2.cvtColor(img_np, cv2.COLOR_RGBA2RGB)
    
    mask = np.zeros(img_np.shape[:2], np.uint8)
    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)
    
    h, w = img_np.shape[:2]
    margin_x = max(5, w // 20)
    margin_y = max(5, h // 20)
    rect = (margin_x, margin_y, w - margin_x * 2, h - margin_y * 2)
    
    cv2.grabCut(img_np, mask, rect, bgd_model, fgd_model, 5, cv2.GC_INIT_WITH_RECT)
    
    mask2 = np.where((mask == 2) | (mask == 0), 0, 1).astype('uint8')
    img_rgba = cv2.cvtColor(img_np, cv2.COLOR_RGB2RGBA)
    img_rgba[:, :, 3] = mask2 * 255
    
    result = Image.fromarray(img_rgba)
    
    stem = Path(input_name).stem
    out_path = _get_unique_path(f"{stem}_nobg.png")
    result.save(out_path, "PNG")
    return out_path


# ==================== Office 转 PDF ====================

def office_to_pdf(file_bytes: bytes, file_name: str) -> Path:
    """Office 文档转 PDF（Windows COM）"""
    try:
        import win32com.client
        import pythoncom
        
        pythoncom.CoInitialize()
        
        suffix = Path(file_name).suffix.lower()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(file_bytes)
            in_path = tmp.name
        
        out_path = _get_unique_path(Path(file_name).stem + ".pdf")
        
        if suffix in (".doc", ".docx"):
            app = win32com.client.Dispatch("Word.Application")
            app.Visible = False
            doc = app.Documents.Open(in_path)
            doc.SaveAs(str(out_path), FileFormat=17)
            doc.Close()
            app.Quit()
        elif suffix in (".xls", ".xlsx"):
            app = win32com.client.Dispatch("Excel.Application")
            app.Visible = False
            wb = app.Workbooks.Open(in_path)
            wb.ExportAsFixedFormat(0, str(out_path))
            wb.Close()
            app.Quit()
        else:
            raise ValueError(f"不支持的格式: {suffix}")
        
        os.unlink(in_path)
        pythoncom.CoUninitialize()
        return out_path
        
    except Exception as e:
        raise RuntimeError(f"Office 转 PDF 需要 Windows + Office 环境: {e}")


# ========== 🔒 隐私保护：安全执行包装器 ==========
# 核心机制：转换结果读取到内存后立即删除临时文件
# 确保服务器管理员无法看到任何用户上传/生成的文件

def secure_run(func, *args, **kwargs):
    """执行转换函数，读取结果后自动删除临时文件，确保文件不落盘留存
    
    返回类型:
        - 原函数返回 Path → 返回 bytes
        - 原函数返回 list[Path] → 返回 list[(bytes, filename)]
        - 其他类型 → 原样返回
    """
    result = func(*args, **kwargs)
    if result is None:
        return None
    
    # 处理 tuple（如 (Path, str)）
    if isinstance(result, tuple) and len(result) >= 1 and isinstance(result[0], Path):
        with open(result[0], "rb") as f:
            data = f.read()
        result[0].unlink()  # 🔒 立即删除
        return (data,) + result[1:]
    
    # 处理列表（多个文件，如 PDF拆分/转图片）
    if isinstance(result, list):
        outputs = []
        for item in result:
            if isinstance(item, Path):
                with open(item, "rb") as f:
                    data = f.read()
                item.unlink()  # 🔒 立即删除
                outputs.append((data, item.name))
            else:
                outputs.append(item)
        return outputs
    
    # 处理单个 Path
    if isinstance(result, Path):
        with open(result, "rb") as f:
            data = f.read()
        result.unlink()  # 🔒 立即删除
        return data
    
    return result


# ========== 子进程隔离：重计算功能独立进程执行 ==========
# 这些功能会在几十秒内占满 CPU（或原生库崩溃），在 Streamlit 服务进程内
# 直接执行会把整个服务拖死，浏览器报 "Connection error"。
# 放到独立子进程后：服务进程始终响应，子进程崩溃也只返回友好错误。
_SUBPROCESS_FUNCS = {
    "pdf_to_word", "image_to_word", "office_to_pdf",
    "video_to_long_image", "video_to_gif", "compress_pdf",
    "convert_audio",
}


def _subprocess_entry(func_name, args, kwargs):
    """子进程入口：按函数名执行转换（spawn 模式只要求参数可序列化）"""
    return secure_run(globals()[func_name], *args, **kwargs)


def safe_run(func, *args, **kwargs):
    """安全执行转换：重计算功能放到独立子进程，轻量功能直接执行。
    子进程异常中断时抛出友好错误，Streamlit 服务不受影响。"""
    if func.__name__ not in _SUBPROCESS_FUNCS:
        return secure_run(func, *args, **kwargs)
    import concurrent.futures
    try:
        with concurrent.futures.ProcessPoolExecutor(max_workers=1) as ex:
            future = ex.submit(_subprocess_entry, func.__name__, args, kwargs)
            return future.result(timeout=600)
    except concurrent.futures.TimeoutError:
        raise RuntimeError("转换超时（超过 10 分钟），文件可能过大或格式异常")
    except Exception:
        raise RuntimeError("转换进程异常中断，文件可能过大或格式异常，请重试")
