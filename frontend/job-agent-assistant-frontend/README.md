# Job Agent Assistant — 前端

## 技术栈

| 技术 | 用途 |
|---|---|
| Vue 3 | UI 框架（Composition API + `<script setup>`） |
| TypeScript 6 | 类型安全 |
| Vite 8 | 构建工具 + 开发服务器 |
| Vue Router 5 | 前端路由（嵌套布局 + 角色守卫） |
| Pinia 3 | 状态管理（含 isAdmin 计算属性） |
| Axios | HTTP 请求 |
| Element Plus 2 | UI 组件库 |

## 依赖包

### 生产依赖

| 包 | 版本 | 用途 |
|---|---|---|
| vue | ^3.5.34 | UI 框架 |
| vue-router | ^5.1.0 | 前端路由管理 + 全局守卫 |
| pinia | ^3.0.4 | 全局状态管理（认证状态 + 角色） |
| axios | ^1.17.0 | HTTP 客户端，请求/响应拦截器 |
| element-plus | ^2.14.1 | UI 组件库（表单、按钮、输入框、表格、弹窗等） |
| marked | ^15.0.12 | Markdown 解析（GFM 表格/换行/JSON尾部裁剪） |

### 开发依赖

| 包 | 版本 | 用途 |
|---|---|---|
| typescript | ~6.0.2 | 类型检查 |
| vite | ^8.0.12 | 构建工具 + 开发服务器 |
| @vitejs/plugin-vue | ^6.0.6 | Vite Vue 插件 |
| vue-tsc | ^3.2.8 | Vue TypeScript 类型检查 |
| @vue/tsconfig | ^0.9.1 | Vue TypeScript 配置预设 |
| @types/node | ^24.12.3 | Node.js 类型定义 |

## 配置文件

| 文件 | 用途 |
|---|---|
| `.env.development` | 开发环境变量（API 走 Vite 代理） |
| `.env.production` | 生产环境变量（直连后端或 Nginx 反代） |
| `.env.example` | 环境变量模板 |
| `vite.config.ts` | Vite 配置（含 API + WebSocket + static 代理到后端 8000） |
| `Dockerfile` | 多阶段构建（node:20 构建 + nginx:alpine 托管静态文件+反代） |
| `.dockerignore` | Docker 构建排除文件 |
| `nginx/nginx.conf` | Nginx 配置（API/WS 反代 + SPA fallback） |

### 环境变量

| 变量 | 开发值 | 生产值 | 用途 |
|---|---|---|---|
| `VITE_API_BASE_URL` | `/api/v1` | `/api/v1`（Nginx 反代）或完整 URL | Axios HTTP baseURL |
| `VITE_WS_BASE_URL` | `ws://localhost:5173/api/v1` | `ws://localhost/api/v1`（Docker）/ `wss://域名`（生产） | WebSocket 连接地址 |
| `VITE_APP_TITLE` | `AI 找工作助手` | `AI 找工作助手` | 应用标题 |

> **注意**：Vite 在**构建时**将环境变量内联到 JS bundle，运行时不可更改。Docker 中通过 `/api/v1` 路径式 URL + Nginx 反代实现跨环境通用。网页标题通过 `document.title` 运行时动态更新，不受构建限制。

## 已完成工作

### 基础设施
1. 用 Vite 创建 Vue 3 + TypeScript 项目骨架
2. 安装并配置 Vue Router，嵌套路由 + 全局守卫（含角色校验）
3. 安装并注册 Pinia，`stores/auth.ts` 管理认证 + 用户信息 + 角色

### 认证与 HTTP 层
4. 封装 Axios（baseURL、超时、Token 自动附加、401 自动跳登录）
5. 响应拦截器对接后端 `ApiResponse` 统一格式（`{ code, data, message }`），code=0 解包 data
6. 登录/注册页面（`Login.vue`）：Element Plus 苹果风格白卡片，登录/注册双模式切换，密码最低 6 位 + 确认密码校验
7. JWT Token 管理：登录/注册存 localStorage（持久登录），刷新自动恢复，退出清除 token + sessionId

