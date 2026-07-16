<p align="center">
  <img src="https://img.shields.io/badge/version-v2.0-5b8def?style=flat-square" alt="version">
  <img src="https://img.shields.io/badge/python-3.13+-4cd964?style=flat-square" alt="python">
  <img src="https://img.shields.io/badge/license-MIT-a855f7?style=flat-square" alt="license">
  <img src="https://img.shields.io/badge/Docker-✓-2496ED?style=flat-square" alt="docker">
  <img src="https://img.shields.io/docker/pulls/mrtangv/tg-monitor?style=flat-square" alt="pulls">
</p>

<h1 align="center">📊 TG Monitor</h1>
<p align="center"><strong>Telegram 群聊管理监控面板</strong></p>
<p align="center">
  🤖 Bot 接入 · 📊 实时看板 · 🔑 反馈检测 · ⚡ Bark 推送 · 🖼️ 图片日报
</p>

---

## 简介

**TG Monitor** 是一个开源的 Telegram 群聊管理监控系统。通过 Telegram Bot 接入群组，提供实时消息监控、反馈关键词检测、每日汇总报告，并支持 Bark 推送通知到手机。

---

## 🐳 Docker Compose 部署（推荐）

### 1Panel 应用商店格式

```yaml
networks:
    1panel-network:
        external: true

services:
    tg-monitor:
        container_name: ${CONTAINER_NAME}
        image: mrtangv/tg-monitor:latest
        deploy:
            resources:
                limits:
                    cpus: ${CPUS}
                    memory: ${MEMORY_LIMIT}
        environment:
            - TZ=Asia/Shanghai
        labels:
            createdBy: Apps
        networks:
            - 1panel-network
        ports:
            - ${HOST_IP}:${PANEL_APP_PORT_HTTP}:8080
        restart: always
        user: "0:0"
        volumes:
            - ./data:/app/data
```

### `.env` 配置文件

在同目录下创建 `.env` 文件：

```ini
CONTAINER_NAME=tg-monitor
CPUS=1
MEMORY_LIMIT=512M
HOST_IP=0.0.0.0
PANEL_APP_PORT_HTTP=8080
```

### 通用 Docker 部署

```bash
# 拉取镜像
docker pull mrtangv/tg-monitor:latest

# 启动容器
docker run -d \
  --name tg-monitor \
  -p 8080:8080 \
  -v ./data:/app/data \
  --restart unless-stopped \
  mrtangv/tg-monitor:latest
```

```bash
# 或使用 docker compose
curl -O https://raw.githubusercontent.com/hanxuan47/tg-monitor/main/docker-compose.yml
curl -O https://raw.githubusercontent.com/hanxuan47/tg-monitor/main/.env.example
cp .env.example .env
docker compose up -d
```

> 镜像发布在 Docker Hub: **mrtangv/tg-monitor:latest**，自动构建，开箱即用。

---

## 📦 手动部署

```bash
# 1. 克隆项目
git clone https://github.com/hanxuan47/tg-monitor.git
cd tg-monitor

# 2. 安装依赖（推荐使用 uv）
uv venv
uv pip install -r requirements.txt

# 3. 启动
uvicorn main:app --host 0.0.0.0 --port 8080

# 4. 打开浏览器访问
open http://localhost:8080
```

---

## 🚀 使用指南

### 第一步：创建 Telegram Bot

