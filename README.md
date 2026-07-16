<p align="center">
  <img src="https://img.shields.io/badge/version-v2.0-5b8def?style=flat-square" alt="version">
  <img src="https://img.shields.io/badge/python-3.13+-4cd964?style=flat-square" alt="python">
  <img src="https://img.shields.io/badge/license-MIT-a855f7?style=flat-square" alt="license">
  <img src="https://img.shields.io/docker/pulls/mrtangv/tg-monitor?style=flat-square" alt="pulls">
</p>

<h1 align="center">📊 TG Monitor</h1>
<p align="center"><strong>Telegram 群聊管理监控面板</strong></p>
<p align="center">
  🤖 Bot 接入 · 📊 实时看板 · 🔑 反馈检测 · ⚡ Bark 推送 · 🖼️ 图片日报
</p>

## 简介

TG Monitor 是一个开源的 Telegram 群聊管理监控系统。通过 Telegram Bot 接入群组，提供实时消息监控、反馈关键词检测、每日汇总报告，并支持 Bark 推送通知到手机。

---

## 🐳 Docker Compose 部署

### 方式一：1Panel 应用商店

编排内容直接复制粘贴，无需任何修改：

```yaml
networks:
    1panel-network:
        external: true

services:
    tg-monitor:
        container_name: tg-monitor
        image: mrtangv/tg-monitor:latest
        deploy:
            resources:
                limits:
                    cpus: "1"
                    memory: 512M
        environment:
            - TZ=Asia/Shanghai
        labels:
            createdBy: Apps
        networks:
            - 1panel-network
        ports:
            - "0.0.0.0:8080:8080"
        restart: always
        user: "0:0"
        volumes:
            - ./data:/app/data
```

所有值都已写死，无需 `.env` 配置文件。数据持久化在 `./data` 目录。

---

### 方式二：标准 Docker 命令

```bash
docker run -d \
  --name tg-monitor \
  -p 8080:8080 \
  -v ./data:/app/data \
  --restart unless-stopped \
  mrtangv/tg-monitor:latest
```

---

## 📦 手动部署

```bash
git clone https://github.com/hanxuan47/tg-monitor.git
cd tg-monitor

# 安装依赖
pip install -r requirements.txt

# 启动
uvicorn main:app --host 0.0.0.0 --port 8080
```

---

## 🚀 使用步骤

### 1. 创建 Telegram Bot

| 步骤 | 操作 |
|:----:|------|
| ① | 打开 [@BotFather](https://t.me/BotFather)，发送 `/newbot` |
| ② | 记下给你的 **HTTP Token**（格式: `123456:ABC-DEF...`） |
| ③ | 发送 `/setprivacy` → 选择你的 Bot → **Disable** |
| ④ | 将 Bot **添加到群组**并设为管理员 |

### 2. 启动监控

打开 http://localhost:8080 → **Telegram 连接** → 🤖 Bot 模式 → 填入 Token → 启动

### 3. 配置反馈关键词

**反馈监控** → 添加关键词（如：反馈、求助、bug、错误、问题）

### 4. 配置 Bark 推送（可选）

App Store 下载 [Bark](https://bark.day.app) → 复制密钥 → 面板 → **Bark 通知** → 保存

### 5. 查看日报

**日报汇总** → 生成图片 → 每日群聊报告一目了然

---

## 📊 面板页面

| 页面 | 功能 |
|------|------|
| 📊 **总览** | 统计卡片 + 7 天趋势图 + 活跃群组 |
| 👥 **群组管理** | 查看 / 添加 / 移除群组 |
| 💬 **消息监控** | 实时消息流，反馈高亮 |
| 🔔 **反馈监控** | 关键词管理 + 反馈记录 |
| 📋 **日报汇总** | 文本 + 图片报告，支持定时任务 |
| 🤖 **Telegram 连接** | Bot 模式 / Telethon 模式切换 |
| ⚡ **Bark 通知** | 推送配置 + 测试 |

---

## 🏗️ 项目结构

```
tg-monitor/
├── main.py              # FastAPI 后端
├── database.py          # SQLite 数据库
├── bot_monitor.py       # Telegram Bot 监控
├── telegram_monitor.py  # Telethon 监控（备选）
├── bark_notify.py       # Bark 推送
├── report_image.py      # 图片日报生成
├── templates/
│   └── dashboard.html   # 暗色主题面板
├── Dockerfile           # 镜像构建
├── docker-compose.yml   # 1Panel 编排
└── requirements.txt
```

### 技术栈

| 层 | 技术 |
|:---|:------|
| 后端 | Python 3.13+, FastAPI, Uvicorn |
| 数据库 | SQLite (aiosqlite) |
| Telegram | python-telegram-bot / Telethon |
| 图片 | Pillow, wqy-zenhei 字体 |
| 前端 | Chart.js + Font Awesome |
| 推送 | Bark API (iOS) |
| 部署 | Docker, GitHub Actions 自动构建 |

---

## 📖 API 接口

### 监控管理

| 方法 | 路径 | 说明 |
|:----:|------|:----:|
| POST | `/api/monitor/bot/start` | 启动 Bot 监控 |
| POST | `/api/monitor/bot/stop` | 停止 Bot |
| GET | `/api/monitor/bot/info` | 查看 Bot 信息 |
| GET | `/api/monitor/status` | 监控状态 |

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

<p align="center">
  <a href="https://github.com/hanxuan47/tg-monitor">GitHub</a>
  ·
  <a href="https://hub.docker.com/r/mrtangv/tg-monitor">Docker Hub</a>
  ·
  MIT License
</p>