### 布局与导航
8. Apple 风格整体布局：毛玻璃 Header + 侧边导航 + 内容区
9. `MainLayout.vue`：布局框架，Header 含用户信息 + 退出，品牌名根据角色动态切换（管理员→「AI 找工作助手」，普通用户→「AI HR助手」）
10. `SideNav.vue`：左侧导航栏，按角色过滤显示（管理员 7 项 / 普通用户 3 项：仪表盘 + HR 助手 + 我的简历）
11. 仪表盘（`Home.vue`）：系统状态卡片 + 按角色展示功能模块（管理员 7 个模块 / 普通用户 2 个模块），点击可跳转
12. 天气助手（`Weather.vue`）：HTTP 聊天对话框，气泡消息，多轮对话
13. 全局样式：Apple 系统字体栈（SF Pro / PingFang SC），毛玻璃效果
14. 网页标题动态更新（`App.vue`）：未登录→`job-agent-assistant-frontend`，管理员→`AI 找工作助手`，普通用户→`AI HR助手`

### WebSocket 通信层
15. `useWebSocket` composable：模块级单例，所有组件共享同一连接
16. WS 安全握手：`connect()` 先 POST `/ws/ticket` 换票据（JWT 在请求头），再用票据 + session_id 建 WS
17. WS 生命周期管理：`App.vue` 监听 authStore.token 自动 connect / disconnect
18. 心跳保活：30 秒间隔自动发 `ping`，非主动断开（code = 1000/1001）5 秒自动重连
19. 事件注册/注销：`on(type, handler)` / `off(type, handler)`，持久化在模块级 handlers Map
20. 断连回调：`onClose` / `offClose`，组件注册后 WS 断开时自动通知
21. 发送保护：`send()` 返回 `boolean`，WS 未连通时拒绝发送
22. 换票失败重试：非 401 错误自动 5 秒重试换票 + 重连
23. 连接错误 UI 反馈：`ws.error` 变化时推送黄色系统通知到聊天区

### 会话管理
24. session_id 由前端 `crypto.randomUUID()` 生成，WS URL query 参数传递给后端
25. sessionStorage 持久化 sessionId：断线重连复用同一会话，不丢 checkpoint 上下文
26. `newSession()` 方法：清除旧 sessionId → disconnect → connect（生成新 UUID）
27. `connect()` 优先复用 sessionStorage 中的旧 sessionId

### 会话侧边栏
28. 会话列表卡片右侧展示：按 `updated_at` 倒序，最新在上
29. 点击卡片切换会话：从后端拉取完整消息历史 → 展示 → 断开 WS 并以选中 session_id 重连
30. "+ 新对话"按钮：`ws.newSession()`，清空聊天区 + 刷新侧边栏
31. LLM 回复完成后自动刷新会话列表（`chat.done` 触发 `loadSessions`）
32. 首次进入页面：有历史会话 → 自动加载最新；无历史 → 使用当前 WS sessionId

### 三个 Agent 页面会话隔离
33. 求职助手/HR助手/知识库三个页面各传各自的 `agent_type`（`job_advisor` / `hr` / `kb`）给 `fetchSessions()`
34. 后端按 agent_type 过滤返回，三个页面的对话列表互不干扰
35. `ws.send()` 携带对应的 `agent_type`，后端据此路由到不同 Agent Graph

### 简历上传与管理
36. 输入框旁 📎 上传按钮（`<input type="file" accept=".pdf">`），已有简历时自动禁用
37. 上传后异步后台处理：前端立即收到 `status: processing`，轮询至 `ready` 后刷新列表
38. 上传期间侧边栏显示实时计时器「解析中... Xs」
39. 简历列表展示文件名 + 删除按钮，processing 状态简历不显示在列表中
40. 上传前自动删除旧简历（每用户限 1 份）
41. 上传期间禁用输入框和发送按钮，防止消息与简历状态交叉混乱

### 求职助手（JobAssistant.vue）
42. WS 流式对话 UI：预埋空 assistant 气泡 → `chat.stream` 逐 token 追加 → `chat.done` 解锁
43. 多轮对话上下文由后端 checkpoint 自动恢复，前端不再传完整 history
44. 断连清理：流式回复中 WS 断开 → 删除未完成消息对 → 补 `[连接中断]` 通知
45. 非发送过程断连提示：code 1001（被其他页面顶替）时显示提示
46. 发送失败回滚：`ws.send()` 返回 `false` 时 pop 预埋消息对
47. 并发拒绝处理：后端 Agent 正忙时 `chat.busy` → 回滚 + 系统通知 + 解锁
48. system 角色消息：黄色居中样式，不与对话气泡混淆
49. token 追加健壮性：`onStream` 从后往前查找 assistant 消息
50. LLM 调用工具时前端实时显示"（正在检索...）"

