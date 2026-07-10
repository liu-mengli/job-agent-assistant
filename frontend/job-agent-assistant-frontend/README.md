# Job Agent Assistant — 前端

## 技术栈

| 技术 | 用途 |
|---|---|
| Vue 3 | UI 框架（Composition API + `<script setup>`） |
| TypeScript | 类型安全 |
| Vite | 构建工具 + 开发服务器 |
| Vue Router | 前端路由（嵌套布局） |
| Pinia | 状态管理 |
| Axios | HTTP 请求 |
| Element Plus | UI 组件库 |

## 新增的包

| 包 | 用途 |
|---|---|
| vue-router | 前端路由管理 + 全局守卫 |
| pinia | 全局状态管理（认证状态） |
| axios | HTTP 客户端，请求/响应拦截器 |
| element-plus | UI 组件库（表单、按钮、输入框等） |

## 配置文件

| 文件 | 用途 |
|---|---|
| `.env.development` | 开发环境变量（API 走 Vite 代理） |
| `.env.production` | 生产环境变量（直连后端） |
| `.env.example` | 环境变量模板 |
| `vite.config.ts` | Vite 配置（含 API + WebSocket 代理到后端 8000） |

## 已完成工作

### 基础设施
1. 用 Vite 创建 Vue 3 + TypeScript 项目骨架
2. 安装并配置 Vue Router，嵌套路由 + 全局守卫
3. 安装并注册 Pinia，`stores/auth.ts` 管理认证 + 用户信息

### 认证与 HTTP 层
4. 封装 Axios（baseURL、超时、Token 自动附加、401 自动跳登录）
5. 响应拦截器对接后端 `ApiResponse` 统一格式（`{ code, data, message }`），code=0 解包 data
6. 登录页面（`Login.vue`）：Element Plus 苹果风格白卡片
7. JWT Token 管理：登录存 sessionStorage，刷新自动恢复，退出清除

### 布局与导航
8. Apple 风格整体布局：毛玻璃 Header + 侧边导航 + 内容区
9. `MainLayout.vue`：布局框架，Header 含用户信息 + 退出
10. `SideNav.vue`：左侧导航栏（仪表盘 / 天气助手 / 求职助手）
11. 仪表盘（`Home.vue`）：系统状态卡片
12. 天气助手（`Weather.vue`）：HTTP 聊天对话框，气泡消息，多轮对话
13. 全局样式：Apple 系统字体栈（SF Pro / PingFang SC），毛玻璃效果

### WebSocket 通信层
14. `useWebSocket` composable：模块级单例，所有组件共享同一连接
15. WS 安全握手：`connect()` 先 POST `/ws/ticket` 换票据（JWT 在请求头），再用票据 + session_id 建 WS
16. WS 生命周期管理：`App.vue` 监听 authStore.token 自动 connect / disconnect
17. 心跳保活：30 秒间隔自动发 `ping`，非主动断开（code ≠ 1000/1001）5 秒自动重连
18. 事件注册/注销：`on(type, handler)` / `off(type, handler)`，持久化在模块级 handlers Map
19. 断连回调：`onClose` / `offClose`，组件注册后 WS 断开时自动通知
20. 发送保护：`send()` 返回 `boolean`，WS 未连通时拒绝发送
21. 换票失败重试：非 401 错误自动 5 秒重试换票 + 重连
22. 连接错误 UI 反馈：`ws.error` 变化时推送黄色系统通知到聊天区

### 会话管理
23. session_id 由前端 `crypto.randomUUID()` 生成，WS URL query 参数传递给后端
24. sessionStorage 持久化 sessionId：断线重连复用同一会话，不丢 checkpoint 上下文
25. `newSession()` 方法：清除旧 sessionId → disconnect → connect（生成新 UUID）
26. `connect()` 优先复用 sessionStorage 中的旧 sessionId

### 会话侧边栏
27. 会话列表卡片右侧展示：按 `updated_at` 倒序，最新在上
28. 点击卡片切换会话：从后端拉取完整消息历史 → 展示 → 断开 WS 并以选中 session_id 重连
29. "+ 新对话"按钮：`ws.newSession()`，清空聊天区 + 刷新侧边栏
30. LLM 回复完成后自动刷新会话列表（`chat.done` 触发 `loadSessions`）
31. 首次进入页面：有历史会话 → 自动加载最新；无历史 → 使用当前 WS sessionId

### 简历上传与管理
32. 输入框旁 📎 上传按钮（`<input type="file" accept=".pdf">`），已有简历时自动禁用
33. 上传后异步后台处理：前端立即收到 `status: processing`，轮询至 `ready` 后刷新列表
34. 上传期间侧边栏显示实时计时器「解析中... Xs」
35. 简历列表展示文件名 + 删除按钮，processing 状态简历不显示在列表中
36. 上传前自动删除旧简历（每用户限 1 份）
37. 上传期间禁用输入框和发送按钮，防止消息与简历状态交叉混乱

