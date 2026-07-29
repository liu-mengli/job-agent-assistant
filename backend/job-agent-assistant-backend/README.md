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
| langgraph-checkpoint-postgres | LangGraph 官方 PostgreSQL checkpoint 持久化 |
| langgraph-checkpoint | LangGraph checkpoint 基础抽象 |
| pymupdf | PDF 文本提取（文字型 PDF 直接读取） |
| sentence-transformers | 本地 embedding 模型加载与推理 + Cross-Encoder 精排（bge-small / bge-m3 / bge-reranker-v2-m3） |
| easyocr | OCR 光学字符识别（图片型 PDF 回退，检测 + 识别双模型） |
| openai | OpenAI SDK，langchain-openai 底层依赖 |
| websockets | WebSocket 协议实现，uvicorn WS 支持 + 测试脚本 |
| python-docx | .docx 文档解析（知识库 SOP 文档提取） |
| jieba | 中文分词（知识库 BM25 检索，`cut_for_search` 召回优先模式） |
| opencc-python-reimplemented | 繁简中文转换（知识库 BM25 索引/查询前统一转简体，消除简繁不匹配） |

## 外部模型

| 模型 | 大小 | 路径 | 用途 |
|------|------|------|------|
| bge-small-zh-v1.5 | ~100 MB | `E:\Code Tools\huggingface\`（本地）/ `/app/models/huggingface`（Docker） | 简历 RAG embedding（512维） |
| bge-m3 | ~2.2 GB | `E:\Code Tools\huggingface\`（本地）/ `/app/models/huggingface`（Docker） | 知识库 RAG embedding（1024维） |
| bge-reranker-v2-m3 | ~2.2 GB | `E:\Code Tools\huggingface\`（本地）/ `/app/models/huggingface`（Docker） | 知识库 RAG Cross-Encoder 精排 |
| easyocr (craft_mlt_25k + zh_sim_g2) | ~100 MB | `~/.EasyOCR/model/` | PDF OCR 文字检测+中文识别 |
| DeepSeek LLM | — | 远程 API | 四个 Agent 共用推理 |

## 外部工具

| 工具 | 路径 | 用途 |
|------|------|------|
| LibreOffice | `E:\Code Tools\LibreOffice\program\soffice.exe`（Windows）/ `/usr/bin/soffice`（Docker） | `.doc → .docx 转换` |
| Docker Desktop | — | 容器化部署（可选，本地开发不需要） |

## 配置文件

| 文件 | 用途 |
|---|---|
| `.env` | 敏感配置（API Key、数据库密码、JWT 密钥、Windows 路径），不提交 git |
| `.env.example` | 配置模板，可提交 git |
| `requirements.txt` | 依赖清单（51 个包），`pip install -r requirements.txt` 一键安装 |
| `config.py` | pydantic-settings 集中管理 + model_validator 防密钥空值 + DATABASE_URL / PG_URL（含 connect_timeout）/ HF_HOME / CORS_ORIGINS / RAG 配置 / KB 配置（含 Reranker 模型/候选数/BM25/阈值）/ LibreOffice 路径 |
| `run.py` | Windows 兼容启动入口（SelectorEventLoop 策略） |
| `Dockerfile` | Docker 镜像构建定义（python:3.12-slim + LibreOffice + 中文字体 + libpq-dev + 默认阿里云镜像源） |
| `.dockerignore` | Docker 构建时排除的文件（.env / .venv / logs / uploads 等） |
| `docker-entrypoint.sh` | Docker 启动脚本（自动检测/下载模型 → 启动 uvicorn） |

### config.py 关键配置项

| 配置项 | 默认值 | 用途 |
|--------|:-----:|------|
| `DEEPSEEK_API_KEY` | — | DeepSeek API 密钥（必填） |
| `DEEPSEEK_BASE_URL` | — | DeepSeek API 地址 |
| `DEEPSEEK_MODEL` | — | DeepSeek 模型名 |
| `DB_HOST` | `localhost` | 数据库主机（Docker 中为 `postgres`） |
| `DB_PORT` | `5432` | 数据库端口 |
| `DB_NAME` | `job_agent` | 数据库名 |
| `DB_USER` | `postgres` | 数据库用户 |
| `DB_PASSWORD` | `""` | 数据库密码 |
| `JWT_SECRET_KEY` | `""` | JWT 签名密钥（必填，启动时校验） |
| `JWT_ALGORITHM` | `HS256` | JWT 签名算法 |
| `JWT_EXPIRE_MINUTES` | `1440` | Token 有效期（24 小时） |
| `CORS_ORIGINS` | `http://localhost:5173` | 前端来源（逗号分隔） |
| `HF_HOME` | `/app/models/huggingface` | HuggingFace 模型缓存目录 |
| `HF_ENDPOINT` | `""` | HF 镜像端点（国内用 `https://hf-mirror.com`） |
| `EMBEDDING_MODEL` | `BAAI/bge-small-zh-v1.5` | 简历 RAG embedding 模型 |
| `EMBEDDING_DEVICE` | `cpu` | 简历 embedding 推理设备 |
| `UPLOAD_DIR` | `uploads/resumes` | 简历上传目录 |
| `CHUNK_SIZE` | `500` | 简历切片字符数 |
| `CHUNK_OVERLAP` | `50` | 简历切片重叠 |
| `RETRIEVAL_TOP_K` | `5` | 简历 Dense 检索返回条数 |
| `RETRIEVAL_THRESHOLD` | `0.55` | 简历余弦距离上限 |
| `KB_EMBEDDING_MODEL` | `BAAI/bge-m3` | Dense 检索 embedding 模型 |
| `KB_EMBEDDING_DEVICE` | `cpu` | 知识库 embedding 推理设备 |
| `KB_RERANKER_MODEL` | `BAAI/bge-reranker-v2-m3` | Cross-Encoder 精排模型 |
| `KB_UPLOAD_DIR` | `uploads/knowledge` | 知识库文档上传目录 |
| `KB_CHUNK_SIZE` | `800` | 知识库切片字符数 |
| `KB_CHUNK_OVERLAP` | `80` | 知识库切片重叠 |
| `KB_RETRIEVAL_TOP_K` | `5` | Dense 检索返回条数 |
| `KB_RETRIEVAL_THRESHOLD` | `0.55` | Dense 余弦距离上限 |
| `KB_RERANK_CANDIDATES` | `20` | 送入精排的候选数 |
| `KB_RERANK_THRESHOLD` | `0.01` | 精排分数门槛（评估验证最优值） |
| `KB_BM25_TOP_K` | `10` | BM25 关键词检索返回条数（中文 OR 模式自动降为 top_k/3） |
| `LIBREOFFICE_PATH` | `/usr/bin/soffice` | LibreOffice 可执行文件路径 |
| `HR_RESUME_PATH` | `uploads/简历.md` | HR Agent 候选人简历 .md 文件路径 |
| `APP_HOST` | `0.0.0.0` | FastAPI 绑定地址 |
| `APP_PORT` | `8000` | FastAPI 绑定端口 |
| `DEBUG` | `False` | 调试模式 |

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
13. 创建 User 表（id / username / password / role），启动时自动建表
14. bcrypt 密码哈希（随机盐 + 12 轮迭代），密码不存明文
15. 启动时自动种子数据：3 个管理员账号（admin / admin1 / admin2，密码 qqnanwang）
16. lifespan 管理数据库连接生命周期
17. JWT 认证：登录/注册签发 Token（含 role 字段），前端存 localStorage 实现持久登录，`get_current_user` 依赖保护接口