### HR 面试助手（HRAssistant.vue）
51. HR 聊天页面（紫色主题 `#7c3aed`），WS 流式对话 + 结构化渲染 + 会话侧边栏
52. `ws.send()` 携带 `agent_type: 'hr'`
53. 路由 `/hr-assistant`（需登录）

### 企业知识库助手（KnowledgeAssistant.vue）
54. 知识库聊天页面（绿色主题 `#059669`），WS 流式对话 + 结构化渲染 + 会话侧边栏
55. `ws.send()` 携带 `agent_type: 'kb'`，后端路由到 KB Agent Graph
56. 路由 `/knowledge-assistant`（需登录）
57. 📎 上传按钮：支持 .doc/.docx 文件上传 → 后台 LibreOffice 解析 → 切片 → bge-m3 向量化 → 入库
58. 右侧面板文档列表：展示已上传文档（文件名 + 状态），processing 时显示「解析中... Xs」计时器，ready 时显示切片数
59. 轮询机制：有 processing 状态的文档时每 2 秒自动刷新列表，全部 ready 后停止
60. 文档删除：hover 卡片的红色删除按钮，删除文档及其全部切片

### Agent 智能工作流（后端 Prompt 驱动）
61. 双模式自动路由：浏览模式 vs 全流程推荐
62. 岗位匹配度分析 / 简历优化建议 / 打招呼语与自我介绍
63. 新用户引导：无简历时正常服务，尾部温和提醒

### 结构化输出渲染
64. `chat.structured` WS 事件处理：接收后端结构化 JSON，附加到对应 assistant 消息
65. `StructuredMessage.vue`：根据 `response_type` 渲染不同组件（岗位表格 / 匹配度分析）
66. 回退机制：无 `structured` 数据时纯文本正常展示；有结构化数据时原文本降为次要展示（小字号灰色）

### 求职偏好设置
67. 侧边栏「⚙ 求职偏好」按钮 → 弹出 Modal 表单
68. 5 个可选字段：城市、薪资范围、岗位关键字、经验年限（7 档下拉）、公司成立年限
69. `fetchPreferences()` / `savePreferences()` 对接后端 API

### 用户注册
70. 登录页改为登录/注册双模式：卡片内 `isRegister` 切换，无需跳转新路由
71. 注册表单：账号 + 密码 + 确认密码（含一致性校验），密码最低 6 位
72. `registerApi()` + authStore `register()`：调 `POST /auth/register`，注册成功自动登录跳回原页面

### 权限与导航优化
73. 公开路由：`/`（首页）和 `/weather`（天气助手）无需登录即可访问；`/job-assistant`、`/hr-assistant`、`/knowledge-assistant` 需登录
74. 未登录拦截：点击需登录页面 → `ElMessage.warning` 提示「请先登录」→ 3 秒后自动跳 `/login?redirect=原路径` → 登录后跳回
75. Token 存储：localStorage 持久化，关闭浏览器后保持登录状态
76. Header 自适应：未登录显示「登录」按钮，已登录显示用户名 +「退出登录」
77. 退出行为：清除 token + sessionId → 跳转 `/login`

### 环境与配置
78. 环境变量：`.env.development` / `.env.production` + `env.d.ts` 类型声明
79. WebSocket 代理：Vite 开发服务器 `ws://` 转发到后端 `/ws/chat`
80. 路由守卫：未登录访问需认证页面 → 弹 toast → 3 秒后跳登录页；已登录访问登录页 → 跳主页

### 知识库图片渲染
81. `parseContent()`：将 assistant 消息中的 `![截图](url)` markdown 解析为文本/图片混合段落（`ContentSegment[]`），模板用 `<template v-for>` 安全渲染
82. 图片样式：圆角阴影、`max-height: 360px`、hover 放大效果、`loading="lazy"` 懒加载
83. 图片灯箱：点击图片弹出全屏遮罩（`img-lightbox`），`max-width: 92vw/max-height: 92vh`，点击背景关闭
84. Vite 代理新增 `/static` 路径 → 后端 `:8000`，确保知识库图片 `/static/kb-images/...` 在开发环境可访问

### 简历查看器
85. `ResumeViewer.vue`：简历图片展示页（`/resume` 路由），`el-image` 点击放大预览 + PDF 下载按钮
86. 图片占位提示：图片不存在时显示占位 SVG，引导用户放置实际图片
87. 简历文件下载：从后端下载求职助手中上传的 PDF 简历

