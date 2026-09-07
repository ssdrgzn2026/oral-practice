# 🔄 格式转换系统

基于 Python + Streamlit 的全功能文件格式转换工具，支持 PDF、图像、Word 等多种常见格式互转。所有转换在**本地完成**，文件不上传云端，保护隐私安全。

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-ff4b4b.svg)](https://streamlit.io)

---

## ✨ 功能特性

| 功能 | 输入格式 | 输出格式 | 说明 |
|------|---------|---------|------|
| 📄→🖼️ **PDF 转图像** | PDF | PNG / JPG / WEBP / TIFF / BMP | 支持自定义 DPI（72~400）和页码范围 |
| 🖼️→📄 **图像转 PDF** | PNG / JPG / WEBP / BMP / TIFF / GIF | PDF | 单张输出或多张合并为单个 PDF |
| 📄→📝 **PDF 转 Word** | PDF | DOCX | 保留原始排版格式 |
| 🔄 **图像格式互转** | 任意图像 | PNG / JPG / WEBP / BMP / TIFF / GIF | 自动处理透明通道（转 JPG 时合成白底） |
| 📑 **PDF 合并** | 多个 PDF | 合并后的 PDF | 按上传顺序合并 |
| ✂️ **PDF 拆分** | PDF | 多个 PDF（ZIP 打包） | 每页独立或按自定义范围拆分 |
| 📝 **PDF 提取文本** | PDF | TXT | 提取纯文本内容，支持页面预览 |

---

## 🚀 快速开始

### 方式一：一键启动（Windows）

双击运行目录下的 `start.bat` 文件，系统自动安装依赖并启动服务。

### 方式二：命令行启动

```bash
# 1. 进入项目目录
cd 格式转换系统

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动服务
streamlit run app.py
```

服务启动后，浏览器会自动打开 `http://localhost:8501`。

---

## 📁 项目结构

```
格式转换系统/
├── app.py              # Streamlit 前端主程序
├── converter.py        # 核心转换引擎
├── start.bat           # Windows 一键启动脚本
├── requirements.txt    # Python 依赖清单
├── README.md           # 项目说明文档
└── output/             # 转换结果输出目录
```

---

## 🛠️ 技术栈

- **[Streamlit](https://streamlit.io/)** — Web 应用框架
- **[PyMuPDF](https://pymupdf.readthedocs.io/)** — PDF 解析、渲染、拆分、合并
- **[pdf2docx](https://github.com/dothinking/pdf2docx)** — PDF 转 Word
- **[python-docx](https://python-docx.readthedocs.io/)** — Word 文档处理
- **[Pillow](https://pillow.readthedocs.io/)** — 图像格式转换与处理

---

## 🖥️ 界面预览

### 首页
- 卡片式功能导航
- 使用步骤说明
- 技术特性介绍

### 转换页面
- **文件上传区**：拖拽或点击上传
- **参数设置区**：格式选择、DPI、页码范围等
- **转换按钮**：一键执行
- **结果下载区**：转换完成后直接下载

---

## ⚠️ 注意事项

1. **PDF 转 Word**：复杂排版（如多栏图文混排、特殊字体）可能无法 100% 还原，建议转换后手动微调。
2. **图像转 PDF**：多张图像合并时保持原始分辨率，不压缩画质。
3. **PDF 拆分**：页码范围格式为 `1-3,5,7-9`（英文逗号和连字符）。
4. **输出文件**：转换结果保存在 `output/` 目录下，24 小时后自动清理。

---

## 📄 开源协议

MIT License — 可自由使用、修改和分发。

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request，一起完善这个工具！