### WebSocket 通信层
18. WS 端点 `/ws/chat`：ticket 临时票据握手（非 JWT），一票一用 + 10 秒 TTL
19. `POST /api/v1/ws/ticket`（认证保护）：JWT 换一次性 WS 票据
20. 统一消息协议（9 种类型）：`auth.success` / `chat.request` / `chat.stream` / `chat.done` / `chat.busy` / `chat.structured` / `ping` / `pong` / `error`
21. 连接管理器：按 (user_id, session_id) 双维度索引、`send_json_to` 绑定原始 WS 防串流
22. 心跳保活：前端 30 秒发 `ping`，后端回 `pong`
23. 并发保护：按 (user_id, session_id) 隔离的 asyncio.Lock，不同会话独立
24. WS 握手优化：`ws.accept()` 提前到校验前执行，捕获 `RuntimeError` 防止刷新时崩溃
25. 旧连接不主动踢除：避免新旧连接连锁重连，自然等待旧连接超时断开

### 求职助手 Agent — 基础架构
26. LangGraph + DeepSeek 求职助手：StateGraph + add_messages 多轮对话 + 真实岗位数据库
27. `POST /api/v1/chat`（HTTP 备用）：`get_graph().ainvoke()` 一次性返回
28. WS 流式对话：`graph.astream(stream_mode="messages")` 逐 token 推送
29. 流式 token 绑定：`send_json_to(stream_chunk, ws)` 防连接顶替串流
30. 代理字符清洗（`sanitize`）：防 Unicode surrogate 致 JSON 崩溃
31. 断连保护：流式循环检测失败立即 `break` 停止浪费 API token
32. 输入容错：`.get()` 防 KeyError，`chunk.content` None 保护

