<p align="center">
  <img src="https://img.shields.io/badge/TG%20Monitor-v2.0-5b8def?style=flat-square" alt="version">
  <img src="https://img.shields.io/badge/Python-3.13+-4cd964?style=flat-square" alt="python">
  <img src="https://img.shields.io/badge/FastAPI-0.139+-ff9500?style=flat-square" alt="fastapi">
  <img src="https://img.shields.io/badge/license-MIT-a855f7?style=flat-square" alt="license">
</p>

<h1 align="center">📊 TG Monitor</h1>
<p align="center"><strong>Telegram 群聊管理监控面板</strong></p>
<p align="center">
  监控群聊 · 汇总报告 · 反馈检测 · Bark 即时推送 · 精美图片日报
</p>

---

## 概述

**TG Monitor** 是一个开源的 Telegram 群聊管理监控系统。通过 Telegram Bot 接入群组，实时监控消息、检测反馈关键词、生成每日汇总报告，并通过 Bark 推送到你的手机。

### ✨ 功能特性

| 功能 | 说明 |
|------|------|
| 🤖 **Bot 模式** | 通过 @BotFather 创建 Bot 即可接入，无需手机号，安全稳定 |
| 📱 **Telethon 模式** | 也支持个人账号连接的备选方案 |
| 💬 **实时消息监控** | 监控所有已接入群组的消息流，面板实时查看 |
| 🔑 **反馈关键词检测** | 自定义关键词（如"反馈、求助、bug"），命中即自动通知 |
| ⚡ **Bark 推送** | 检测到反馈时通过 Bark 发送时效性通知到 iOS 设备 |
| 📊 **数据看板** | 6 大统计卡片 + 7 天趋势图 + 消息流 |
| 🖼️ **图片日报** | 每日 22:00 自动生成精美图片版群聊汇总报告 |
| 📋 **日报汇总** | 自动统计每日消息数、活跃用户、反馈数 |
| 🐳 **Docker 部署** | 一键 docker-compose 启动 |

---

## 快速开始

### 方式一：Docker Compose（推荐）

```bash
# 1. 克隆项目
git clone https://github.com/hanxuan47/tg-monitor.git
cd tg-monitor

# 2. 启动
docker compose up -d

# 3. 访问
open http://localhost:8080
```

### 方式二：手动部署

```bash
# 1. 克隆项目
git clone https://github.com/hanxuan47/tg-monitor.git
cd tg-monitor

# 2. 安装依赖（推荐使用 uv）
uv venv
uv pip install -r requirements.txt

# 3. 启动
uvicorn main:app --host 0.0.0.0 --port 8080

# 4. 访问
open http://localhost:8080
```

---

## 使用指南

### 第一步：创建 Telegram Bot

