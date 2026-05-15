# Reddit 本地订阅站

一个本地 Web 应用，封装 [reddit-universal-scraper](https://github.com/reddit-universal-scraper) 实现 Reddit 帖子的自动爬取、管理和内容筛选工作流。

## 关注我
关注微信公众号"独立开发者故事"，掌握后续动态

![独立开发者故事](static/qrcode.jpeg)

## 功能特性

- 可视化配置爬取目标（subreddit），支持多目标并行
- 按帖子类型过滤（文本/图片/视频/图集/链接）
- 工作流状态管理：`pending` → `to_sync` → `synced` / `deleted`
- 多维度排序与筛选（来源、状态、时间、热度）
- 爬取日志记录与历史查看
- UI 偏好自动持久化

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | FastAPI + Uvicorn |
| 数据库 | SQLite (WAL 模式) |
| 爬虫 | reddit-universal-scraper (子进程调用) |
| 前端 | 原生 HTML/CSS/JS (单文件，无构建步骤) |

## 快速开始

### 前置条件

- Python 3.9+
- pip

### 安装与运行

```bash
# 克隆项目
git clone <repo-url> && cd web

# 安装依赖
pip install -r requirements.txt
pip install -r reddit-universal-scraper/requirements.txt

# 启动服务
python app.py
```

浏览器访问 http://localhost:8080

## 项目结构

```
├── app.py                  # FastAPI 后端入口
├── database.py             # SQLite 数据库操作
├── scraper_runner.py       # 爬虫调度（守护线程 + 子进程）
├── static/
│   └── index.html          # 前端单页应用
├── data/
│   └── reddit_local.db     # SQLite 数据库文件
├── reddit-universal-scraper/  # 爬虫子模块
└── requirements.txt
```

## 数据流

1. 用户在 UI 配置爬取目标 → 保存至 `scrape_config` 表
2. ScraperRunner 守护线程按间隔调用爬虫子进程
3. 爬虫输出 CSV → ScraperRunner 读取并导入 `posts` 表
4. 前端通过 REST API 获取、筛选和管理帖子

## API

所有接口位于 `/api/` 路径下：

- `GET /api/posts` — 分页查询帖子（支持 status/sort/source 过滤）
- `POST /api/posts/{id}/sync` — 标记为待同步
- `POST /api/posts/{id}/delete` — 软删除
- `POST /api/posts/{id}/publish` — 标记为已发布
- `GET /api/config` — 获取爬取配置
- `POST /api/config` — 更新爬取配置
- `GET /api/scrape-logs` — 查看爬取日志

## License

MIT