### 岗位查询结果面板
88. 右侧 `el-table` 面板（岗位名称/公司/薪资/经验/司龄），始终占位与聊天区/会话栏按 flex 3:1:3 比例平摊
89. 空状态占位提示：「暂无查询结果，输入筛选条件后自动展示」
90. 岗位结果持久化：`GET /sessions/{id}/jobs` 在 `chat.done` 和 `switchToSession` 时加载，刷新/切换会话不丢失
91. `all_jobs` 字段：聊天区 `StructuredMessage` 只渲染前 10 条，右侧面板展示全部

### 岗位上传
92. 侧边栏「📤 上传岗位」按钮：选择 JSON 文件 → `POST /jobs/upload-json`，结果提示新增/更新条数

### 对话体验优化
93. `cleanContent()`：正则裁掉 LLM 回复末尾附带的 JSON 数据（`{"response_type":`）
94. `onDone` 顺序修复：`loadSessions` 在 `sending=false` 之前执行，防止 `switchToSession` 覆盖流式回答
95. `onStructured` 分流：只有 `full_recommendation` / `match_analysis` 挂 `msg.structured` 走 `StructuredMessage` 渲染，其他类型保留 LLM 原文
96. ToolMessage / SystemMessage 过滤：`get_session_messages` 不返回内部消息给前端

### 偏好设置精简
97. 删除：工作模式下拉、技术方向输入、公司规模输入、排除条件输入、求职状态下拉
98. 经验年限 → 7 档下拉框（不限/在校应届/1年以内/1-3年/3-5年/5-10年/10年以上）
99. 新增：公司成立时间（年）输入框

### Docker 容器化部署
100. `Dockerfile`：多阶段构建（node:20-alpine 构建 + nginx:alpine 托管），支持国内 NPM 镜像源
101. `.dockerignore`：排除 node_modules / dist / .git / .env 等
102. `nginx/nginx.conf`：统一入口设计 — 静态文件服务 + `/api/*` 反代（含 WebSocket upgrade）+ `/static/*` 代理 + SPA fallback
103. 前端构建时 `vue-tsc -b` 替换为 `npx vite build`，跳过 Docker 构建环境中的 TS 严格检查

### 角色权限与人员管理
104. authStore 新增 `isAdmin` 计算属性：根据 `user.role === 'admin'` 判断
105. `SideNav.vue`：导航项按角色过滤，管理员全部 7 项可见，普通用户仅 3 项（仪表盘 / HR 助手 / 我的简历）
106. `MainLayout.vue`：Header 品牌名按角色动态切换
107. `App.vue`：`document.title` 按角色动态更新网页标题
108. `Home.vue`：功能模块卡片按角色展示（管理员 7 个 / 普通用户 2 个），点击可跳转到对应页面
109. `UserManagement.vue`：人员管理页面（`/admin/users`），Element Plus 表格展示所有普通用户（账号 / 明文密码），支持删除确认弹窗 + 级联清理
110. `api/admin.ts`：`fetchUsers()` + `deleteUser()` 对接后端管理员 API
111. 路由守卫新增 `requiresAdmin` meta：`getUserRole()` 解析 JWT payload 中的 role 字段，非管理员访问 `/admin/users` 时拦截跳转首页
112. `auth.ts` API 类型：`UserInfo` 含 `role` 字段，登录/注册返回均含 `role`

### Markdown 渲染与对话体验
113. 安装 `marked` 库，`src/utils/markdown.ts` 统一封装 `renderMarkdown()`：GFM 表格 + 换行 + JSON 尾部裁剪
114. 三个聊天页（求职/HR/知识库）全部改用 `v-html="renderMarkdown()"` 替代纯文本渲染，支持标题、加粗、表格、列表、引用、行内代码
115. Assistant 气泡内 markdown 元素完整样式：标题/段落/表格/列表/代码块/引用/图片
116. `cleanContent()` 移除，JSON 裁剪逻辑并入 `renderMarkdown()`

### 页面布局优化
117. MainLayout 内容区移除 padding，三个聊天页各自 `padding: 24px`，宽度填满
118. 聊天页布局从固定高度改为 `flex: 1; min-height: 0`，高度自适应窗口
119. 聊天框与侧边栏比例调整为 3:1（chat `flex: 3`，sidebar `flex: 1`）
120. 聊天气泡间距 8px → 16px，用户气泡 `padding: 6px 16px; line-height: 1.4` 紧贴文字
121. 仪表盘、简历查看器补回内边距