### 会话隔离（session_id）
33. 前端生成 UUID，WS URL query 参数传入后端
34. 连接管理器 (user_id, session_id) → connection，同用户不同会话互不踢下线
35. 并发锁 (user_id, session_id) 隔离，不同会话独立并发
36. `session_id` 注入 loguru 日志 Context：`[request_id][session_id]`

### LangGraph Checkpoint 持久化
37. AsyncPostgresSaver + AsyncConnectionPool：StateGraph 状态实时持久化到 PG
38. `init_graph()` + `get_graph()` 懒初始化：setup() autocommit 建表，运行时连接池
39. 4 张 checkpoint 表：`checkpoints` / `checkpoint_blobs` / `checkpoint_writes` / `checkpoint_migrations`
40. `get_checkpoint_state(thread_id)`：按 session_id 反序列化消息历史
41. 有 checkpoint 后 `astream()` 只传当前 HumanMessage，历史由 checkpointer 自动恢复

### 会话管理 API
42. Session ORM 模型（`sessions` 表）：user_id / session_id / agent_type / title / created_at / updated_at
43. `GET /api/v1/sessions?agent_type=kb`：当前用户会话列表（按 agent_type 过滤，updated_at 倒序）
44. `GET /api/v1/sessions/{session_id}`：从 checkpoint 反序列化消息历史
45. `DELETE /api/v1/sessions/{session_id}`：永久删除会话（sessions 记录 + checkpoint 3 张表按 thread_id 清除）

### 简历 RAG 检索增强
46. PDF 简历上传 → 解析 → 切片 → 向量化 → 入库完整管线
47. PyMuPDF 文字型 PDF 提取 + easyocr（craft_mlt_25k + zh_sim_g2）图片型 PDF OCR 回退
48. 三层层级语义切片：正则章节标题（30+ 关键词）→ 空行段落 → RecursiveCharacterTextSplitter 兜底
49. sentence-transformers + bge-small-zh-v1.5（512 维）本地 embedding，L2 归一化
50. pgvector `vector(512)` 原生类型存储 + `<=>` 余弦距离检索
51. `POST /api/v1/resumes/upload`：上传 → 存文件立即返回，后台异步解析 → 切片 → 向量化 → 入库（每用户限 1 份）
52. `GET /api/v1/resumes`：当前用户简历列表（含 status / error_message 字段）
53. `DELETE /api/v1/resumes/{id}`：删除简历及全部切片
54. `search_resume` LangGraph Tool：LLM 检测到简历相关问题 → 自动调用工具 → pgvector 检索 top-5（含阈值过滤）
55. `search_jobs` LangGraph Tool：LLM 检测到岗位查询 → 自动调用 → pgvector 语义检索 `job_listings` 表

