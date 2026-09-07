# 🧰 MiscHub｜杂具小栈

一站式零散工具工作台。线上地址：https://oral.pingxu.xin/

## 功能模块

| 模块 | 路径 | 技术栈 | 说明 |
|------|------|--------|------|
| **口语AI伴侣** | `/oral` | Flask Blueprint + Web Speech API | AI 情景对话、话题独白、影子跟读、每日表达、雅思口语、练习记录 |
| **格式转换系统** | `/convert/` | Streamlit | PDF / Word / 图片 / 音视频等 18+ 种格式互转，本地处理，隐私安全 |
| **DCF 工具** | `/dcf/` | Streamlit | 两阶段/三阶段现金流折现估值，敏感性分析，支持年报数据自动抓取 |

### 口语AI伴侣子功能

- **AI 情景对话**：可选日常闲聊 / 英文面试 / 观点辩论 / 学术讨论
- **话题独白**：随机抽取口语话题，计时录音并语音识别
- **影子跟读**：提供地道短文与发音提示，先听后读
- **每日表达**：高频口语表达 + 例句，跟读练习
- **雅思口语**：Part 1 → Part 2 话题卡 → Part 3 全流程模拟
- **练习记录**：自动保存练习内容，按匿名用户 ID 隔离

## 环境要求

- Python 3.10+（本地运行口语模块）
- 格式转换 / DCF 模块建议直接用 Docker 运行
- 浏览器：**Chrome 或 Edge**（语音识别依赖 Web Speech API）

## 快速启动（本地）

口语模块（主站）：

1. 双击运行 `start.bat`
2. 等待浏览器自动打开 `http://127.0.0.1:5000`

格式转换 / DCF 模块（本地开发，可选）：

```bash
pip install -r 格式转换系统/requirements.txt
streamlit run 格式转换系统/app.py --server.port=8501

pip install -r DCF估值分析系统/requirements.txt
streamlit run DCF估值分析系统/streamlit_app.py --server.port=8502
```

启动后首页点击对应卡片会自动跳转到本地 8501 / 8502 端口。

## 配置 AI 对话（可选）

若要使用 AI 对话，双击 `configure.bat`，按提示输入 API Key 和 Base URL，然后重新启动系统即可。支持任意 OpenAI 兼容接口（Kimi、DeepSeek、OpenAI 等）。

## 项目结构

```
MiscHub/
├── app.py                 # Flask 主应用（首页导航 + 加载口语 Blueprint）
├── requirements.txt       # 主应用依赖
├── Dockerfile             # 主应用镜像（Flask + gunicorn）
├── Dockerfile.streamlit   # Streamlit 模块镜像（格式转换 + DCF 共用）
├── docker-compose.yml     # 三个服务：mischub / mischub-convert / mischub-dcf
├── start.bat              # 本地一键启动脚本
├── configure.bat          # 本地 API 配置入口
├── configure_api.py       # 本地 API 配置脚本
├── .github/workflows/     # GitHub Actions 自动部署
├── templates/index.html   # MiscHub 工具导航首页
├── static/css/style.css   # 首页样式
├── 口语AI伴侣/            # 口语模块（Flask Blueprint）
│   ├── blueprint.py       # 口语模块路由与 API
│   ├── templates/oral.html
│   ├── static/css|js/
│   └── data/topics.json   # 题库与素材（history.jsonl 自动生成）
├── 格式转换系统/          # Streamlit 应用
│   ├── app.py
│   └── converter.py       # 转换核心逻辑
└── DCF估值分析系统/       # Streamlit 应用
    ├── streamlit_app.py
    └── core/              # DCF 计算引擎与数据抓取
```

## 部署架构

```
浏览器
  │  https://oral.pingxu.xin
  ▼
nginx (443)
  ├── /          → mischub (Flask, 127.0.0.1:5000)
  ├── /convert/  → mischub-convert (Streamlit, 127.0.0.1:8501, WebSocket)
  └── /dcf/      → mischub-dcf (Streamlit, 127.0.0.1:8502, WebSocket)
```

每次 push 到 `main` 分支，GitHub Actions 会将源码上传到服务器（`/opt/oral-practice`），在服务器上构建镜像并用 docker compose 重启三个服务。

### GitHub Secrets

| Secret 名 | 说明 |
|---|---|
| `ORAL_HOST` | 服务器地址 |
| `ORAL_USERNAME` | SSH 用户名 |
| `ORAL_PASSWORD` | SSH 密码 |
| `OPENAI_API_KEY` | （可选）AI 对话 API Key |
| `OPENAI_BASE_URL` | （可选）API Base URL |
| `OPENAI_MODEL` | （可选）模型名，默认 `gpt-4o-mini` |
| `OPENAI_WHISPER_MODEL` | （可选）语音转写模型 |

## 常见问题

**Q：麦克风没反应？**
A：请使用 Chrome 或 Edge，并确保浏览器已授权麦克风权限。

**Q：AI 对话提示未配置 API？**
A：双击 `configure.bat` 配置 API 后重启；不配置也能使用口语模块的其他功能。

**Q：格式转换 / DCF 页面打不开？**
A：生产环境检查 `docker ps` 确认 `mischub-convert` / `mischub-dcf` 容器在运行；本地开发需先按上文手动启动对应的 Streamlit 服务。

## 许可证

仅供个人学习使用。
