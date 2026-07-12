# 🎙️ 口语练习系统

一个为大学生设计的口语练习工具，无需联网即可使用本地练习功能。

## 功能模块

| 模块 | 说明 |
|------|------|
| **AI 情景对话** | 可选日常闲聊 / 英文面试 / 观点辩论 / 学术讨论，AI 陪你练口语 |
| **话题独白** | 随机抽取口语话题，计时录音并语音识别 |
| **影子跟读** | 提供地道短文与发音提示，先听后读 |
| **每日表达** | 高频口语表达 + 例句，跟读练习 |
| **练习记录** | 自动保存练习内容到本地 |

## 环境要求

- Python 3.10+
- Windows 10/11
- 浏览器：**Chrome 或 Edge**（语音识别依赖 Web Speech API）

## 快速启动

1. 双击运行 `start.bat`
2. 等待浏览器自动打开 `http://127.0.0.1:5000`
3. 选择练习模块开始

首次启动会自动创建 `.venv` 虚拟环境并安装依赖。

## 配置 AI 对话（可选）

如果只想用本地练习功能（话题独白、影子跟读、每日表达），**无需任何配置**。

若要使用 AI 对话，双击 `configure.bat`，按提示输入 API Key 和 Base URL，然后重新启动系统即可。

支持任意 OpenAI 兼容接口，例如 Kimi、DeepSeek、OpenAI 等。

## 项目结构

```
口语练习/
├── app.py                 # Flask 后端
├── requirements.txt       # 依赖
├── Dockerfile             # Docker 镜像
├── docker-compose.yml     # Docker 部署配置
├── start.bat              # 本地一键启动脚本
├── configure.bat          # 本地 API 配置入口
├── configure_api.py       # 本地 API 配置脚本
├── config.bat             # 生成的本地 API 配置（由 configure.bat 生成）
├── .github/workflows/     # GitHub Actions 自动部署
├── data/
│   ├── topics.json        # 题库与素材
│   └── history.jsonl      # 练习记录（自动生成）
├── static/
│   ├── css/style.css      # 样式
│   └── js/app.js          # 前端逻辑
└── templates/index.html   # 主页面
```

## 部署到服务器（最小可行版）

### 1. 本地准备

```bash
git add .
git commit -m "init oral practice system"
```

### 2. 在 GitHub 创建仓库

登录 GitHub，新建一个仓库（例如 `oral-practice`），不要初始化 README。

### 3. 推送代码

```bash
git remote add origin https://github.com/你的用户名/oral-practice.git
git push -u origin main
```

### 4. 配置 GitHub Secrets

进入仓库 → Settings → Secrets and variables → Actions → New repository secret，添加：

| Secret 名 | 说明 |
|---|---|
| `ORAL_HOST` | 平叙平台服务器 IP 地址 |
| `ORAL_USERNAME` | SSH 用户名（通常是 root 或 ubuntu） |
| `ORAL_SSH_KEY` | SSH 私钥（~/.ssh/id_rsa 的内容） |
| `OPENAI_API_KEY` | （可选）AI 对话 API Key |
| `OPENAI_BASE_URL` | （可选）API Base URL，默认 `https://api.openai.com/v1` |
| `OPENAI_MODEL` | （可选）模型名，默认 `gpt-4o-mini` |

### 5. 服务器上准备目录

SSH 登录服务器，执行：

```bash
sudo mkdir -p /opt/oral-practice
sudo chown $USER:$USER /opt/oral-practice
```

确保服务器已安装 Docker 和 Docker Compose：

```bash
docker --version
docker compose version
```

### 6. 自动部署

每次 push 到 `main` 分支，GitHub Actions 会自动：
- 构建 Docker 镜像
- 上传到服务器
- 启动/重启容器

部署完成后，访问：

```
http://服务器IP:5000
```

手机浏览器打开同一个链接即可使用。

### 7. 协作开发

其他电脑：

```bash
git clone https://github.com/你的用户名/oral-practice.git
cd oral-practice
# 修改代码
git add .
git commit -m "update"
git push origin main
```

push 后会自动部署到服务器。

## 使用建议

- **每天坚持 15 分钟**：话题独白 5 分钟 + 影子跟读 5 分钟 + 每日表达 5 分钟。
- **大声说出来**：语音识别只能识别你真正说出的内容，不要默念。
- **回看记录**：定期在“练习记录”里回顾自己的表达，找出重复错误。

## 常见问题

**Q：麦克风没反应？**  
A：请使用 Chrome 或 Edge，并确保浏览器已授权麦克风权限。

**Q：AI 对话提示未配置 API？**  
A：双击 `configure.bat` 配置 API 后重启；不配置也能使用其他三个模块。

**Q：识别准确率不高？**  
A：尽量在安静环境练习，语速适中，发音清晰。识别结果仅供参考，重点是开口说。

## 许可证

仅供个人学习使用。