### 企业知识库 RAG
56. `.doc/.docx` SOP 文档上传 → 解析 → 切片 → bge-m3 向量化 → 入库完整管线
57. LibreOffice headless 转换 .doc → .docx（`subprocess.run`）+ python-docx 逐段落提取文本/表格（表格转 Markdown）+ 回退方案：UTF-16LE 直接解码
58. 数据清洗（`doc_parser.py`）：控制字符去除、Word 域代码清理、14 种法律声明/保修/RoHS 关键词过滤、孤立页码清除、XML 标签碎片和乱码行删除、空行归一化
59. 标签-说明行合并（`_merge_labels`）：将 `Save\n\n點選後...` 合并为 `Save: 點選後...`
60. 乱码检测（`_is_garbled`）只保留自然语言信号检测（中文标点 + 常见技术词汇）
61. 页面级切片（`kb_chunker.py`）：检测 Heading 1 / Heading 2 章节边界，一个页面 = 一个完整切片，自动追踪父子章节层级，子切片注入所属章标题上下文。MAX_CHUNK_SIZE=800，超长切片按段落二次拆分为 400-800 字子切片
62. Heading 自动编号：python-docx 读取 Heading 1 / Heading 2 样式，`h1++ / h2=0` 实现层级编号
63. 内容注入：入库时将 `文档：{filename}` 写入每个切片正文开头
64. sentence-transformers + bge-m3（1024 维）本地 embedding，独立于简历管线
65. pgvector `knowledge_chunks` 表 `vector(1024)` + 文档元数据冗余存储（document_name / version / source_file）
66. `POST /api/v1/knowledge/upload`：上传 → 存文件立即返回，后台异步解析 → 切片 → 向量化 → 入库
67. `GET /api/v1/knowledge`：知识库文档列表（所有用户共享，含 status / chunk_count / error_message）
68. `DELETE /api/v1/knowledge/{doc_id}`：删除文档及全部切片
69. `search_knowledge` LangGraph Tool：LLM 检测到 SOP/技术文档相关问题 → 自动调用 → 检索 top-5

### 知识库 Agent
70. `api/agent/kb_graph.py`：独立 KB Agent Graph，单 Tool search_knowledge
71. kb_advisor_node（带工具）→ tools（执行检索）→ kb_finalize_node（强制生成文本）→ format_response → END
72. 严格约束：基于检索内容回答 + 来源标注 + 检索为空明确告知 + 操作步骤按原文顺序 + 安全内容突出警示 + 繁体中文回答

### 四个 Agent 类型隔离
73. sessions 表新增 `agent_type` 字段：`job_advisor`（求职）/ `hr`（HR）/ `kb`（知识库）/ `sql_agent`（SQL 查询）
74. `GET /api/v1/sessions?agent_type=kb`：前端每个页面只拉取对应类型的会话
75. `_upsert_session()` 写入时保存 agent_type，删除时按 thread_id 跨 3 张 checkpoint 表清理

### 性能与稳定性
76. 阻塞操作卸载：`parse_pdf`（EasyOCR）、`parse_doc`（LibreOffice 转换）、`embed`/`kb_embed`（sentence-transformers）通过 `loop.run_in_executor` 卸载到线程池
77. embedding 模型离线加载：`HF_HUB_OFFLINE=1` 在 `import sentence_transformers` 之前设置
78. OCR/知识库文档上传异步化：HTTP 立即返回 `status: processing`，`asyncio.create_task` 后台处理
79. Checkpoint 脏数据清洗：检测 orphan tool_call，自动清除防止 DeepSeek 400 错误
80. PG_URL 加 `connect_timeout=5` 防止数据库不可达时无限挂起
81. bge-m3 懒加载：启动时不预热，首次知识库查询时才加载

### KB RAG 检索管线（全链路优化）

