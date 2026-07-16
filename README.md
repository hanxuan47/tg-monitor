<p align="center">
  <img src="https://img.shields.io/badge/version-v2.0-5b8def?style=flat-square" alt="version">
  <img src="https://img.shields.io/badge/python-3.13+-4cd964?style=flat-square" alt="python">
  <img src="https://img.shields.io/badge/license-MIT-a855f7?style=flat-square" alt="license">
  <img src="https://img.shields.io/docker/pulls/mrtangv/tg-monitor?style=flat-square" alt="pulls">
</p>

<h1 align="center">📊 TG Monitor</h1>
<p align="center"><strong>Telegram 群聊管理监控面板</strong></p>
<p align="center">
  🤖 Bot 监控 · 🔑 反馈检测 · 🧠 AI 回复 · 🎬 影视追新 · 🖼️ 图片日报
</p>

---

## 简介

TG Monitor 是一个全能的 Telegram 群聊管理监控系统。通过 Bot 接入群组，提供消息监控、反馈关键词检测、DeepSeek AI 智能回复、影视追新通知、自动回复、每日图片日报等能力，支持 Bark 推送和群内 Bot 通知。

---

## 🐳 部署

### 1Panel 一键部署

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

所有参数已写死，复制粘贴即用。数据持久化在 `./data` 目录。

### Docker 命令行

```bash
docker run -d --name tg-monitor -p 8080:8080 -v ./data:/app/data --restart unless-stopped mrtangv/tg-monitor:latest
```

### 手动部署

```bash
git clone https://github.com/hanxuan47/tg-monitor.git
cd tg-monitor
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8080
```

---

## 🚀 功能一览

### 🤖 Bot 智能监控

| 功能 | 说明 |
|:----|:------|
| 实时消息监控 | Bot 接入群组后自动监控所有消息，面板实时展示 |
| 反馈关键词检测 | 自定义关键词（反馈、求助、bug...），命中即触发通知 + Bot 自动回复 |
| 自动回复 | 检测到关键词时 Bot 在群内回复「已收到反馈，管理员会尽快处理」 |
| 自动删除回复 | Bot 回复后默认 30 秒自动删除，保持群聊整洁（可配置） |
| Bark 推送 | 同时通过 Bark 发送时效性通知到手机 |
| Bot 代发消息 | 面板直接选择群组、输入内容，Bot 代为发送 |
| 日报推送群聊 | 生成图片日报并通过 Bot 发送到群，替代 Bark 推送 |

### 🧠 DeepSeek AI 群聊

| 方式 | 说明 |
|:----|:------|
| @Bot 提及 | 群聊中 @Bot 用户名，自动调用 DeepSeek 回复 |
| 回复 Bot 消息 | 回复 Bot 发的任意消息，自动接话 |
| 全开模式 | 指定群组所有消息都触发 AI 回复 |
| 配置简单 | 面板填入 DeepSeek API Key 即可使用 |

### 🎬 影视追新通知

通过 TMDB API 追踪最新影视资讯，Bot 推送到群聊。

| 类型 | 说明 |
|:----|:------|
| 🔥 今日热门影视 | TMDB Trending 榜单 |
| 🎬 正在热映 | 正在上映的电影 |
| 📺 今日更新剧集 | 当天更新的 TV 剧集 |

### 📊 面板功能

| 页面 | 功能 |
|:-----|:------|
| 📊 **总览** | 6 大统计卡片 + 7 天趋势图 + 活跃群组 |
| 👥 **群组管理** | 查看 / 添加 / 移除群组 |
| 💬 **消息监控** | 实时消息流，反馈高亮标记 |
| 🔔 **反馈监控** | 关键词管理 + 反馈记录 + 自动回复设置 + 自动删除配置 |
| 📋 **日报汇总** | 文本日报 + 精美图片报告 + 定时任务 |
| 🤖 **Telegram 连接** | Bot 模式 / Telethon 模式切换 |
| ⚡ **Bark 通知** | 推送密钥配置 + 测试 |
| 🧠 **AI 助手** | DeepSeek 配置 + 消息发送 + 日报推送 + 群聊统计 + 影视追新 |

### 🎨 界面特性

