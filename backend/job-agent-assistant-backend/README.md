# Job Agent Assistant — 后端

## 已安装的库

| 库 | 用途 |
|---|---|
| fastapi | Web 框架 |
| uvicorn[standard] | ASGI 服务器（含 WebSocket、watchfiles 等） |
| pydantic-settings | 配置管理（类型校验 + model_validator 密钥空值拦截） |
| python-dotenv | 从 .env 文件加载环境变量 |
| sqlalchemy[asyncio] | ORM 框架（异步支持） |
| asyncpg | PostgreSQL 异步驱动（SQLAlchemy 使用） |
| psycopg | PostgreSQL 驱动（LangGraph checkpoint + RAG 向量表使用） |
| psycopg-pool | PostgreSQL 异步连接池（AsyncConnectionPool） |
| pgvector | pgvector Python 客户端（vector 类型适配 + 索引操作） |
| bcrypt | 密码哈希（加盐 + 慢哈希） |
| PyJWT | JWT 签发与验签 |
| loguru | 结构化日志（彩色终端 + JSON 文件轮转） |
| python-multipart | HTTP 文件上传支持 |
| langchain-openai | DeepSeek 大模型接入（OpenAI 兼容协议） |
| langchain-core | 消息类型（SystemMessage / HumanMessage / AIMessage / ToolMessage） |
| langchain-text-splitters | 文本切片（RecursiveCharacterTextSplitter） |
| langgraph | Agent 工作流框架（StateGraph + astream + tool calling） |
| langgraph-checkpoint-postgres | LangGraph 官方 PostgreSQL checkpoint 持久化（PostgresSaver + AsyncPostgresSaver） |
| langgraph-checkpoint | LangGraph checkpoint 基础抽象 |
| pymupdf | PDF 文本提取（文字型 PDF 直接读取） |
| sentence-transformers | 本地 embedding 模型加载与推理 |
| easyocr | OCR 光学字符识别（图片型 PDF 回退，检测 + 识别双模型） |
| openai | OpenAI SDK，langchain-openai 底层依赖 |
| websockets | WebSocket 协议实现，uvicorn WS 支持 + 测试脚本 |

## 配置文件

| 文件 | 用途 |
|---|---|
| `.env` | 敏感配置（API Key、数据库密码、JWT 密钥、代理等），不提交 git |
| `.env.example` | 配置模板，可提交 git |
| `requirements.txt` | 依赖清单，`pip install -r requirements.txt` 一键安装 |
| `config.py` | pydantic-settings 集中管理 + model_validator 防密钥空值 + DATABASE_URL / PG_URL |
| `run.py` | Windows 兼容启动入口（SelectorEventLoop 策略） |

## 已完成工作

### 基础设施
1. 创建 `.env` 环境变量文件，存放 DeepSeek API Key 等敏感配置，已写入 `.gitignore`
2. 创建 `.env.example` 模板文件，可安全提交到 git
3. 创建项目级 `.gitignore`，统一管理前后端忽略规则
4. 搭建 FastAPI 应用骨架，配置 CORS 允许前端跨域访问
5. 路由分层：`main.py` 只做应用组装，业务路由按模块拆分到 `api/` 目录
6. 健康检查接口 `GET /api/v1/health`
7. 配置升级为 `pydantic-settings`：`Settings` 类做类型校验 + `model_validator` 拦截空密钥
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
18. WS 端点 `/ws/chat`：ticket 临时票据握手（非 JWT），一票一用 + 10 秒 TTL
19. `POST /api/v1/ws/ticket`（认证保护）：JWT 换一次性 WS 票据
20. 统一消息协议（7 种类型）：`auth.success` / `chat.request` / `chat.stream` / `chat.done` / `chat.busy` / `ping` / `pong` / `error`
21. 连接管理器：按 (user_id, session_id) 双维度索引、同 key 踢旧连接、`send_json_to` 绑定原始 WS 防串流
22. 心跳保活：前端 30 秒发 `ping`，后端回 `pong`
23. 并发保护：按 (user_id, session_id) 隔离的 asyncio.Lock，不同会话独立

### 求职助手 Agent
24. LangGraph + DeepSeek 求职助手：StateGraph + add_messages 多轮对话、18 个 Mock 岗位
25. `POST /api/v1/chat`（HTTP 备用）：`get_graph().ainvoke()` 一次性返回
26. WS 流式对话：`graph.astream(stream_mode="messages")` 逐 token 推送
27. 流式 token 绑定：`send_json_to(stream_chunk, ws)` 防连接顶替串流
28. 代理字符清洗（`sanitize`）：防 Unicode surrogate 致 JSON 崩溃
29. 断连保护：流式循环检测失败立即 `break` 停止浪费 API token
30. 输入容错：`.get()` 防 KeyError，`chunk.content` None 保护

### 会话隔离（session_id）
31. 前端生成 UUID，WS URL query 参数传入后端
32. 连接管理器 (user_id, session_id) → connection，同用户不同会话互不踢下线
33. 并发锁 (user_id, session_id) 隔离，不同会话独立并发
34. `session_id` 注入 loguru 日志 Context：`[request_id][session_id]`

