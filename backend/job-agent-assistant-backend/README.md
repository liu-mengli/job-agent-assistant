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
| langchain-openai | DeepSeek 大模型接入（OpenAI 兼容协议） |
| langchain-core | LangChain 核心消息类型（SystemMessage / HumanMessage / AIMessage / AIMessageChunk） |
| langgraph | Agent 工作流框架（StateGraph + astream 流式） |
| langgraph-checkpoint | 对话检查点抽象（langgraph-checkpoint-postgres 依赖） |
| langgraph-checkpoint-postgres | 对话历史持久化到 PostgreSQL（待接入） |
| openai | OpenAI SDK，langchain-openai 底层依赖 |
| websockets | WebSocket 协议实现，uvicorn WS 支持 + 测试脚本 |

## 配置文件

| 文件 | 用途 |
|---|---|
| `.env` | 敏感配置（API Key、数据库密码、JWT 密钥等），不提交 git |
| `.env.example` | 配置模板，可提交 git |
| `requirements.txt` | 依赖清单，`pip install -r requirements.txt` 一键安装 |
| `config.py` | pydantic-settings 集中管理，读取 .env，类型校验 |

## 已完成工作

### 基础设施
1. 创建 `.env` 环境变量文件，存放 DeepSeek API Key 等敏感配置，已写入 `.gitignore`
2. 创建 `.env.example` 模板文件，可安全提交到 git
3. 创建项目级 `.gitignore`，统一管理前后端忽略规则
4. 搭建 FastAPI 应用骨架，配置 CORS 允许前端跨域访问
5. 路由分层：`main.py` 只做应用组装，业务路由按模块拆分到 `api/` 目录
6. 健康检查接口 `GET /api/v1/health`
7. 配置升级为 `pydantic-settings`：`Settings` 类做类型校验，启动即报错
8. 生成 `requirements.txt`，锁定依赖版本

### 认证与数据库
9. API 响应统一格式：`ApiResponse` 模型，`{ code, data, message }` 结构
10. 全局异常处理器：422 和 500 均包装为统一格式
11. 登录接口 `POST /api/v1/auth/login`，数据库查询 + bcrypt 校验
12. 接入 PostgreSQL，SQLAlchemy 异步引擎 + 会话工厂 + `get_db` 依赖注入
13. 创建 User 表（id / username / password），启动时自动建表
14. bcrypt 密码哈希（随机盐 + 12 轮迭代），密码不存明文
15. 启动时自动种子数据：`admin / 123456`
16. lifespan 管理数据库连接生命周期
17. JWT 认证：登录签发 Token，`get_current_user` 依赖保护接口

### WebSocket 通信层
18. WS 端点 `/ws/chat`：Token 通过 URL 参数握手验签，JWT 无效返回 4003
19. 统一消息协议（6 种类型）：`auth.success` / `chat.request` / `chat.stream` / `chat.done` / `ping` / `pong` / `error`
20. 连接管理器（`ConnectionManager`）：按 user_id 索引、重复连接清理旧连接、send_json 返回 bool
21. 心跳保活：前端 30 秒发 `ping`，后端回 `pong`

### 求职助手 Agent
22. LangGraph + DeepSeek 求职助手：StateGraph + add_messages 多轮对话、18 个 Mock 岗位（5 城市）、回答规则约束
23. `POST /api/v1/chat`（HTTP）：`graph.ainvoke()` 一次性返回，Pydantic ChatRequest 严格校验
24. WS 流式对话：`graph.astream(stream_mode="messages")` 逐 token 推送，LLM 边生成边发送
25. 代理字符清洗（`sanitize`）：防止 Unicode surrogate 导致 JSON 序列化崩溃
26. 断连保护：`send_json` 返回 bool，流式循环检测失败立即 `break` 停止浪费 API token
27. 输入容错：消息字段 `.get()` 防 KeyError，`chunk.content` None 保护

### 日志与可观测性
28. 日志系统（loguru）：request_id 全链路追踪、HTTP/WS/异常/lifespan 全覆盖
29. RequestIdMiddleware：`contextualize` 让每个请求/连接的所有日志自动携带唯一 ID

## 文件结构

```
backend/job-agent-assistant-backend/
├── .env                   # 敏感配置（不提交）
├── .env.example           # 配置模板（可提交）
├── .venv/                 # Python 虚拟环境
├── README.md
├── requirements.txt       # 项目依赖清单
├── config.py              # pydantic-settings 集中管理
├── main.py                # 应用组装入口（lifespan、异常处理、路由挂载）
└── api/
    ├── __init__.py
    ├── auth.py            # 登录 + JWT 签发 / GET /auth/me
    ├── chat.py            # HTTP 聊天接口（POST /chat，调用 graph.ainvoke，认证 + 日志）
    ├── database.py        # SQLAlchemy 引擎 + 会话 + 自动建表 + 种子数据
    ├── dependencies.py    # get_current_user 认证依赖
    ├── health.py          # 健康检查
    ├── log.py             # 日志配置中心（loguru）
    ├── middleware.py       # RequestId 中间件（contextualize）
    ├── router.py          # v1 路由汇总
    ├── security.py        # bcrypt / JWT 签发 / JWT 解析
    ├── agent/
    │   ├── __init__.py
    │   └── graph.py       # LangGraph 求职助手（State + Node + astream 循环 + Graph 编译）
    ├── models/
    │   ├── __init__.py
    │   └── user.py        # User 表
    ├── ws/
    │   ├── __init__.py
    │   ├── protocol.py    # 消息协议（6 种消息类型 + WSMessage 模型）
    │   ├── manager.py     # 连接管理器（按 user_id 索引、断连保护）
    │   └── chat.py        # WS 端点（/ws/chat，JWT 握手 + 流式 chat.request 处理）
    └── schemas/
        ├── __init__.py
        └── response.py    # ApiResponse 统一格式
```