#### Query 改写
82. **LLM Query 改写**：口语问题改写为 2-3 个检索 query（术语化、中英互译、同义词扩展、子问题拆解）
83. **文档术语表注入**：从 41 个切片中 LLM 提取 231 个中英技术名词（6 类：页面/功能/硬件/操作/模式/缩写），注入 Query 改写 Prompt。术语表持久化在 `api/rag/kb_terminology.json`
84. **实体映射强制规则**：Prompt 明确要求「工程师→Engineer Page」「作业员→User Page」等页面映射，禁止自行推测

#### 混合检索
85. **Dense 语义检索**：bge-m3（1024 维）+ pgvector `<=>` 余弦距离，threshold=0.55
86. **BM25 关键词检索**：PG `tsvector`/`tsquery` 全文检索
    - 英文列（`fts`）：`to_tsvector('simple', content)`，`plainto_tsquery`（AND 语义），匹配英文术语/型号/缩写
    - 中文列（`fts_zh`）：jieba `cut_for_search` 分词 + opencc 简繁转换 → `to_tsvector('simple')` → `to_tsquery`（OR 语义 + `top_k/3` 限制），匹配中文关键词
87. **RRF 融合**：Reciprocal Rank Fusion（k=60）融合 Dense + BM25 排序结果，不依赖分数量纲

#### 精排与过滤
88. **Cross-Encoder 精排**：bge-reranker-v2-m3 对 top-20 候选做交叉注意力二次排序
89. **精排分数门槛**：`KB_RERANK_THRESHOLD=0.01`（评估验证最优值），低于阈值全部过滤时 fallback top-1
90. **LLM 相关性二次过滤**：精排后 → 轻量 LLM 逐条判 1/0 → 仅保留相关切片。全部被判 0 时 fallback top-1

#### 质量度量
91. **检索质量日志**：`kb_retrieval_logs` 表记录每次检索的原始查询/改写查询/各阶段命中数/top-3 分数/全部过滤标记/耗时
92. **`GET /api/v1/knowledge/logs`**：查询检索日志 + 自动计算 hit_rate / all_filtered_rate / avg_latency_ms
93. **评估脚本**：`eval_rag.py` 支持自定义问题集 JSON，自动化 10 题管线评估 + LLM 回答生成

### Agent 行为优化
94. 双模式自动路由：根据用户措辞自动判断「浏览模式」vs「全流程推荐」
95. 全流程推荐工作流：同时调用 search_resume + search_jobs → 岗位表格含匹配度 → 综合评估
96. 简历优化建议 / 打招呼语 / 自我介绍生成，严禁虚构经历
97. 新用户引导：无简历/偏好时正常服务，末尾温和引导上传
98. System Prompt 约束：禁止循环搜索、接受检索结果如实告知

### 用户偏好
99. `user_preferences` 表 + `GET/PUT /api/v1/preferences`
100. Agent 自动注入偏好到 System Prompt

### 日志与可观测性
101. 日志系统（loguru）：request_id + session_id 全链路追踪
102. RequestIdMiddleware：每个请求/连接日志自动携带唯一 ID

### 结构化输出
103. `StructuredResponse` Pydantic 模型（8 种响应类型）
104. `format_response_node`：独立 LLM `with_structured_output(method="json_mode")` 提取结构化 JSON
105. 静默回退：format 失败 → `structured_content = None`，纯文本照常展示

### 用户注册
106. `POST /api/v1/auth/register`：bcrypt 哈希 + 注册即登录

### HR 面试官 Agent
107. `api/agent/hr_graph.py`：独立 HR Agent，单 Tool search_resume
108. WS `agent_type: "hr"` 路由
109. 简历文件直读：通过 `HR_RESUME_PATH` 配置项将候选人 `.md` 简历全文注入 System Prompt，无需 RAG 检索

