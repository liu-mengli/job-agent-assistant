# Job Agent Assistant — 后端

## 已安装的库

| 库 | 用途 |
|---|---|
| fastapi | Web 框架 |
| uvicorn[standard] | ASGI 服务器（含 WebSocket、watchfiles 等） |
| pydantic-settings | 配置管理（类型校验，启动即报错） |
| python-dotenv | 从 .env 文件加载环境变量 |
| sqlalchemy[asyncio] | ORM 框架（异步支持） |
| asyncpg | PostgreSQL 异步驱动 |
| bcrypt | 密码哈希（加盐 + 慢哈希） |
| PyJWT | JWT 签发与验签 |
| loguru | 结构化日志（彩色终端 + JSON 文件轮转） |

## 配置文件

| 文件 | 用途 |
|---|---|
| `.env` | 敏感配置（API Key、数据库密码、JWT 密钥等），不提交 git |
| `.env.example` | 配置模板，可提交 git |
| `requirements.txt` | 依赖清单，`pip install -r requirements.txt` 一键安装 |
| `config.py` | pydantic-settings 集中管理，读取 .env，类型校验 |

## 已完成工作

1. 创建 `.env` 环境变量文件，存放 DeepSeek API Key 等敏感配置，已写入 `.gitignore`
2. 创建 `.env.example` 模板文件，可安全提交到 git
3. 创建项目级 `.gitignore`，统一管理前后端忽略规则
4. 搭建 FastAPI 应用骨架，配置 CORS 允许前端跨域访问
5. 路由分层：`main.py` 只做应用组装，业务路由按模块拆分到 `api/` 目录
6. 健康检查接口 `GET /api/v1/health`
7. 配置升级为 `pydantic-settings`：`Settings` 类做类型校验，启动即报错，业务模块通过 `settings.XXX` 读取
8. 生成 `requirements.txt`，锁定依赖版本
9. API 响应统一格式：`ApiResponse` 模型，所有接口返回 `{ code, data, message }` 结构
10. 全局异常处理器：参数校验失败（422）和未捕获异常（500）均包装为统一格式
11. 登录接口 `POST /api/v1/auth/login`，从数据库查询用户并校验密码
12. 接入 PostgreSQL，配置 SQLAlchemy 异步引擎 + 会话工厂 + `get_db` 依赖注入
13. 创建 User 表（id / username / password），启动时自动建表
14. bcrypt 密码哈希（随机盐 + 12 轮迭代），密码不存明文
15. 启动时自动种子数据：插入默认管理员 `admin / 123456`
16. lifespan 管理数据库连接生命周期，启动初始化、关闭释放
17. JWT 认证：登录签发 Token，`get_current_user` 依赖保护接口，过期/伪造自动 401
18. WebSocket 双向通信通道：JWT 鉴权握手、统一消息协议（6 种类型）、连接管理（重复连接清理 + 发送异常保护）、心跳保活、流式回复模拟
19. 日志系统（loguru）：request_id 全链路追踪（contextualize）、HTTP/WS/异常/lifespan 全覆盖、开发彩色终端 + 生产 JSON 轮转

## 文件结构

```
backend/job-agent-assistant-backend/
├── .env                   # 敏感配置（不提交）
├── .env.example           # 配置模板（可提交）
├── .venv/                 # Python 虚拟环境
├── README.md
├── requirements.txt       # 项目依赖清单
├── config.py              # Settings 类 + settings 实例，类型校验，读取 .env
├── main.py                # 应用组装入口（lifespan、全局异常处理、路由挂载）
└── api/
    ├── __init__.py
    ├── auth.py            # 登录 + JWT 签发 / GET /auth/me 用户信息
    ├── database.py        # SQLAlchemy 引擎 + 会话工厂 + 自动建表 + 种子数据
    ├── dependencies.py    # get_current_user 认证依赖（Bearer Token 提取 + 验签）
    ├── health.py          # 健康检查路由
    ├── log.py             # 日志配置中心（loguru）
    ├── middleware.py       # RequestId 中间件（contextualize 注入）
    ├── router.py          # v1 路由汇总（含 WebSocket）
    ├── security.py        # bcrypt 密码哈希 / JWT 签发 / JWT 解析
    ├── models/
    │   ├── __init__.py    # 模型导出
    │   └── user.py        # User 表
    ├── ws/
    │   ├── __init__.py
    │   ├── protocol.py    # 消息协议（6 种消息类型）
    │   ├── manager.py     # 连接管理器（按 user_id 索引）
    │   └── chat.py        # WS 端点（JWT 验签 + 消息分发）
    └── schemas/
        ├── __init__.py
        └── response.py    # ApiResponse 统一响应格式
```