- **深色/浅色双主题** — 侧栏一键切换，自动保存偏好
- **毛玻璃设计** — 卡片半透明 + backdrop-filter 质感
- **极简滚动条** — 细边框，跟随文字颜色
- **响应式布局** — 桌面 / 平板 / 手机自适应

### ⚡ 性能优化

| 优化 | 说明 |
|:----|:------|
| GZip 压缩 | HTML 压缩至 15KB，传输快 4 倍 |
| DB 连接池 | 单例连接复用 + 内存缓存配置 |
| DB 索引 | messages 表 3 个索引，查询提升 10-100 倍 |
| 配置缓存 | 5 秒内存缓存，频繁读取不查库 |
| 批量读配置 | 一次查询 6 个值，减少 5 次 DB 查询 |

---

## 🚀 快速上手

```
1. @BotFather 创建 Bot → 获取 Token
2. 面板 → Telegram 连接 → Bot 模式 → 填入 Token → 启动
3. 将 Bot 添加到群组并设为管理员
4. 面板 → 反馈监控 → 配置关键词和自动回复
5. （可选）Bark 密钥 → 手机接收推送
6. （可选）AI 助手 → 填入 DeepSeek Key → 开启 AI 聊天
7. （可选）AI 助手 → TMDB Key → 影视追新通知
```

---

## 🏗️ 项目结构

```
tg-monitor/
├── main.py              # FastAPI 后端 + API 路由
├── database.py          # SQLite 异步数据库层（带索引 + 缓存）
├── bot_monitor.py       # Telegram Bot 监控（消息处理 + AI 回复 + 自动删除）
├── telegram_monitor.py  # Telethon 监控（备选方案）
├── bark_notify.py       # Bark iOS 推送
├── report_image.py      # 图片日报生成（Pillow）
├── ai_chat.py           # DeepSeek AI 集成
├── media_tracker.py     # TMDB 影视追新
├── templates/
│   ├── dashboard.html   # 暗色/浅色双主题面板
│   └── login.html       # 登录页面
├── Dockerfile           # 镜像构建
├── docker-compose.yml   # 1Panel 编排
└── requirements.txt
```

### 技术栈

| 层 | 技术 |
|:---|:------|
| 后端 | Python 3.13+, FastAPI, Uvicorn, GZip |
| 数据库 | SQLite (aiosqlite), 连接池 + 索引 + 缓存 |
| Telegram | python-telegram-bot / Telethon |
| AI | DeepSeek API (OpenAI 兼容) |
| 影视 | TMDB API (themoviedb.org) |
| 图片 | Pillow, wqy-zenhei 中文字体 |
| 前端 | Chart.js + Font Awesome, 双主题, 毛玻璃 |
| 推送 | Bark API (iOS) |
| 部署 | Docker, GitHub Actions 自动构建 |

---

## 📖 API 接口

### 监控管理

| 方法 | 路径 | 说明 |
|:----:|------|:----:|
| POST | `/api/monitor/bot/start` | 启动 Bot |
| POST | `/api/monitor/bot/stop` | 停止 Bot |
| GET | `/api/monitor/bot/info` | Bot 信息 |
| POST | `/api/monitor/bot/send` | Bot 发送消息到群 |
| POST | `/api/monitor/bot/send-report` | 推送日报图片到群 |
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

### AI & 影视

| 方法 | 路径 | 说明 |
|:----:|------|:----:|
| GET | `/api/auto-reply` | 获取自动回复内容 |
| POST | `/api/auto-reply` | 设置自动回复内容 |
| POST | `/api/media/check` | 查询并推送影视资讯 |
| GET | `/api/media/preview` | 预览影视资讯 |

### Bark & 配置

| 方法 | 路径 | 说明 |
|:----:|------|:----:|
| POST | `/api/bark/test` | 测试推送 |
| POST | `/api/bark/send` | 自定义推送 |
| POST | `/api/set-password` | 设置面板密码 |
| POST | `/api/login` | 登录验证 |
| GET | `/api/config` | 获取配置 |
| POST | `/api/config` | 更新配置 |

---

## 📄 License

MIT License

---

<p align="center">
  <a href="https://github.com/hanxuan47/tg-monitor">GitHub</a>
  ·
  <a href="https://hub.docker.com/r/mrtangv/tg-monitor">Docker Hub</a>
</p>