1. 在 Telegram 中打开 [@BotFather](https://t.me/BotFather)
2. 发送 `/newbot`，按提示创建 Bot
3. 记下 BotFather 给你的 **HTTP Token**（格式: `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`）
4. 在 @BotFather 中运行 `/setprivacy` → 选择你的 Bot → **Disable**（关闭隐私模式）

### 第二步：配置 Bark 通知（可选）

1. 在 App Store 下载 [Bark](https://bark.day.app)
2. 打开 Bark App，复制你的推送密钥
3. 在面板 → **Bark 通知** 页填入密钥 → 保存 → 测试

### 第三步：启动监控

1. 打开面板 → **Telegram 连接**
2. 切换到 **🤖 Bot 模式**（推荐）
3. 填入 Bot Token → 点击「启动」
4. 将 Bot **添加到群组**并设为管理员（至少需要消息读取权限）

### 第四步：配置反馈关键词

1. 面板 → **反馈监控**
2. 添加关键词：`反馈`、`求助`、`bug`、`错误`、`问题`（已预设）
3. 当群聊中出现包含关键词的消息 → 自动 Bark 推送

### 第五步：查看日报

1. 面板 → **日报汇总**
2. 点击「生成图片」生成精美 PNG 报告
3. 设置定时任务：每天 22:00 自动生成

---

## 面板页面

| 页面 | 功能 |
|------|------|
| 📊 **总览** | 6 个统计卡片 + 7 天消息趋势图 + 活跃群组列表 |
| 👥 **群组管理** | 查看/添加/移除群组 |
| 💬 **消息监控** | 实时消息流，反馈消息高亮标记 |
| 🔔 **反馈监控** | 关键词管理 + 反馈消息记录 |
| 📋 **日报汇总** | 文本日报 + 图片报告 + 定时任务设置 |
| 🤖 **Telegram 连接** | Bot 模式 / Telethon 模式切换 |
| ⚡ **Bark 通知** | 推送密钥配置 + 测试 |

![Dashboard Preview](https://img.shields.io/badge/UI-Dark%20Theme-1a1d2e?style=flat-square)

---

## 系统架构

```
tg-monitor/
├── main.py              # FastAPI 后端 (API + Web 路由)
├── database.py          # SQLite 异步数据库层
├── bot_monitor.py       # Telegram Bot 监控模块（Bot API）
├── telegram_monitor.py  # Telethon 监控模块（用户账号）
├── bark_notify.py       # Bark iOS 推送通知模块
├── report_image.py      # 日报图片生成器 (Pillow)
├── templates/
│   └── dashboard.html   # 暗色主题 Web 面板
├── Dockerfile           # Docker 构建文件
├── docker-compose.yml   # Docker Compose 配置
└── requirements.txt     # Python 依赖
```

### 技术栈

- **Backend:** Python 3.13+, FastAPI, Uvicorn
- **Database:** SQLite (aiosqlite)
- **Telegram:** python-telegram-bot (Bot API) / Telethon (MTProto)
- **Images:** Pillow (PIL), wqy-zenhei CJK font
- **Frontend:** Single-page HTML + Chart.js + Font Awesome
- **Notifications:** Bark API (iOS push)
- **Deploy:** Docker, docker-compose

---

## API 接口

### 监控管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/monitor/bot/start` | 启动 Bot 监控 |
| `POST` | `/api/monitor/bot/stop` | 停止 Bot |
| `GET` | `/api/monitor/bot/info` | Bot 信息 |
| `POST` | `/api/monitor/telethon/start` | 启动 Telethon |
| `POST` | `/api/monitor/telethon/stop` | 停止 Telethon |
| `GET` | `/api/monitor/status` | 监控状态 |
| `POST` | `/api/monitor/stop` | 停止所有监控 |

### 群组 & 消息

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/groups` | 群组列表 |
| `POST` | `/api/groups/add` | 添加群组 |
| `POST` | `/api/groups/remove` | 移除群组 |
| `GET` | `/api/messages` | 消息列表 |
| `GET` | `/api/stats` | 统计数据 + 时间线 |

### 关键词 & 报告

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/keywords` | 关键词列表 |
| `POST` | `/api/keywords/add` | 添加关键词 |
| `POST` | `/api/keywords/remove` | 移除关键词 |
| `GET` | `/api/reports` | 日报列表 |
| `POST` | `/api/reports/generate` | 生成日报 |
| `POST` | `/api/reports/generate-image` | 生成图片日报 |
| `GET` | `/api/reports/images` | 图片列表 |
| `POST` | `/api/reports/daily-cron` | cron 设置指引 |

### Bark & 配置

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/bark/test` | 测试 Bark 通知 |
| `POST` | `/api/bark/send` | 发送自定义通知 |
| `GET` | `/api/config` | 获取配置 |
| `POST` | `/api/config` | 更新配置 |

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `TZ` | `Asia/Shanghai` | 时区设置 |

所有配置通过 Web 面板保存到 SQLite 数据库，无需环境变量文件。

---

## 设置每日定时日报

```bash
# 在 Hermes 或 cron 中执行：
cronjob action=create schedule='0 22 * * *' name='tg-daily-report' \
  prompt='运行 TG Monitor 每日群聊日报汇总。为所有活跃群组生成报告图片，如有 Bark 配置则发送推送通知。最后输出汇总文本。' \
  skills='[]' deliver='origin'
```

或在面板 → **日报汇总** → **定时任务** 中获取设置指引。

---

## 开发

```bash
# 克隆
git clone https://github.com/hanxuan47/tg-monitor.git
cd tg-monitor

# 安装
uv venv
uv pip install -r requirements.txt

# 开发模式（热重载）
uvicorn main:app --reload --host 0.0.0.0 --port 8080
```

## 许可证

[MIT License](LICENSE)

---

<p align="center">
  由 <a href="https://hermes-agent.nousresearch.com">Hermes Agent</a> 构建
</p>
