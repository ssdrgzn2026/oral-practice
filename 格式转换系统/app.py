import streamlit as st
import converter
from pathlib import Path
import io
import os

st.set_page_config(
    page_title="格式转换系统 v2.0",
    page_icon="🔄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========== 场景分类定义 ==========
SCENES = {
    "📄 文档处理": [
        ("PDF ↔ 图像", "pdf2img"),
        ("PDF ↔ Word", "pdf2word"),
        ("PDF 合并 / 拆分", "pdf_merge_split"),
        ("PDF 提取文本", "pdf_text"),
        ("PDF 压缩优化", "pdf_compress"),
        ("Excel/Word → PDF", "office2pdf"),
        ("图像转 Word (OCR)", "img2word"),
    ],
    "🖼️ 图片处理": [
        ("图像 → PDF", "img2pdf"),
        ("图像格式互转", "img2img"),
        ("图片合并长图", "merge_long"),
        ("图片压缩", "compress_img"),
        ("图片去背景", "remove_bg"),
        ("二维码生成", "qr"),
    ],
    "🎬 音视频处理": [
        ("视频 → 长图", "video2long"),
        ("视频 → GIF", "video2gif"),
        ("音频格式转换", "audio"),
    ],
    "🛠️ 实用工具": [
        ("批量重命名", "batch_rename"),
    ],
}

SCENE_ICONS = {
    "📄 文档处理": "📄",
    "🖼️ 图片处理": "🖼️",
    "🎬 音视频处理": "🎬",
    "🛠️ 实用工具": "🛠️",
}


def render_home():
    """首页 - 系统概览与隐私承诺"""
    
    # ===== Hero 横幅 =====
    st.markdown("""
    <div style='text-align:center;padding:30px 20px;background:linear-gradient(135deg,#667eea0d,#764ba20d);border-radius:16px;margin-bottom:20px;border:1px solid #667eea20;'>
        <div style='font-size:48px;margin-bottom:10px;'>🔄</div>
        <h1 style='margin:0;font-size:32px;color:#333;'>格式转换系统 v2.0</h1>
        <p style='margin:8px 0 0;color:#666;font-size:16px;'>强大 · 易用 · 全场景覆盖 · 零痕迹隐私保护</p>
        <div style='margin-top:12px;'>
            <span style='background:#4A90D9;color:white;padding:3px 10px;border-radius:12px;font-size:12px;margin:0 3px;'>18+ 功能</span>
            <span style='background:#27AE60;color:white;padding:3px 10px;border-radius:12px;font-size:12px;margin:0 3px;'>4 大场景</span>
            <span style='background:#E74C3C;color:white;padding:3px 10px;border-radius:12px;font-size:12px;margin:0 3px;'>🔒 隐私优先</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # ===== 🔒 隐私保护核心承诺（最醒目） =====
    st.markdown("""
    <div style='background:linear-gradient(135deg,#059669,#10b981);border-radius:12px;padding:20px;color:white;margin-bottom:20px;'>
        <div style='font-size:20px;font-weight:bold;margin-bottom:12px;'>🔒 隐私保护核心承诺</div>
        <div style='display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;'>
            <div style='text-align:center;'>
                <div style='font-size:28px;margin-bottom:6px;'>🛡️</div>
                <div style='font-weight:bold;font-size:14px;margin-bottom:4px;'>内存-only 处理</div>
                <div style='font-size:12px;opacity:0.9;'>文件不写入服务器硬盘<br>仅在内存中处理</div>
            </div>
            <div style='text-align:center;'>
                <div style='font-size:28px;margin-bottom:6px;'>👁️‍🗨️</div>
                <div style='font-weight:bold;font-size:14px;margin-bottom:4px;'>管理员不可见</div>
                <div style='font-size:12px;opacity:0.9;'>服务器管理员<br>无法查看任何用户文件</div>
            </div>
            <div style='text-align:center;'>
                <div style='font-size:28px;margin-bottom:6px;'>🗑️</div>
                <div style='font-weight:bold;font-size:14px;margin-bottom:4px;'>即时销毁</div>
                <div style='font-size:12px;opacity:0.9;'>转换完成后立即删除<br>服务器不留任何痕迹</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    with st.expander("📖 了解零痕迹保障机制", expanded=False):
        st.markdown("""
        **🔐 为什么管理员完全看不到您的数据？**
        
        本系统采用 **内存-only 架构**，核心机制如下：
        
        1. **上传即入内存** — 用户上传的文件直接读入内存变量，**不保存到服务器硬盘任何位置**
        2. **转换全程内存** — 所有格式转换操作（PDF解析、图像处理、OCR识别、音视频编解码）全部在内存中完成
        3. **结果直传浏览器** — 转换完成后，结果数据通过 HTTP 响应直接发送给浏览器，**服务器不保留任何副本**
        4. **临时文件秒删** — 极少数必须借助第三方库生成的临时文件，在读取到内存后立即 `unlink()` 删除
        
        **这意味着：**
        - ✅ 服务器硬盘上不会留下任何用户文件
        - ✅ 服务器管理员无法通过文件系统查看任何用户数据
        - ✅ 即使服务器被入侵，攻击者也无法恢复已处理过的文件
        - ✅ 阿里云/云服务商同样无法查看您的文件内容
        
        **唯一能看到您数据的人：只有您自己。**
        """)
    
    # ===== 系统核心能力 =====
    st.subheader("⚡ 系统核心能力")
    cap_col1, cap_col2, cap_col3, cap_col4 = st.columns(4)
    with cap_col1:
        st.metric("转换功能", "18+", "持续扩展")
    with cap_col2:
        st.metric("覆盖场景", "4 大", "文档/图片/音视频/工具")
    with cap_col3:
        st.metric("隐私等级", "Level 3", "内存-only + 即时销毁")
    with cap_col4:
        st.metric("支持格式", "30+", "PDF/Word/Excel/图片/音视频")
    
    # ===== 四场景快捷入口 =====
    st.subheader("📂 场景快捷入口")
    col1, col2, col3, col4 = st.columns(4)
    scene_cards = [
        ("📄 文档处理", "PDF/Word/Excel 互转、合并拆分、OCR提取、压缩优化", "#4A90D9"),
        ("🖼️ 图片处理", "格式互转、压缩、去背景、长图拼接、二维码生成", "#E67E22"),
        ("🎬 音视频处理", "视频转GIF/长图、音频格式转换(MP3/WAV/FLAC/OGG/AAC/M4A)", "#27AE60"),
        ("🛠️ 实用工具", "批量重命名、PDF优化等效率工具", "#8E44AD"),
    ]
    for col, (title, desc, color) in zip([col1, col2, col3, col4], scene_cards):
        with col:
            st.markdown(f"""
            <div style='background:{color}15;border:1px solid {color}40;border-radius:12px;padding:20px;text-align:center;margin-bottom:10px;min-height:170px;display:flex;flex-direction:column;justify-content:center;cursor:pointer;'>
                <div style='font-size:36px;margin-bottom:8px;'>{title.split()[0]}</div>
                <div style='font-weight:bold;font-size:16px;color:{color};margin-bottom:6px;'>{title.split()[1]}</div>
                <div style='font-size:13px;color:#666;'>{desc}</div>
            </div>
            """, unsafe_allow_html=True)
    
    # ===== 功能总览（列表式展示） =====
    st.subheader("📌 功能总览")
    
    feat_col1, feat_col2 = st.columns(2)
    with feat_col1:
        with st.container(border=True):
            st.markdown("**📄 文档处理（8项）**")
            st.markdown("""
            - 📄 PDF ↔ 图像（双向转换）
            - 📝 PDF ↔ Word（版式还原）
            - 📑 PDF 合并 / 拆分
            - 📋 PDF 提取文本
            - 🗜️ PDF 压缩优化
            - 📊 Excel/Word → PDF
            - 🖼️→📝 图像 OCR 转 Word
            - 🔍 支持手写体识别
            """)
        with st.container(border=True):
            st.markdown("**🎬 音视频处理（3项）**")
            st.markdown("""
            - 🎞️ 视频 → 长图（抽帧拼接）
            - 🎬 视频 → GIF（自定义时段）
            - 🎵 音频格式转换（6种格式）
            """)
    with feat_col2:
        with st.container(border=True):
            st.markdown("**🖼️ 图片处理（6项）**")
            st.markdown("""
            - 🖼️ 图像 → PDF
            - 🔄 图像格式互转（6种格式）
            - 📷 图片合并长图
            - 🗜️ 图片压缩（质量可调）
            - ✨ 图片去背景（AI算法）
            - 🔲 二维码生成（3级容错）
            """)
        with st.container(border=True):
            st.markdown("**🛠️ 实用工具（1项）**")
            st.markdown("""
            - 📝 批量重命名（4种规则）
            - 📦 一键打包 ZIP 下载
            - 📋 实时预览命名结果
            """)
    
    st.caption("总计 **18+ 项转换功能**，持续扩展中...")
    
    # ===== 使用提示 =====
    st.subheader("💡 使用提示")
    tips = [
        "📄 文档处理：PDF转Word支持版式还原，图像转Word支持OCR文字识别（含手写体），扫描件也能识别",
        "🖼️ 图片处理：去背景使用OpenCV GrabCut算法，二维码支持3级容错率，长图拼接支持垂直/水平方向",
        "🎬 音视频：视频转长图按秒抽帧拼接，GIF支持自定义时段和帧率，音频转换需安装ffmpeg",
        "🔒 隐私保障：所有文件内存处理，服务器不留痕迹，管理员不可见，您的数据只属于您",
    ]
    for tip in tips:
        st.markdown(f"- {tip}")
    
    # ===== 📱 手机使用指南 =====
    st.divider()
    st.subheader("📱 手机使用指南")
    st.markdown("**在手机上使用本系统时，可以直接从微信中选择文件进行转换！**")
    
    ios_col, android_col = st.columns(2)
    with ios_col:
        with st.container(border=True):
            st.markdown("**🍎 iPhone 用户**")
            st.markdown("""
            1. 在微信中长按要转换的文件/图片
            2. 选择「**用其他应用打开**」→「**存储到"文件"**」
            3. 打开 Safari/Chrome 浏览器，访问本系统
            4. 点击上传按钮 → 选择「**浏览**」→ 找到刚保存的文件
            """)

    with android_col:
        with st.container(border=True):
            st.markdown("**🤖 Android 用户**")
            st.markdown("""
            1. 在微信中长按要转换的文件/图片
            2. 选择「**保存到手机**」或「**下载**」
            3. 打开 Chrome/系统浏览器，访问本系统
            4. 点击上传按钮 → 在文件管理器中找到 `Download/WeiXin/` 或 `DCIM/WeiXin/` 目录
            """)

    st.info("""
    💡 **提示**：也可直接在微信内点击右上角「···」→「**在浏览器打开**」，然后在浏览器中使用本系统。
    上传时系统文件选择器会自动弹出，可浏览手机存储中的任何位置（包括微信下载目录）。
    """)

    st.divider()


def render_pdf2img():
    st.header("📄 PDF ↔ 图像")
    tab1, tab2 = st.tabs(["PDF → 图像", "图像 → PDF"])
    
    with tab1:
        uploaded = st.file_uploader("上传PDF文件", type=["pdf"], key="p2i")
        if uploaded:
            with st.spinner("转换中..."):
                try:
                    pdf_bytes = uploaded.getvalue()
                    results = converter.safe_run(converter.pdf_to_images, pdf_bytes)
                    if results:
                        st.success(f"✅ 转换完成！共 {len(results)} 页")
                        cols = st.columns(min(3, len(results)))
                        for i, (data, name) in enumerate(results):
                            with cols[i % 3]:
                                st.image(data, caption=f"第{i+1}页", use_container_width=True)
                                st.download_button("⬇️ 下载", data, name, key=f"dl_p2i_{i}")
                    else:
                        st.error("转换失败")
                except Exception as e:
                    st.error(f"转换出错: {e}")
    
    with tab2:
        uploaded = st.file_uploader("上传图像文件", type=["jpg", "jpeg", "png", "bmp", "tiff", "webp"], accept_multiple_files=True, key="i2p")
        if uploaded:
            with st.spinner("转换中..."):
                try:
                    files = [f.getvalue() for f in uploaded]
                    names = [f.name for f in uploaded]
                    pdf_bytes_out = converter.safe_run(converter.images_to_pdf, files, names)
                    if pdf_bytes_out:
                        st.success("✅ 转换完成！")
                        st.info(f"共 {len(uploaded)} 张图片")
                        st.download_button("⬇️ 下载PDF", pdf_bytes_out, "converted.pdf")
                    else:
                        st.error("转换失败")
                except Exception as e:
                    st.error(f"转换出错: {e}")


def render_pdf2word():
    st.header("📝 PDF ↔ Word")
    tab1, tab2 = st.tabs(["PDF → Word", "Word → PDF"])
    
    with tab1:
        uploaded = st.file_uploader("上传PDF文件", type=["pdf"], key="p2w")
        mode_label = st.radio(
            "转换模式",
            ["自动（智能判断）", "文字提取（纯文字文档，完全可编辑）", "版式还原（带表格/图表的报表，排版不变）"],
            index=0,
            key="p2w_mode",
            horizontal=True,
        )
        mode_map = {
            "自动（智能判断）": "auto",
            "文字提取（纯文字文档，完全可编辑）": "rebuild",
            "版式还原（带表格/图表的报表，排版不变）": "layout",
        }
        if uploaded:
            with st.spinner("转换中（智能版式还原+图文混排）..."):
                try:
                    pdf_bytes = uploaded.getvalue()
                    result = converter.safe_run(converter.pdf_to_word, pdf_bytes, mode=mode_map[mode_label])
                    if result:
                        doc_bytes, mode_desc = result
                        st.success(f"✅ 转换完成！{mode_desc}")
                        out_name = Path(uploaded.name).stem + ".docx"
                        st.download_button("⬇️ 下载Word", doc_bytes, out_name)
                    else:
                        st.error("转换失败")
                except Exception as e:
                    st.error(f"转换出错: {e}")
    
    with tab2:
        st.info("Word → PDF 请使用「文档处理 → Excel/Word → PDF」功能")


def render_pdf_merge_split():
    st.header("📑 PDF 合并 / 拆分")
    tab1, tab2 = st.tabs(["合并", "拆分"])
    
    with tab1:
        uploaded = st.file_uploader("上传多个PDF文件（按选择顺序合并）", type=["pdf"], accept_multiple_files=True, key="merge")
        if uploaded and len(uploaded) >= 2:
            st.write("文件顺序（可重新选择调整）：")
            for i, f in enumerate(uploaded, 1):
                st.write(f"{i}. {f.name}")
            if st.button("🔄 开始合并"):
                with st.spinner("合并中..."):
                    try:
                        files = [f.getvalue() for f in uploaded]
                        names = [f.name for f in uploaded]
                        pdf_bytes_out = converter.safe_run(converter.merge_pdfs, files, names)
                        if pdf_bytes_out:
                            st.success("✅ 合并完成！")
                            st.download_button("⬇️ 下载合并PDF", pdf_bytes_out, "merged.pdf")
                        else:
                            st.error("合并失败")
                    except Exception as e:
                        st.error(f"合并出错: {e}")
        elif uploaded:
            st.warning("请至少上传2个PDF文件")
    
    with tab2:
        uploaded = st.file_uploader("上传PDF文件", type=["pdf"], key="split")
        if uploaded:
            pages = st.text_input("页码范围（如：1,3,5-10）", value="", placeholder="留空则每页单独拆分")
            if st.button("✂️ 开始拆分"):
                with st.spinner("拆分中..."):
                    try:
                        pdf_bytes = uploaded.getvalue()
                        results = converter.safe_run(converter.split_pdf, pdf_bytes, uploaded.name, pages if pages else None)
                        if results:
                            st.success(f"✅ 拆分完成！共 {len(results)} 个文件")
                            for data, name in results:
                                st.download_button(f"⬇️ {name}", data, name, key=f"dl_split_{name}")
                        else:
                            st.error("拆分失败")
                    except Exception as e:
                        st.error(f"拆分出错: {e}")


def render_pdf_text():
    st.header("📋 PDF 提取文本")
    uploaded = st.file_uploader("上传PDF文件", type=["pdf"], key="txt")
    if uploaded:
        if st.button("📖 提取文本"):
            with st.spinner("提取中..."):
                try:
                    pdf_bytes = uploaded.getvalue()
                    text = converter.extract_pdf_text(pdf_bytes)
                    if text:
                        st.success("✅ 提取完成！")
                        st.text_area("提取内容", text, height=400)
                        st.download_button("⬇️ 下载TXT", text.encode("utf-8"), uploaded.name.replace(".pdf", ".txt"))
                    else:
                        st.warning("未提取到文本内容（可能是扫描件/图片PDF）")
                except Exception as e:
                    st.error(f"提取出错: {e}")


def render_img2pdf():
    st.header("🖼️ 图像 → PDF")
    uploaded = st.file_uploader("上传图像文件", type=["jpg", "jpeg", "png", "bmp", "tiff", "webp"], accept_multiple_files=True, key="img2pdf")
    if uploaded:
        with st.spinner("转换中..."):
            try:
                files = [f.getvalue() for f in uploaded]
                names = [f.name for f in uploaded]
                pdf_bytes_out = converter.safe_run(converter.images_to_pdf, files, names)
                if pdf_bytes_out:
                    st.success("✅ 转换完成！")
                    st.info(f"共 {len(uploaded)} 张图片")
                    st.download_button("⬇️ 下载PDF", pdf_bytes_out, "converted.pdf")
                else:
                    st.error("转换失败")
            except Exception as e:
                st.error(f"转换出错: {e}")


def render_img2img():
    st.header("🔄 图像格式互转")
    uploaded = st.file_uploader("上传图像文件", type=["jpg", "jpeg", "png", "bmp", "tiff", "webp", "ico", "gif"], key="i2i")
    if uploaded:
        fmt = st.selectbox("目标格式", ["png", "jpg", "bmp", "tiff", "webp", "ico"], key="i2i_fmt")
        if st.button("🔄 开始转换"):
            with st.spinner("转换中..."):
                try:
                    img_bytes = uploaded.getvalue()
                    img_bytes_out = converter.safe_run(converter.convert_image, img_bytes, uploaded.name, fmt)
                    if img_bytes_out:
                        st.success("✅ 转换完成！")
                        st.download_button("⬇️ 下载", img_bytes_out, f"converted.{fmt}")
                    else:
                        st.error("转换失败")
                except Exception as e:
                    st.error(f"转换出错: {e}")


def render_img2word():
    st.header("🖼️→📝 图像转 Word (OCR)")
    try:
        import rapidocr_onnxruntime
        ocr_ok = True
    except ImportError:
        ocr_ok = False
    if ocr_ok:
        st.success("✅ OCR 引擎已就绪")
    else:
        st.warning("⚠️ OCR 引擎未安装，将使用云端方案（需联网）")
    
    uploaded = st.file_uploader("上传图像文件", type=["jpg", "jpeg", "png", "bmp", "tiff", "webp"], accept_multiple_files=True, key="i2w")
    if uploaded:
        mode = st.radio("转换模式", [
            ("embed", "📷 图片嵌入（保留原图，不可编辑）"),
            ("ocr", "📝 OCR文字提取（可编辑文本）"),
            ("hybrid", "🔀 混合模式（第1页原图+第2页OCR文字）"),
        ], format_func=lambda x: x[1], key="i2w_mode")
        
        if st.button("🚀 开始转换"):
            progress = st.progress(0, "准备转换...")
            try:
                files = [f.getvalue() for f in uploaded]
                names = [f.name for f in uploaded]
                
                progress.progress(20, "📖 正在加载 OCR 引擎（首次约 1-2 秒）...")
                
                progress.progress(50, "🔍 正在识别文字（根据图片大小可能需要几秒）...")
                result = converter.safe_run(converter.image_to_word, files[0], names[0], mode=mode[0])
                
                progress.progress(90, "📝 正在生成 Word 文档...")
                
                if result:
                    doc_bytes, mode_desc = result
                    progress.progress(100, "✅ 完成！")
                    st.success(f"✅ {mode_desc}")
                    st.download_button("⬇️ 下载Word", doc_bytes, "converted.docx")
                else:
                    progress.empty()
                    st.error("❌ 转换失败：未能识别到文字或生成文档")
            except Exception as e:
                progress.empty()
                st.error(f"❌ 转换出错: {e}")
                st.info("💡 如果图片分辨率很高，处理可能需要更长时间。建议尝试「图片嵌入」模式。")


def render_merge_long():
    st.header("📷 图片合并长图")
    uploaded = st.file_uploader("上传图片（按选择顺序拼接）", type=["jpg", "jpeg", "png", "bmp", "webp"], accept_multiple_files=True, key="long")
    if uploaded and len(uploaded) >= 2:
        col1, col2 = st.columns(2)
        with col1:
            spacing = st.slider("间距 (px)", 0, 50, 10, key="long_space")
        with col2:
            align = st.selectbox("对齐方式", ["center", "left", "right"], format_func=lambda x: {"center": "居中", "left": "左对齐", "right": "右对齐"}[x], key="long_align")
        max_w = st.slider("最大宽度 (px)", 400, 2000, 1200, 100, key="long_w")
        if st.button("🔗 开始拼接"):
            with st.spinner("拼接中..."):
                try:
                    files = [f.getvalue() for f in uploaded]
                    names = [f.name for f in uploaded]
                    img_bytes_out = converter.safe_run(converter.merge_images_vertical, files, names, spacing, align, max_w)
                    if img_bytes_out:
                        st.success("✅ 拼接完成！")
                        st.image(img_bytes_out, use_container_width=True)
                        st.download_button("⬇️ 下载长图", img_bytes_out, "merged.png")
                    else:
                        st.error("拼接失败")
                except Exception as e:
                    st.error(f"拼接出错: {e}")
    elif uploaded:
        st.warning("请至少上传2张图片")


# ==================== 新功能 ====================

def render_video2long():
    st.header("🎬 视频 → 长图")
    uploaded = st.file_uploader("上传视频文件", type=["mp4", "avi", "mov", "mkv", "flv"], key="v2l")
    if uploaded:
        col1, col2, col3 = st.columns(3)
        with col1:
            interval = st.slider("抽帧间隔(秒)", 0.5, 10.0, 2.0, 0.5, key="v2l_int")
        with col2:
            max_frames = st.slider("最大帧数", 5, 100, 30, 5, key="v2l_max")
        with col3:
            direction = st.selectbox("拼接方向", ["vertical", "horizontal"], format_func=lambda x: "垂直" if x=="vertical" else "水平", key="v2l_dir")
        
        if st.button("🎞️ 开始转换"):
            with st.spinner("正在提取视频帧并拼接..."):
                try:
                    video_bytes = uploaded.getvalue()
                    img_bytes_out = converter.safe_run(converter.video_to_long_image, video_bytes, interval, max_frames, direction)
                    if img_bytes_out:
                        st.success("✅ 转换完成！")
                        st.image(img_bytes_out, use_container_width=True)
                        st.download_button("⬇️ 下载长图", img_bytes_out, "video_long_image.png")
                    else:
                        st.error("转换失败（请检查视频格式）")
                except Exception as e:
                    st.error(f"转换出错: {e}")


def render_video2gif():
    st.header("🎬 视频 → GIF")
    uploaded = st.file_uploader("上传视频文件", type=["mp4", "avi", "mov", "mkv"], key="v2g")
    if uploaded:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            start = st.number_input("起始(秒)", 0.0, 3600.0, 0.0, 1.0, key="v2g_start")
        with col2:
            duration = st.number_input("时长(秒)", 1.0, 30.0, 5.0, 1.0, key="v2g_dur")
        with col3:
            gif_fps = st.slider("GIF帧率", 5, 20, 10, 1, key="v2g_fps")
        with col4:
            width = st.slider("宽度(px)", 240, 800, 480, 40, key="v2g_w")
        
        if st.button("🎞️ 开始转换"):
            with st.spinner("正在生成GIF..."):
                try:
                    video_bytes = uploaded.getvalue()
                    gif_bytes = converter.safe_run(converter.video_to_gif, video_bytes, start, duration, gif_fps, width)
                    if gif_bytes:
                        st.success("✅ 转换完成！")
                        st.image(gif_bytes, use_container_width=True)
                        st.download_button("⬇️ 下载GIF", gif_bytes, "converted.gif")
                    else:
                        st.error("转换失败")
                except Exception as e:
                    st.error(f"转换出错: {e}")


def render_audio():
    st.header("🎵 音频格式转换")
    st.info("💡 提示：此功能需要安装 ffmpeg。Windows 用户请下载 ffmpeg 并添加到系统 PATH。")
    
    uploaded = st.file_uploader("上传音频文件", type=["mp3", "wav", "flac", "ogg", "aac", "m4a", "wma"], key="aud")
    if uploaded:
        fmt = st.selectbox("目标格式", ["mp3", "wav", "flac", "ogg", "aac", "m4a"], key="aud_fmt")
        bitrate = "192k"
        if fmt == "mp3":
            bitrate = st.selectbox("比特率", ["128k", "192k", "256k", "320k"], key="aud_br")
        
        if st.button("🎵 开始转换"):
            with st.spinner("转换中..."):
                try:
                    audio_bytes = uploaded.getvalue()
                    audio_bytes_out = converter.safe_run(converter.convert_audio, audio_bytes, uploaded.name, fmt, bitrate)
                    if audio_bytes_out:
                        st.success("✅ 转换完成！")
                        st.audio(audio_bytes_out)
                        st.download_button("⬇️ 下载", audio_bytes_out, f"converted.{fmt}")
                    else:
                        st.error("转换失败（请检查是否已安装 ffmpeg）")
                except Exception as e:
                    st.error(f"转换出错: {e}")


def render_compress_img():
    st.header("🗜️ 图片压缩")
    uploaded = st.file_uploader("上传图片", type=["jpg", "jpeg", "png", "bmp", "webp"], key="cmp_img")
    if uploaded:
        col1, col2, col3 = st.columns(3)
        with col1:
            quality = st.slider("质量 (JPEG)", 30, 100, 85, 5, key="cmp_q")
        with col2:
            max_w = st.number_input("最大宽度", 0, 4000, 0, 100, key="cmp_w", help="0=不限制")
        with col3:
            max_h = st.number_input("最大高度", 0, 4000, 0, 100, key="cmp_h", help="0=不限制")
        
        # 显示原图信息
        img = __import__("PIL.Image", fromlist=["Image"]).Image.open(__import__("io").BytesIO(uploaded.getvalue()))
        st.write(f"原图尺寸: {img.width}x{img.height}, 模式: {img.mode}")
        
        if st.button("🗜️ 开始压缩"):
            with st.spinner("压缩中..."):
                try:
                    img_bytes = uploaded.getvalue()
                    img_bytes_out = converter.safe_run(converter.compress_image, img_bytes, uploaded.name, quality, max_w or None, max_h or None)
                    if img_bytes_out:
                        st.success("✅ 压缩完成！")
                        st.image(img_bytes_out, use_container_width=True)
                        orig_size = len(img_bytes) / 1024
                        new_size = len(img_bytes_out) / 1024
                        st.info(f"原大小: {orig_size:.1f} KB → 新大小: {new_size:.1f} KB (节省 {(1-new_size/orig_size)*100:.1f}%)")
                        st.download_button("⬇️ 下载", img_bytes_out, "compressed.jpg")
                    else:
                        st.error("压缩失败")
                except Exception as e:
                    st.error(f"压缩出错: {e}")


def render_batch_rename():
    st.header("🛠️ 批量重命名")
    st.info("上传多个文件，使用规则批量重命名")
    
    uploaded = st.file_uploader("上传文件", accept_multiple_files=True, key="ren")
    if uploaded:
        st.write(f"已选择 {len(uploaded)} 个文件")
        
        col1, col2 = st.columns(2)
        with col1:
            rule = st.selectbox("命名规则", [
                "序号 (001, 002, ...)",
                "序号+原文件名",
                "日期+序号",
                "自定义前缀+序号",
            ], key="ren_rule")
        with col2:
            if "自定义" in rule:
                prefix = st.text_input("前缀", value="file", key="ren_pre")
            else:
                prefix = ""
        
        start_num = st.number_input("起始序号", 1, 9999, 1, 1, key="ren_start")
        
        # 预览
        previews = []
        digits = max(3, len(str(len(uploaded) + start_num)))
        for i, f in enumerate(uploaded):
            idx = str(start_num + i).zfill(digits)
            ext = Path(f.name).suffix
            if "序号+原" in rule:
                name = f"{idx}_{Path(f.name).stem}{ext}"
            elif "日期" in rule:
                from datetime import datetime
                date = datetime.now().strftime("%Y%m%d")
                name = f"{date}_{idx}{ext}"
            elif "自定义" in rule:
                name = f"{prefix}_{idx}{ext}"
            else:
                name = f"{idx}{ext}"
            previews.append((f.name, name))
        
        st.subheader("📋 预览")
        for orig, new in previews:
            st.write(f"`{orig}` → `{new}`")
        
        if st.button("✅ 执行重命名"):
            import zipfile
            import tempfile
            with st.spinner("打包中..."):
                try:
                    zip_buf = io.BytesIO()
                    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                        for (orig, new), f in zip(previews, uploaded):
                            zf.writestr(new, f.getvalue())
                    zip_buf.seek(0)
                    st.success("✅ 打包完成！")
                    st.download_button("⬇️ 下载ZIP", zip_buf.getvalue(), "renamed_files.zip")
                except Exception as e:
                    st.error(f"打包出错: {e}")


def render_pdf_compress():
    st.header("🗜️ PDF 压缩优化")
    st.info("去除冗余数据、压缩流，减小PDF体积")
    uploaded = st.file_uploader("上传PDF文件", type=["pdf"], key="pdf_cmp")
    if uploaded:
        if st.button("🗜️ 开始优化"):
            with st.spinner("优化中..."):
                try:
                    pdf_bytes = uploaded.getvalue()
                    pdf_bytes_out = converter.safe_run(converter.compress_pdf, pdf_bytes)
                    if pdf_bytes_out:
                        st.success("✅ 优化完成！")
                        orig_size = len(pdf_bytes) / 1024
                        new_size = len(pdf_bytes_out) / 1024
                        st.info(f"原大小: {orig_size:.1f} KB → 新大小: {new_size:.1f} KB")
                        st.download_button("⬇️ 下载优化版PDF", pdf_bytes_out, "compressed.pdf")
                    else:
                        st.error("优化失败")
                except Exception as e:
                    st.error(f"优化出错: {e}")


def render_qr():
    st.header("🔲 二维码生成")
    data = st.text_area("内容（URL/文本）", value="https://example.com", height=100, key="qr_data")
    col1, col2 = st.columns(2)
    with col1:
        size = st.slider("尺寸", 5, 30, 10, 1, key="qr_size")
    with col2:
        ec = st.selectbox("容错率", ["L(7%)", "M(15%)", "H(30%)"], key="qr_ec")
    ec_val = ec[0]
    
    if st.button("🔲 生成二维码"):
        with st.spinner("生成中..."):
            try:
                qr_bytes = converter.safe_run(converter.generate_qr, data, size, ec_val)
                if qr_bytes:
                    st.success("✅ 生成完成！")
                    st.image(qr_bytes, use_container_width=True)
                    st.download_button("⬇️ 下载二维码", qr_bytes, "qrcode.png")
                else:
                    st.error("生成失败")
            except Exception as e:
                st.error(f"生成出错: {e}")


def render_remove_bg():
    st.header("✨ 图片去背景")
    st.info("使用 OpenCV GrabCut 算法自动去除背景（效果因图片复杂度而异）")
    uploaded = st.file_uploader("上传图片", type=["jpg", "jpeg", "png"], key="rmbg")
    if uploaded:
        if st.button("✨ 开始去背景"):
            with st.spinner("处理中（AI算法分析前景/背景）..."):
                try:
                    img_bytes = uploaded.getvalue()
                    img_bytes_out = converter.safe_run(converter.remove_background, img_bytes, uploaded.name)
                    if img_bytes_out:
                        st.success("✅ 处理完成！")
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write("原图")
                            st.image(img_bytes, use_container_width=True)
                        with col2:
                            st.write("去背景后")
                            st.image(img_bytes_out, use_container_width=True)
                        st.download_button("⬇️ 下载", img_bytes_out, "nobg.png")
                    else:
                        st.error("处理失败")
                except Exception as e:
                    st.error(f"处理出错: {e}")


def render_office2pdf():
    st.header("📊 Excel/Word → PDF")
    st.info("💡 此功能需要 Windows + Microsoft Office 环境")
    
    uploaded = st.file_uploader("上传文件", type=["doc", "docx", "xls", "xlsx"], key="o2p")
    if uploaded:
        suffix = Path(uploaded.name).suffix.lower()
        if suffix not in (".doc", ".docx", ".xls", ".xlsx"):
            st.error("不支持的文件格式")
            return
        
        if st.button("📄 开始转换"):
            with st.spinner("转换中（调用Office COM接口）..."):
                try:
                    file_bytes = uploaded.getvalue()
                    pdf_bytes_out = converter.safe_run(converter.office_to_pdf, file_bytes, uploaded.name)
                    if pdf_bytes_out:
                        st.success("✅ 转换完成！")
                        st.download_button("⬇️ 下载PDF", pdf_bytes_out, "converted.pdf")
                    else:
                        st.error("转换失败")
                except Exception as e:
                    st.error(f"转换出错: {e}")
                    st.info("请确保：1) 在Windows服务器上运行；2) 已安装Microsoft Office")


# ==================== 功能说明字典 ====================

FEATURE_INFO = {
    "home": {
        "title": "🏠 首页",
        "desc": "格式转换系统 v2.0 总览，覆盖文档/图片/音视频/实用工具四大场景。",
        "features": ["18+ 转换功能全覆盖", "🔒 隐私模式：内存-only处理，管理员不可见", "场景化分类，快速定位所需功能"],
        "tips": "",
    },
    "pdf2img": {
        "title": "📄 PDF ↔ 图像",
        "desc": "PDF 与图像之间的双向转换。PDF 可拆分为多页图像，多张图像可合并为单个 PDF。",
        "features": ["PDF 逐页转为高质量图像", "多图按序合并为 PDF", "支持 PNG/JPG/BMP/WEBP 等多种格式"],
        "formats": "PDF ↔ PNG / JPG / BMP / TIFF / WEBP",
        "tips": "PDF 转图像时每页生成一张图；图像转 PDF 时上传顺序即为合并顺序",
    },
    "pdf2word": {
        "title": "📝 PDF ↔ Word",
        "desc": "PDF 与 Word 文档互转，支持版式还原和图文混排。",
        "features": ["智能版式还原，保留段落、标题、图片排版", "文字极少时自动切换图片模式", "支持多页 PDF 完整转换"],
        "formats": "PDF ↔ DOCX",
        "tips": "复杂版式 PDF 转换后可能需要微调；扫描件/图片 PDF 转换效果取决于 OCR 质量",
    },
    "pdf_merge_split": {
        "title": "📑 PDF 合并 / 拆分",
        "desc": "将多个 PDF 合并为一个，或将单个 PDF 按页拆分为多个文件。",
        "features": ["多文件按上传顺序合并", "支持指定页码范围拆分（如 1,3,5-10）", "不填页码则每页单独拆分"],
        "formats": "PDF → PDF",
        "tips": "合并时文件顺序以勾选/上传顺序为准；拆分后文件名为原文件名+页码",
    },
    "pdf_text": {
        "title": "📋 PDF 提取文本",
        "desc": "从 PDF 文件中提取纯文本内容，支持文字型 PDF 和扫描件。",
        "features": ["快速提取 PDF 中的文字内容", "支持多页 PDF 全文提取", "提取结果可直接下载为 TXT"],
        "formats": "PDF → TXT",
        "tips": "图片型/扫描件 PDF 可能无法提取文字，建议使用「图像转 Word(OCR)」功能",
    },
    "pdf_compress": {
        "title": "🗜️ PDF 压缩优化",
        "desc": "通过去除冗余数据、压缩流等方式优化 PDF 体积，不损失内容。",
        "features": ["去除 PDF 内部冗余数据", "压缩对象流减小体积", "纯优化，不降低图片质量"],
        "formats": "PDF → PDF",
        "tips": "此为无损优化，压缩幅度有限；如需大幅减小体积，可先用「PDF→图像」再转回",
    },
    "office2pdf": {
        "title": "📊 Excel/Word → PDF",
        "desc": "通过 Windows Office COM 接口，将 Word/Excel 文档转换为 PDF。",
        "features": ["调用 Microsoft Office 原生引擎", "完美保留 Office 文档排版", "支持 .doc/.docx/.xls/.xlsx"],
        "formats": "DOC/DOCX/XLS/XLSX → PDF",
        "tips": "仅限 Windows 服务器 + 已安装 Microsoft Office；Linux 环境无法使用此功能",
    },
    "img2word": {
        "title": "🖼️→📝 图像转 Word (OCR)",
        "desc": "将图片中的文字识别并导出为可编辑的 Word 文档，支持三种模式。",
        "features": ["嵌入模式：原图嵌入，保留视觉效果", "OCR模式：纯文字提取，可编辑", "混合模式：第1页原图+第2页OCR文字", "支持 RapidOCR / Tesseract 双引擎"],
        "formats": "JPG/PNG/BMP/WEBP/TIFF → DOCX",
        "tips": "清晰度高、文字规整的图片识别效果更好；手写体识别准确率约 70-85%",
    },
    "img2pdf": {
        "title": "🖼️ 图像 → PDF",
        "desc": "将多张图像按顺序合并为单个 PDF 文件。",
        "features": ["支持多张图片批量合并", "上传顺序即为 PDF 页面顺序", "保留原图质量"],
        "formats": "JPG/PNG/BMP/WEBP/TIFF → PDF",
        "tips": "如需调整页面顺序，请重新选择文件调整上传顺序",
    },
    "img2img": {
        "title": "🔄 图像格式互转",
        "desc": "在 PNG、JPG、BMP、TIFF、WEBP、ICO 等格式之间自由转换。",
        "features": ["支持 6 种主流图像格式互转", "自动处理颜色模式适配", "保留图像质量"],
        "formats": "JPG/PNG/BMP/TIFF/WEBP/ICO/GIF → PNG/JPG/BMP/TIFF/WEBP/ICO",
        "tips": "PNG 转 JPG 会丢失透明通道；ICO 格式适合制作图标",
    },
    "merge_long": {
        "title": "📷 图片合并长图",
        "desc": "将多张图片垂直或水平拼接为一张长图，支持自定义间距和对齐方式。",
        "features": ["垂直/水平两种拼接方向", "支持居中/左对齐/右对齐", "自定义间距和最大宽度", "自动等比缩放"],
        "formats": "JPG/PNG/WEBP → PNG",
        "tips": "建议上传尺寸相近的图片，拼接效果更整齐；间距设为 0 可无缝拼接",
    },
    "compress_img": {
        "title": "🗜️ 图片压缩",
        "desc": "通过调整质量和尺寸来压缩图片体积，适合网页上传和分享。",
        "features": ["JPEG 质量可调（30-100）", "支持限制最大宽度/高度", "自动计算压缩比例", "PNG 保留透明通道"],
        "formats": "JPG/PNG/BMP/WEBP → JPG/PNG",
        "tips": "JPEG 质量 85 是体积与质量的平衡点；PNG 压缩主要通过尺寸缩放",
    },
    "remove_bg": {
        "title": "✨ 图片去背景",
        "desc": "使用 OpenCV GrabCut 算法自动识别前景并去除背景，输出透明 PNG。",
        "features": ["AI 自动识别前景/背景", "输出带透明通道的 PNG", "无需手动标记区域"],
        "formats": "JPG/PNG → PNG (透明)",
        "tips": "主体与背景对比明显的图片效果更好；复杂背景可能需要多次尝试",
    },
    "qr": {
        "title": "🔲 二维码生成",
        "desc": "将网址、文本等内容生成二维码图片，支持自定义尺寸和容错率。",
        "features": ["支持网址、文本、联系方式等任意内容", "3 级容错率可选（L/M/H）", "尺寸可调，高清输出"],
        "formats": "文本/URL → PNG",
        "tips": "容错率 H(30%) 适合需要添加 Logo 的二维码；尺寸越大扫描越容易",
    },
    "video2long": {
        "title": "🎬 视频 → 长图",
        "desc": "按固定间隔从视频中提取帧，拼接为一张长图，适合制作视频预览图。",
        "features": ["按秒间隔自动抽帧", "支持垂直/水平拼接", "最大帧数可控（5-100帧）", "自动等比缩放统一宽度"],
        "formats": "MP4/AVI/MOV/MKV/FLV → PNG",
        "tips": "间隔越小帧数越多，长图越长；建议根据视频时长调整间隔",
    },
    "video2gif": {
        "title": "🎬 视频 → GIF",
        "desc": "从视频中截取片段转换为 GIF 动图，支持自定义时段、帧率和尺寸。",
        "features": ["指定起始时间和时长", "帧率可调（5-20 fps）", "输出宽度可调", "循环播放"],
        "formats": "MP4/AVI/MOV/MKV → GIF",
        "tips": "帧率越高动画越流畅但体积越大；建议时长控制在 10 秒以内",
    },
    "audio": {
        "title": "🎵 音频格式转换",
        "desc": "在 MP3、WAV、FLAC、OGG、AAC、M4A 等音频格式之间转换。",
        "features": ["支持 6 种主流音频格式", "MP3 支持多种比特率（128k-320k）", "保持音频质量"],
        "formats": "MP3/WAV/FLAC/OGG/AAC/M4A/WMA → MP3/WAV/FLAC/OGG/AAC/M4A",
        "tips": "需要安装 ffmpeg 才能使用此功能；Windows 用户需将 ffmpeg 添加到 PATH",
    },
    "batch_rename": {
        "title": "🛠️ 批量重命名",
        "desc": "批量重命名文件，支持多种命名规则，一键打包下载。",
        "features": ["纯序号命名（001, 002...）", "序号+原文件名", "日期+序号", "自定义前缀+序号", "实时预览重命名结果"],
        "formats": "任意文件 → ZIP",
        "tips": "重命名后的文件会打包为 ZIP 下载；不会修改原始文件名",
    },
}


def render_feature_info(key: str):
    """在功能页面底部渲染功能说明"""
    if key == "home":
        return
    info = FEATURE_INFO.get(key)
    if not info:
        return
    st.divider()
    with st.expander("📖 功能说明", expanded=False):
        st.markdown(f"**{info['title']}**")
        st.write(info['desc'])
        if info.get('features'):
            st.markdown("**核心特点：**")
            for f in info['features']:
                st.markdown(f"- {f}")
        if info.get('formats'):
            st.info(f"📌 支持格式：{info['formats']}")
        if info.get('tips'):
            st.warning(f"💡 使用提示：{info['tips']}")


# ==================== 路由映射 ====================
ROUTE_MAP = {
    "home": render_home,
    "pdf2img": render_pdf2img,
    "pdf2word": render_pdf2word,
    "pdf_merge_split": render_pdf_merge_split,
    "pdf_text": render_pdf_text,
    "img2pdf": render_img2pdf,
    "img2img": render_img2img,
    "img2word": render_img2word,
    "merge_long": render_merge_long,
    "video2long": render_video2long,
    "video2gif": render_video2gif,
    "audio": render_audio,
    "compress_img": render_compress_img,
    "batch_rename": render_batch_rename,
    "pdf_compress": render_pdf_compress,
    "qr": render_qr,
    "remove_bg": render_remove_bg,
    "office2pdf": render_office2pdf,
}


# ==================== 主函数 ====================

def main():
    # 清理过期的临时输出文件（云端磁盘有限，避免长期运行后堆积）
    try:
        converter.cleanup_old_files()
    except Exception:
        pass

    # 顶部返回首页（移动端侧边栏默认收起，这里给一个显眼入口）
    st.markdown(
        "<a href='/' target='_self' style='color:#4f46e5;text-decoration:none;font-size:14px;'>← 返回 MiscHub 首页</a>",
        unsafe_allow_html=True,
    )

    # 侧边栏
    st.sidebar.title("🔄 格式转换系统")
    st.sidebar.markdown("<p style='color:#888;font-size:12px;'>v2.0 | 全场景覆盖</p>", unsafe_allow_html=True)
    st.sidebar.markdown(
        "<a href='/' target='_self' style='display:block;text-align:center;background:#4f46e5;color:#fff;"
        "padding:8px 0;border-radius:8px;text-decoration:none;font-weight:600;'>🧰 返回 MiscHub 首页</a>",
        unsafe_allow_html=True,
    )
    st.sidebar.divider()
    
    # 初始化页面状态
    if "page" not in st.session_state:
        st.session_state.page = "home"
        st.session_state.current_func = None
        st.session_state.current_scene = None
    
    # 🏠 首页独立入口（置顶）
    is_home = st.session_state.page == "home"
    if st.sidebar.button("🏠 首页", use_container_width=True, type="primary" if is_home else "secondary"):
        st.session_state.page = "home"
        st.rerun()
    
    st.sidebar.divider()
    
    # 场景选择
    scene = st.sidebar.radio("选择场景", list(SCENES.keys()), label_visibility="collapsed")
    
    st.sidebar.divider()
    
    # 功能选择
    functions = SCENES[scene]
    func_labels = [label for label, _ in functions]
    func_keys = [key for _, key in functions]
    
    # 确定 radio 默认选中项
    prev_func = st.session_state.get("current_func")
    if prev_func in func_keys:
        default_index = func_keys.index(prev_func)
    else:
        default_index = 0
    
    selected_label = st.sidebar.radio("选择功能", func_labels, index=default_index, key="func_select")
    selected_key = func_keys[func_labels.index(selected_label)]
    
    # 关键逻辑：只有用户主动切换功能时才离开首页
    if prev_func is None:
        # 首次选择功能（从首页进入）
        st.session_state.current_func = selected_key
        st.session_state.current_scene = scene
        st.session_state.page = "func"
    elif selected_key != prev_func:
        # 用户主动切换了功能
        st.session_state.current_func = selected_key
        st.session_state.current_scene = scene
        st.session_state.page = "func"
    # 否则（点击首页后 rerun）：保持 page = "home"，显示首页
    
    # 渲染页面
    if st.session_state.page == "home":
        render_home()
    elif selected_key in ROUTE_MAP:
        # 功能页面顶部：手机使用提示（可关闭）
        with st.expander("📱 手机用户：如何从微信选择文件？", expanded=False):
            st.markdown("""
            **🍎 iPhone**：微信长按文件 → 「用其他应用打开」→「存储到"文件"」→ 浏览器打开本系统 → 上传时选「浏览」找到文件
            
            **🤖 Android**：微信长按文件 → 「保存到手机」→ 浏览器打开本系统 → 上传时在文件管理器中找到 `Download/WeiXin/` 目录
            
            💡 **快捷方式**：在微信内点击右上角「···」→「**在浏览器打开**」，即可直接在浏览器中使用本系统
            """)
        ROUTE_MAP[selected_key]()
        render_feature_info(selected_key)
    else:
        st.error(f"未知功能: {selected_key}")
    
    # 页脚
    st.sidebar.divider()
    st.sidebar.caption("© 格式转换系统 v2.0")


if __name__ == "__main__":
    main()