### LangGraph Checkpoint 持久化
35. AsyncPostgresSaver + AsyncConnectionPool：StateGraph 状态实时持久化到 PG
36. `init_graph()` + `get_graph()` 懒初始化：setup() autocommit 建表，运行时连接池
37. 4 张 checkpoint 表：`checkpoints` / `checkpoint_blobs` / `checkpoint_writes` / `checkpoint_migrations`
38. `get_checkpoint_state(thread_id)`：按 session_id 反序列化消息历史
39. 有 checkpoint 后 `astream()` 只传当前 HumanMessage，历史由 checkpointer 自动恢复

### 会话管理 API
40. Session ORM 模型（`sessions` 表）：user_id / session_id / title / created_at / updated_at
41. `GET /api/v1/sessions`：当前用户会话列表（updated_at 倒序）
42. `GET /api/v1/sessions/{session_id}`：从 checkpoint 反序列化消息历史

### 知识库与 RAG 检索增强
43. PDF 简历上传 → 解析 → 切片 → 向量化 → 入库完整管线
44. PyMuPDF 文字型 PDF 提取 + easyocr（craft_mlt_25k + zh_sim_g2）图片型 PDF OCR 回退
45. 三层层级语义切片：正则章节标题（30+ 关键词）→ 空行段落 → RecursiveCharacterTextSplitter 兜底
46. sentence-transformers + bge-small-zh-v1.5（512 维）本地 embedding，L2 归一化
47. pgvector `vector(512)` 原生类型存储 + `<=>` 余弦距离检索
48. `POST /api/v1/resumes/upload`：上传 → 解析 → 切片 → 向量化 → 入库（每用户限 1 份，上传新简历自动替换旧简历）
49. `GET /api/v1/resumes`：当前用户简历列表
50. `DELETE /api/v1/resumes/{id}`：删除简历及全部切片
51. `search_resume` LangGraph Tool：LLM 检测到简历相关问题 → 自动调用工具 → pgvector 检索 top-5 → 结果回传 LLM
52. Tool calling 循环：job_advisor ⇄ tools，conditional edge 路由，每轮最多 2 次工具调用防死循环
53. 工具执行时前端实时显示"（正在检索简历...）"状态

### 日志与可观测性
54. 日志系统（loguru）：request_id + session_id 全链路追踪
55. RequestIdMiddleware：每个请求/连接日志自动携带唯一 ID

## 文件结构

```
backend/job-agent-assistant-backend/
├── .env                   # 敏感配置（不提交）
├── .env.example           # 配置模板（可提交）
├── .venv/                 # Python 虚拟环境
├── README.md
├── requirements.txt       # 项目依赖清单
├── config.py              # pydantic-settings + DATABASE_URL / PG_URL / RAG 配置
├── main.py                # 应用组装入口（lifespan、CORS、异常处理、embedding 预热）
├── run.py                 # Windows 兼容启动入口（SelectorEventLoop）
└── api/
    ├── __init__.py
    ├── auth.py            # 登录 + JWT 签发
    ├── chat.py            # HTTP 聊天接口（备用）
    ├── database.py        # SQLAlchemy 引擎 + 会话 + 自动建表 + 种子数据
    ├── dependencies.py    # get_current_user 认证依赖
    ├── health.py          # 健康检查
    ├── log.py             # 日志配置中心（loguru）
    ├── middleware.py       # RequestId 中间件
    ├── router.py          # v1 路由汇总
    ├── security.py        # bcrypt / JWT 签发 / JWT 解析
    ├── sessions.py        # 会话管理（GET /sessions + GET /sessions/{id}）
    ├── resumes.py         # 简历管理（POST upload + GET list + DELETE {id}）
    ├── agent/
    │   ├── __init__.py
    │   └── graph.py       # LangGraph Agent（State + Node + Tool + conditional routing + checkpointer）
    ├── models/
    │   ├── __init__.py
    │   ├── user.py        # User 表
    │   ├── session.py     # Session 表（会话索引）
    │   └── resume.py      # ResumeDocument 表（简历元数据）
    ├── rag/
    │   ├── __init__.py
    │   ├── parser.py      # PDF 解析（PyMuPDF 文字提取 + easyocr OCR 图片回退）
    │   ├── chunker.py     # 语义切片（章节标题 → 段落 → 字符数兜底，三层）
    │   ├── embedder.py    # Embedding 模型（bge-small-zh-v1.5, 512 维, 模块级单例）
    │   ├── store.py       # pgvector 存取 + 余弦距离检索 + 建表
    │   └── tool.py        # search_resume LangGraph Tool
    ├── ws/
    │   ├── __init__.py
    │   ├── protocol.py    # 消息协议（7 种类型 + WSMessage 模型）
    │   ├── manager.py     # 连接管理器（(user_id, session_id) 双维度）
    │   ├── chat.py        # WS 端点 + HTTP 换票 + 流式处理 + 会话元数据
    │   ├── lock.py        # 用户会话级异步锁
    │   └── ticket.py      # 票据存储（10s TTL + 一票一用）
    └── schemas/
        ├── __init__.py
        └── response.py    # ApiResponse 统一格式
```