### 知识库图片提取
110. `extract_docx_images()`：从 docx zip 中提取 `word/media/` 下所有图片，过滤 WMF 格式 + < 2KB 小图标
111. `map_images_to_sections()`：遍历 docx 正文，按 Heading 1/2 章节归属图片
112. `parse_doc_with_images()`：一站式解析 .doc/.docx，同时返回清洗文本和章节-图片映射
113. `assign_images_to_chunks()`：按章节标签分层匹配，将图片分配到对应切片
114. `knowledge_chunks` 表新增 `images JSONB DEFAULT '[]'` 列
115. `kb_insert_chunks()` / `kb_search()` / `kb_bm25_search()` 适配 images 字段读写
116. `main.py` 挂载 `/static/kb-images` StaticFiles 目录，提供图片 HTTP 访问
117. KB Agent ToolMessage 中附带章节截图 URL，LLM 可自然引用
118. `_collect_images_from_state()`：从 ToolMessage 中提取图片 URL，追加到最终回复

### SQL Agent（结构化岗位查询）
119. `api/agent/sql_graph.py`：独立 SQL Agent，自然语言 → LLM 生成 SELECT → 校验（只读/白名单/CTE 支持）→ 执行 → 失败重试 → 结果结构化输出
120. SQL 校验器：正则拦截非 SELECT/DML 关键字/多语句/user_id 注入/非白名单表，自动识别 CTE 别名放行
121. `delegate_to_sql_agent` Tool：求职 Agent 工具内部调用 SQL Agent 子图（`ainvoke`，不持久化子图 checkpoint）
122. SQL 生成 Prompt：完整的 `job_listings` 表结构说明 + `salary_range`/`experience` 安全解析规则
123. 经验匹配映射表：6 档下拉选项 → `experience IN (...)` 精确匹配 + `经验不限` 兜底
124. 公司成立年限筛选：`established_date` 文本解析 → 浮点年限 → `company_years` 列输出
125. 强制过滤：`WHERE status = 'new' AND upload_date = CURRENT_DATE`

### 岗位数据管理
126. `api/jobs.py`：`POST /api/v1/jobs/upload-json` — 上传 JSON 岗位文件批量入库
127. 查重逻辑：title + url 联合判断，首次 `status='new'`，重复 `status='update'`
128. `job_listings` 表自动建表 + pgvector 扩展启用（Docker 全新数据库不依赖手动建表）
129. `_save_job_results()`：SQL Agent 查询结果 JSON 持久化到 `sessions.job_results` 列
130. `GET /api/v1/sessions/{id}/jobs`：REST 端点返回会话的持久化岗位结果

### 偏好设置精简
131. 删除字段：`work_mode`、`deal_breakers`、`industry`（→ `job_keywords`）、`company_size`、`tech_stack`、`job_status`
132. 新增字段：`job_keywords VARCHAR(50)`（岗位关键字）、`company_age INTEGER`（公司最低成立年限）
133. `experience_years` 从 `INTEGER` 改为 `VARCHAR(20)` 下拉文本
134. 数据库迁移：`user_preferences` 表自动增删列 + industry → job_keywords 数据迁移

### 简历更新通知范围修复
135. 简历上传成功后只向 `agent_type = 'job_advisor'` 的会话注入系统通知，HR 助手和知识库会话不再被打扰

### 管理员系统
136. `api/admin.py`：GET /admin/users 列出所有用户（含角色）、PUT /admin/users/{id}/role 修改角色
137. User 表新增 `role VARCHAR(20) DEFAULT 'user'` 列，启动时自动迁移
138. 路由守卫：`get_current_admin` 依赖校验 role=admin

### HR Agent 会话上下文管理器
139. `api/agent/context_manager.py`：维护基于 YAML 的提示词文本而非代码，便于非技术人员修改 System Prompt
140. 结论前置激励（HR Agent 先列出一句话精炼结论再展开分析）通过上下文管理器注入

### Docker 容器化部署
141. `Dockerfile`：python:3.12-slim + LibreOffice + libpq-dev + EasyOCR 系统依赖 + 中文字体，默认阿里云 APT/PIP 镜像源，非 root 用户运行
142. `.dockerignore`：排除 .venv / .env / logs / uploads / .git 等
143. `docker-entrypoint.sh`：启动前自动检测模型缓存，缺失时在线下载（HF_HUB_OFFLINE=0），完成后启动 uvicorn
144. `config.py` 路径兼容：`HF_HOME` 默认 `/app/models/huggingface`，`LIBREOFFICE_PATH` 默认 `/usr/bin/soffice`，`CORS_ORIGINS` 环境变量可配
145. RAG 模块适配：`embedder.py` / `kb_embedder.py` / `kb_reranker.py` 的 `os.environ.setdefault` 改用 `settings.HF_HOME`
146. `database.py` 新增 `job_listings` 建表 + pgvector 扩展启用
147. `requirements.txt` 删除 `win32_setctime`（Linux 不需要）

