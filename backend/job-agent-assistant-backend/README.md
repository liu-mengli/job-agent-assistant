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
| `config.py` | pydantic-settings 集中管理 + model_validator 防密钥空值 + DATABASE_URL / PG_URL / RAG 配置（含 RETRIEVAL_THRESHOLD） |
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

### 求职助手 Agent — 基础架构
24. LangGraph + DeepSeek 求职助手：StateGraph + add_messages 多轮对话 + 真实岗位数据库
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
43. `DELETE /api/v1/sessions/{session_id}`：永久删除会话（sessions 记录 + checkpoint 3 张表按 thread_id 清除）

### 知识库与 RAG 检索增强
44. PDF 简历上传 → 解析 → 切片 → 向量化 → 入库完整管线
45. PyMuPDF 文字型 PDF 提取 + easyocr（craft_mlt_25k + zh_sim_g2）图片型 PDF OCR 回退
46. 三层层级语义切片：正则章节标题（30+ 关键词）→ 空行段落 → RecursiveCharacterTextSplitter 兜底
47. sentence-transformers + bge-small-zh-v1.5（512 维）本地 embedding，L2 归一化
48. pgvector `vector(512)` 原生类型存储 + `<=>` 余弦距离检索
49. `POST /api/v1/resumes/upload`：上传 → 存文件立即返回，后台异步解析 → 切片 → 向量化 → 入库（每用户限 1 份，上传新简历自动替换旧简历）
50. `GET /api/v1/resumes`：当前用户简历列表（含 status / error_message 字段）
51. `DELETE /api/v1/resumes/{id}`：删除简历及全部切片
52. `search_resume` LangGraph Tool：LLM 检测到简历相关问题 → 自动调用工具 → pgvector 检索 top-5（含阈值过滤）→ 结果回传 LLM
53. `search_jobs` LangGraph Tool：LLM 检测到岗位查询 → 自动调用 → pgvector 语义检索 `job_listings` 表 → 结构化岗位返回 LLM
54. Tool calling 循环：job_advisor ⇄ tools，conditional edge 路由，每轮最多 2 次工具调用防死循环
55. 工具执行时前端实时显示"（正在检索...）"状态

### 性能与稳定性
56. 阻塞操作卸载：`parse_pdf`（EasyOCR）和 `embed`（sentence-transformers）通过 `loop.run_in_executor` 卸载到线程池，防止阻塞事件循环
57. embedding 模型离线加载：`HF_HUB_OFFLINE=1` 禁止 HuggingFace 联网校验，解决国内网络超时问题
58. OCR 耗时简历上传异步化：HTTP 立即返回 `status: processing`，`asyncio.create_task` 后台处理，前端轮询状态
59. Checkpoint 脏数据清洗：检测 orphan tool_call（缺少 ToolMessage），自动清除防止 DeepSeek 400 错误

### Agent 行为优化
60. 双模式自动路由：根据用户措辞自动判断「浏览模式」（轻量，只看岗位）vs「全流程推荐」（简历+岗位+匹配度+下一步追问）
61. 全流程推荐工作流：同时调用 search_resume + search_jobs → 岗位表格含匹配度 → 综合评估优劣势 → 询问下一步（优化简历/准备面试/详细匹配分析）
62. 简历优化建议：用户要求时，基于简历原文和岗位 JD 给出 5 维度建议（突出经历/补充关键词/弱描述/不建议内容/优化示例），严禁虚构经历
63. 打招呼语与自我介绍：基于简历生成 2 版招呼语 + 1 分钟自我介绍 + 3 条个人优势话术
64. 新用户引导：无简历/偏好时浏览模式正常服务，末尾温和引导上传，不阻塞不重复
65. 无简历降级处理：全流程推荐无简历时跳过匹配度，按偏好排序，引导上传
66. System Prompt 约束：双工具同时调用、禁止循环搜索、接受检索结果如实告知
67. 简历失效通知：上传新简历后自动向用户所有 session checkpoint 注入 AIMessage 失效提示，防止 LLM 依赖旧简历
68. 阈值过滤检索：`RETRIEVAL_THRESHOLD=0.55` 过滤低相似度简历片段，无结果时明确告知而非强行匹配

### 用户偏好
69. `user_preferences` 表：每用户一行，存储城市/工作模式/薪资/行业/公司规模/技术方向/排除条件/经验年限/求职状态
70. `GET /api/v1/preferences`：获取当前用户偏好
71. `PUT /api/v1/preferences`：创建或更新偏好（不存在则 Insert）
72. Agent 自动注入偏好：每次对话将用户偏好格式化追加到 System Prompt，指导 LLM 按偏好过滤和排序岗位

### 日志与可观测性
73. 日志系统（loguru）：request_id + session_id 全链路追踪
74. RequestIdMiddleware：每个请求/连接日志自动携带唯一 ID

### 结构化输出
75. `StructuredResponse` Pydantic 模型（`api/agent/schemas.py`）：7 种响应类型（greeting / browse / full_recommendation / match_analysis / resume_optimization / resume_analysis / general），全可选字段 + `extra="ignore"` 兼容 DeepSeek json_mode
76. `format_response_node`：tool-calling 循环结束后，独立 `structured_llm`（`with_structured_output(method="json_mode")`）将 Markdown 回复提取为结构化 JSON
77. `chat.structured` WS 消息类型：结构化 JSON 在 `chat.done` 之前推送到前端，旧前端忽略该类型向后兼容
78. 静默回退：`format_response_node` 失败或 Pydantic 校验失败 → `structured_content = None`，纯文本照常展示

## 文件结构

```
backend/job-agent-assistant-backend/
├── .env                   # 敏感配置（不提交）
├── .env.example           # 配置模板（可提交）
├── .venv/                 # Python 虚拟环境
├── README.md
├── requirements.txt       # 项目依赖清单
├── config.py              # pydantic-settings + DATABASE_URL / PG_URL / RAG 配置（含 RETRIEVAL_THRESHOLD）
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
    ├── router.py          # v1 路由汇总（含 preferences_router）
    ├── security.py        # bcrypt / JWT 签发 / JWT 解析
    ├── sessions.py        # 会话管理（GET list + GET messages + DELETE）
    ├── resumes.py         # 简历管理（POST upload 异步 + GET list + DELETE）+ 后台处理
    ├── preferences.py     # 用户偏好（GET + PUT）
    ├── agent/
    │   ├── __init__.py
    │   ├── graph.py       # LangGraph Agent（双 Tool + checkpointer + 偏好注入 + 结构化输出）
    │   └── schemas.py     # StructuredResponse Pydantic 模型（7 种响应类型）
    ├── models/
    │   ├── __init__.py
    │   ├── user.py        # User 表
    │   ├── session.py     # Session 表（会话索引）
    │   ├── resume.py      # ResumeDocument 表（简历元数据 + status + error_message）
    │   └── preference.py  # UserPreference 表（求职偏好）
    ├── rag/
    │   ├── __init__.py
    │   ├── parser.py      # PDF 解析（PyMuPDF 文字提取 + easyocr OCR 图片回退）
    │   ├── chunker.py     # 语义切片（章节标题 → 段落 → 字符数兜底，三层）
    │   ├── embedder.py    # Embedding 模型（bge-small-zh-v1.5, 512 维, 离线加载）
    │   ├── store.py       # pgvector 存取 + 阈值过滤检索 + 岗位检索 + 建表
    │   └── tool.py        # LangGraph Tool 定义（已废弃，实际在 graph.py）
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