| 步骤 | 操作 |
|:----:|------|
| 1 | 在 Telegram 中打开 [@BotFather](https://t.me/BotFather) |
| 2 | 发送 `/newbot`，按提示创建 Bot |
| 3 | 记下 BotFather 给你的 **HTTP Token**（格式: `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`） |
| 4 | 发送 `/setprivacy` → 选择你的 Bot → **Disable**（关闭隐私模式） |
| 5 | 将 Bot **添加到群组**并设为管理员（至少需要消息读取权限） |

### 第二步：启动监控

```
面板 → Telegram 连接 → 🤖 Bot 模式 → 填入 Token → 点击「启动」
```

### 第三步：配置反馈关键词（可选）

```
面板 → 反馈监控 → 添加关键词（如: 反馈、求助、bug、错误、问题）
```

群聊中出现包含关键词的消息时，系统会自动标记并推送通知。

### 第四步：配置 Bark 推送（可选）

| 步骤 | 操作 |
|:----:|------|
| 1 | 在 App Store 下载 [Bark](https://bark.day.app) |
| 2 | 打开 Bark App，复制你的推送密钥 |
| 3 | 面板 → **Bark 通知** → 填入密钥 → 保存 → 测试 |

### 第五步：查看日报

```
面板 → 日报汇总 → 生成图片 → 查看每日群聊报告
```

---

## 📊 面板功能

| 页面 | 功能 |
|------|------|
| 📊 **总览** | 统计卡片 + 7 天趋势图 + 活跃群组 |
| 👥 **群组管理** | 查看/添加/移除群组 |
| 💬 **消息监控** | 实时消息流，反馈高亮 |
| 🔔 **反馈监控** | 关键词管理 + 反馈记录 |
| 📋 **日报汇总** | 文本/图片报告 + 定时任务 |
| 🤖 **Telegram 连接** | Bot / Telethon 模式切换 |
| ⚡ **Bark 通知** | 推送配置 + 测试 |

---

## 🔧 设置每日定时日报

在 Hermes 终端中执行：

```bash
cronjob action=create schedule='0 22 * * *' name='tg-daily-report' \
  prompt='运行 TG Monitor 每日群聊日报汇总。为所有活跃群组生成报告图片，如有 Bark 配置则发送推送通知。最后输出汇总文本。' \
  skills='[]' deliver='origin'
```

或在面板 → **日报汇总** → **定时任务** 查看设置指引。

---

## 🏗️ 项目结构

```
tg-monitor/
├── main.py              # FastAPI 后端 + API 路由
├── database.py          # SQLite 异步数据库层
├── bot_monitor.py       # Telegram Bot 监控（Bot API）
├── telegram_monitor.py  # Telethon 监控（用户账号）
├── bark_notify.py       # Bark iOS 推送
├── report_image.py      # 日报图片生成（Pillow）
├── templates/
│   └── dashboard.html   # 暗色主题 Web 面板
├── Dockerfile           # 镜像构建
├── docker-compose.yml   # 1Panel 编排格式
└── requirements.txt     # Python 依赖
```

### 技术栈

| 层 | 技术 |
|:---|:----|
| 后端 | Python 3.13+, FastAPI, Uvicorn |
| 数据库 | SQLite (aiosqlite) |
| Telegram | python-telegram-bot / Telethon |
| 图片 | Pillow, wqy-zenhei 中文字体 |
| 前端 | 单页 HTML + Chart.js + Font Awesome |
| 推送 | Bark API (iOS) |
| 部署 | Docker, docker-compose, GitHub Actions |

---

## 🌐 API 接口

### 监控管理

| 方法 | 路径 | 说明 |
|:----:|------|:----:|
| POST | `/api/monitor/bot/start` | 启动 Bot 监控 |
| POST | `/api/monitor/bot/stop` | 停止 Bot |
| GET | `/api/monitor/bot/info` | 查看 Bot 信息 |
| POST | `/api/monitor/telethon/start` | 启动 Telethon |
| POST | `/api/monitor/telethon/stop` | 停止 Telethon |
| GET | `/api/monitor/status` | 监控状态 |
| POST | `/api/monitor/stop` | 停止所有 |

### 群组 & 消息

| 方法 | 路径 | 说明 |
|:----:|------|:----:|
| GET | `/api/groups` | 群组列表 |
| POST | `/api/groups/add` | 添加群组 |
| POST | `/api/groups/remove` | 移除群组 |
| GET | `/api/messages` | 消息列表 |
| GET | `/api/stats` | 统计数据 |

### 关键词 & 报告

| 方法 | 路径 | 说明 |
|:----:|------|:----:|
| GET | `/api/keywords` | 关键词列表 |
| POST | `/api/keywords/add` | 添加关键词 |
| POST | `/api/keywords/remove` | 移除关键词 |
| GET | `/api/reports` | 日报列表 |
| POST | `/api/reports/generate` | 生成日报 |
| POST | `/api/reports/generate-image` | 生成图片日报 |
| GET | `/api/reports/images` | 报告图片列表 |

### Bark & 配置

| 方法 | 路径 | 说明 |
|:----:|------|:----:|
| POST | `/api/bark/test` | 测试推送 |
| POST | `/api/bark/send` | 自定义推送 |
| GET | `/api/config` | 获取配置 |
| POST | `/api/config` | 更新配置 |

---

## 📝 开发

```bash
git clone https://github.com/hanxuan47/tg-monitor.git
cd tg-monitor
uv venv && uv pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8080
```

---

## 📄 License

MIT License

---

<p align="center">
  <a href="https://github.com/hanxuan47/tg-monitor">GitHub</a> ·
  <a href="https://hub.docker.com/r/mrtangv/tg-monitor">Docker Hub</a>
</p>