### WebSocket 连接稳定性修复
148. `ws.accept()` 提前到校验前执行，防止连接断开时抛 RuntimeError
149. 捕获 `RuntimeError`（非 HTTPS 下连接异常关闭）
150. 不主动踢旧 WS 连接，改为覆盖 key 自然等待旧连接消亡，消除连锁重连
151. Nginx `proxy_buffering off` 确保 WebSocket 流式推送不被缓冲

## 环境切换

项目 `config.py` 默认值为 Docker/Linux 环境。Windows 本地开发需在 `.env` 中覆盖以下配置：

```bash
HF_HOME=E:\Code Tools\huggingface
LIBREOFFICE_PATH=E:\Code Tools\LibreOffice\program\soffice.exe
CORS_ORIGINS=http://localhost:5173
HF_HUB_OFFLINE=1
```

Docker 部署时 `.env` 被 `.dockerignore` 排除，自动使用 config.py 的 Linux 默认值，无需手动切换。

## 文件结构

```
backend/job-agent-assistant-backend/
├── .env                        # 敏感配置（不提交）
├── .env.example                # 配置模板（可提交）
├── .dockerignore               # Docker 构建排除
├── .venv/                      # Python 虚拟环境
├── README.md
├── requirements.txt            # 项目依赖清单（51 个包）
├── config.py                   # pydantic-settings + DATABASE_URL/PG_URL + CORS + HF + RAG/KB 全配置
├── main.py                     # 应用组装入口（lifespan、CORS、异常处理、bge-small 预热、四 Graph 初始化）
├── run.py                      # Windows 兼容启动入口（SelectorEventLoop）
├── Dockerfile                  # Docker 镜像定义
├── docker-entrypoint.sh        # Docker 启动脚本
├── eval_rag.py                 # KB RAG 评估脚本
├── export_chunks.py            # 知识库切片导出脚本
├── extract_terminology.py      # 术语表提取脚本
└── api/
    ├── __init__.py
    ├── admin.py                # 管理员 API（用户列表 + 角色修改）
    ├── auth.py                 # 登录 + 注册 + JWT 签发（含 role 字段）
    ├── chat.py                 # HTTP 聊天接口（备用）
    ├── database.py             # SQLAlchemy 引擎 + 会话 + 建表 + 迁移 + 种子数据 + pgvector
    ├── dependencies.py         # get_current_user / get_current_admin 认证依赖
    ├── health.py               # 健康检查
    ├── knowledge.py            # 知识库文档管理（upload/list/delete + 图片提取 + 后台处理）+ 检索日志
    ├── log.py                  # 日志配置中心（loguru）
    ├── middleware.py            # RequestId 中间件
    ├── router.py               # v1 路由汇总（10 个模块）
    ├── security.py             # bcrypt / JWT 签发 / JWT 解析
    ├── sessions.py             # 会话管理（GET list + GET messages + DELETE + jobs）
    ├── resumes.py              # 简历管理（POST upload 异步 + GET list + DELETE + download）
    ├── preferences.py          # 用户偏好（GET + PUT，精简字段）
    ├── jobs.py                 # 岗位管理（POST upload-json 批量入库 + 查重 title+url）
    ├── agent/
    │   ├── __init__.py
    │   ├── graph.py            # 求职顾问 Agent（search_resume + delegate_to_sql_agent + 偏好注入 + 结构化输出）
    │   ├── hr_graph.py         # HR 面试官 Agent（简历文件直读 + 结构化输出，无 tool 直线架构）
    │   ├── kb_graph.py         # 知识库 Agent（Query改写 + 混合检索 + 精排 + LLM过滤 + 图片注入）
    │   ├── sql_graph.py        # SQL Agent（自然语言→SQL 生成/校验/执行/重试 + 经验映射 + 公司年限）
    │   ├── context_manager.py  # HR Agent 上下文管理器（YAML 提示词 + 结论前置）
    │   └── schemas.py          # StructuredResponse + JobItem Pydantic 模型
    ├── models/
    │   ├── __init__.py         # User / Session / ResumeDocument / RegistrationLog / KnowledgeDocument
    │   ├── user.py             # User 表（username + bcrypt password + role）
    │   ├── session.py          # Session 表（agent_type + job_results JSON）
    │   ├── resume.py           # ResumeDocument 表
    │   ├── preference.py       # UserPreference 表（精简字段）
    │   ├── knowledge_document.py    # KnowledgeDocument 表
    │   └── registration_log.py     # RegistrationLog 表
    ├── rag/
    │   ├── __init__.py
    │   ├── parser.py           # PDF 解析（PyMuPDF + easyocr OCR）
    │   ├── doc_parser.py       # DOC/DOCX 解析（LibreOffice 转换 + python-docx + 数据清洗 + 图片提取）
    │   ├── chunker.py          # 简历语义切片（三层）
    │   ├── kb_chunker.py       # SOP 手册切片（章节边界 + 父子层级追踪 + 图片关联分配）
    │   ├── embedder.py         # bge-small embedding（512维，离线加载）
    │   ├── kb_embedder.py      # bge-m3 embedding（1024维，离线加载）
    │   ├── kb_reranker.py      # bge-reranker-v2-m3 Cross-Encoder 精排（模块级单例）
    │   ├── kb_terminology.json # 文档术语表（231个中英技术名词，6类）
    │   ├── store.py            # pgvector 简历存取 + 岗位检索
    │   └── kb_store.py         # pgvector 知识库存取 + BM25 中英文双列检索 + 检索日志
    ├── ws/
    │   ├── __init__.py
    │   ├── protocol.py         # 消息协议（9 种类型 + WSMessage 模型）
    │   ├── manager.py          # 连接管理器（(user_id, session_id) 双维度，旧连接自然消亡）
    │   ├── chat.py             # WS 端点 + HTTP 换票 + agent_type 四路路由 + 流式处理 + 结构化输出
    │   ├── lock.py             # 用户会话级异步锁
    │   └── ticket.py           # 票据存储（10s TTL + 一票一用）
    └── schemas/
        ├── __init__.py
        └── response.py         # ApiResponse 统一格式
```