### 求职助手（JobAssistant.vue）
38. WS 流式对话 UI：预埋空 assistant 气泡 → `chat.stream` 逐 token 追加 → `chat.done` 解锁
39. 多轮对话上下文由后端 checkpoint 自动恢复，前端不再传完整 history
40. 断连清理：流式回复中 WS 断开 → 删除未完成消息对 → 补 `[连接中断]` 通知
41. 非发送过程断连提示：code 1001（被其他页面顶替）时显示提示
42. 发送失败回滚：`ws.send()` 返回 `false` 时 pop 预埋消息对
43. 并发拒绝处理：后端 Agent 正忙时 `chat.busy` → 回滚 + 系统通知 + 解锁
44. system 角色消息：黄色居中样式，不与对话气泡混淆
45. token 追加健壮性：`onStream` 从后往前查找 assistant 消息
46. LLM 调用工具时前端实时显示"（正在检索...）"

### Agent 智能工作流（后端 Prompt 驱动）
47. 双模式自动路由：浏览模式（「看看岗位」→ 简洁岗位表）vs 全流程推荐（「推荐适合我的」→ 匹配度+评估+下一步）
48. 岗位匹配度分析：匹配百分比 + 技能逐项对比表 + 优势短板 + 投递建议
49. 简历优化建议：5 维度分析（突出经历/关键词/弱描述/删减建议/优化示例），严禁虚构
50. 打招呼语与自我介绍：基于简历生成招呼语 + 面试自我介绍 + 个人优势话术
51. 新用户引导：无简历时正常服务，尾部温和提醒，不阻塞不重复

### 会话管理增强
52. 会话卡片 hover 显示删除按钮：默认 `⋯` → hover 切换红色「删除」按钮
53. 删除当前活跃会话时自动切换到最新会话并加载消息

### 求职偏好设置
54. 侧边栏「⚙ 求职偏好」按钮 → 弹出 Modal 表单
55. 10 个可选字段：城市、工作模式（下拉）、薪资范围（元/月）、行业、公司规模、技术方向、经验年限、求职状态（下拉）、排除条件
56. `fetchPreferences()` / `savePreferences()` 对接后端 API
57. 偏好数据注入 Agent System Prompt，影响岗位推荐和匹配分析
### 结构化输出渲染
58. `chat.structured` WS 事件处理：接收后端结构化 JSON，附加到对应 assistant 消息的 `structured` 字段
59. `StructuredMessage.vue`：根据 `response_type` 渲染不同组件——`browse`/`full_recommendation` 岗位表格（含匹配度彩色徽章）、`match_analysis` 环形匹配度分数 + 技能对比表（✅匹配/⚠️部分/❌缺失高亮行）
60. 回退机制：无 `structured` 数据时纯文本正常展示；有结构化数据时原文本降为次要展示（小字号灰色）

### 环境与配置
61. 环境变量：`.env.development` / `.env.production` + `env.d.ts` 类型声明
62. WebSocket 代理：Vite 开发服务器 `ws://` 转发到后端 `/ws/chat`
63. 路由守卫：未登录 → 跳登录页 / 已登录访问登录页 → 跳主页

## 文件结构

```
frontend/job-agent-assistant-frontend/
├── .env.development       # 开发环境变量
├── .env.production        # 生产环境变量
├── .env.example           # 环境变量模板
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts         # Vite 配置（API + WS 代理 → localhost:8000）
└── src/
    ├── main.ts            # 入口，注册 Pinia + Router + Element Plus
    ├── App.vue            # 根组件（<router-view /> + WS 生命周期管理）
    ├── style.css          # 全局样式（Apple 字体栈）
    ├── env.d.ts           # 环境变量类型声明
    ├── api/
    │   ├── client.ts       # Axios（Token 自动附加 / ApiResponse 解包 / 401 跳登录）
    │   ├── health.ts       # GET /health
    │   ├── auth.ts         # POST /auth/login + GET /auth/me
    │   ├── chat.ts         # POST /chat（HTTP 备用）
    │   ├── sessions.ts     # GET /sessions + GET /sessions/{id} + DELETE /sessions/{id}
    │   ├── resumes.ts      # POST /resumes/upload + GET /resumes + DELETE /resumes/{id}（含 status / error_message）
    │   └── preferences.ts  # GET /preferences + PUT /preferences
    ├── types/
    │   └── structured.ts   # StructuredContent 类型定义（与后端 Pydantic 模型对应）
    ├── router/
    │   └── index.ts       # 嵌套路由（MainLayout → 子页面）+ 全局守卫
    ├── stores/
    │   └── auth.ts        # 认证状态（token / user / login / logout / init）
    ├── layouts/
    │   └── MainLayout.vue # 毛玻璃 Header + SideNav + <router-view>
    ├── components/
    │   ├── SideNav.vue    # 左侧导航栏（仪表盘/天气助手/求职助手）
    │   └── StructuredMessage.vue  # 结构化响应渲染（岗位表格 / 匹配度分析）
    ├── views/
    │   ├── Login.vue      # 登录页
    │   ├── Home.vue       # 仪表盘（状态卡片）
    │   ├── Weather.vue    # 天气助手（HTTP 聊天对话框）
    │   └── JobAssistant.vue # 求职助手（WS 流式聊天 + 会话侧边栏（含删除）+ 简历异步上传 + 偏好设置 + 断连/并发防护）
    ├── composables/
    │   └── useWebSocket.ts  # WS 单例（sessionId 持久化 + newSession + ticket 换票 + 心跳 + 重连）
    └── assets/            # 静态资源
```