### 简历查看器
122. `ResumeViewer.vue`：三张简历图片（`/resume/resume1-3.png`）三列网格 + 点击放大
123. 下载按钮移至顶部标题栏右侧，避免长页面滚动

## 文件结构

```
frontend/job-agent-assistant-frontend/
├── .env.development       # 开发环境变量
├── .env.production        # 生产环境变量
├── .env.example           # 环境变量模板
├── .dockerignore          # Docker 构建排除
├── index.html
├── package.json
├── tsconfig.json
├── tsconfig.app.json
├── tsconfig.node.json
├── vite.config.ts         # Vite 配置（API + WS + /static 代理 → localhost:8000）
├── Dockerfile             # 多阶段构建（node:20 + nginx:alpine）
├── nginx/
│   └── nginx.conf         # Nginx 配置（反代 + WS + SPA fallback）
└── src/
    ├── main.ts            # 入口，注册 Pinia + Router + Element Plus
    ├── App.vue            # 根组件（<router-view /> + WS 生命周期管理 + 网页标题动态更新）
    ├── style.css          # 全局样式（Apple 字体栈）
    ├── env.d.ts           # 环境变量类型声明
    ├── api/
    │   ├── client.ts       # Axios（Token 自动附加 / ApiResponse 解包 / 401 跳登录）
    │   ├── auth.ts         # POST /auth/login + POST /auth/register + GET /auth/me（含 role）
    │   ├── admin.ts        # GET /admin/users + DELETE /admin/users/{id}（管理员端点）
    │   ├── chat.ts         # POST /chat（HTTP 备用，天气助手使用）
    │   ├── health.ts       # GET /health
    │   ├── sessions.ts     # GET /sessions?agent_type= + GET /sessions/{id} + DELETE /sessions/{id} + GET /sessions/{id}/jobs
    │   ├── resumes.ts      # POST /resumes/upload + GET /resumes + DELETE /resumes/{id} + download
    │   ├── knowledge.ts    # POST /knowledge/upload + GET /knowledge + DELETE /knowledge/{id}
    │   ├── preferences.ts  # GET /preferences + PUT /preferences（精简字段）
    │   └── jobs.ts         # POST /jobs/upload-json
    ├── types/
    │   └── structured.ts   # StructuredContent + JobItem（含 company_years / all_jobs）类型定义
    ├── router/
    │   └── index.ts        # 嵌套路由（8 条）+ 全局守卫（含 requiresAdmin 角色校验 + JWT payload role 解析）
    ├── stores/
    │   └── auth.ts         # 认证状态（token / user / isAdmin / login / register / logout / init）
    ├── layouts/
    │   └── MainLayout.vue  # 毛玻璃 Header（品牌名动态切换）+ SideNav + <router-view>
    ├── components/
    │   ├── SideNav.vue      # 左侧导航栏（按角色过滤：admin 7 项 / user 3 项）
    │   └── StructuredMessage.vue  # 结构化响应渲染（岗位表格 / 匹配度分析）
    ├── views/
    │   ├── Login.vue       # 登录/注册页（双模式切换）
    │   ├── Home.vue         # 仪表盘（状态卡片 + 按角色展示功能模块，点击跳转）
    │   ├── Weather.vue      # 天气助手（HTTP 聊天对话框）
    │   ├── JobAssistant.vue # 求职助手（WS 流式聊天 + 会话侧边栏 + 简历上传 + 偏好设置 + 岗位上传 + 结果面板，agent_type: job_advisor）
    │   ├── HRAssistant.vue  # HR 助手（WS 流式聊天 + 会话侧边栏，紫色主题，agent_type: hr）
    │   ├── KnowledgeAssistant.vue  # 知识库助手（WS 流式聊天 + 文档上传 + 文档列表 + 图片渲染/灯箱，绿色主题，agent_type: kb）
    │   ├── ResumeViewer.vue # 简历查看器（图片预览 + PDF 下载）
    │   └── UserManagement.vue   # 人员管理（管理员专属，普通用户列表表格 + 删除确认弹窗）
    ├── composables/
    │   └── useWebSocket.ts  # WS 单例（sessionId 持久化 + newSession + ticket 换票 + 心跳 + 重连）
    ├── utils/
    │   └── markdown.ts      # Markdown 渲染（marked + GFM + JSON 尾部裁剪）
    └── assets/              # 静态资源
```