## Docker Compose 项目级文件

```
job-agent-assistant/
├── docker-compose.yml          # 基础编排（3 服务 + 5 volume）
├── docker-compose.local.yml    # 本地开发覆盖（挂载 Windows 模型路径 + 阿里云镜像源）
├── docker-compose.prod.yml     # 生产覆盖（HF 在线下载 + CORS 域名 + WS 公网 URL）
├── .env.docker.example         # Docker 环境变量模板
├── .env.docker                 # Docker 实际环境变量（不提交 git）
└── scripts/
    └── download_models.py      # HF 模型预下载工具
```

## 知识库 RAG 检索全链路

```
用户提问
  │
  ├─ Query 改写 (LLM + 术语表注入 + 实体映射)
  │
  ├─ Dense 检索 (bge-m3 + pgvector, threshold=0.55)
  │     └─ BM25 英文检索 (fts 列, AND 语义)
  │     └─ BM25 中文检索 (fts_zh 列, jieba+opencc, OR 语义)
  │
  ├─ RRF 融合 (k=60, 多 query 去重)
  │
  ├─ Cross-Encoder 精排 (bge-reranker-v2-m3, top-20→top-5)
  │
  ├─ 精排阈值过滤 (threshold=0.01, fallback top-1)
  │
  ├─ LLM 相关性二次过滤 (逐条判1/0, fallback top-1)
  │
  └─ LLM 生成回答 (System Prompt + 检索上下文)
```
