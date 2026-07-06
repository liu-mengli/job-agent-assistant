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
32. 输入框旁 📎 上传按钮（`<input type="file" accept=".pdf">`）
33. 上传期间侧边栏显示实时计时器「解析中... Xs」
34. 简历列表展示文件名 + 删除按钮
35. 上传前自动删除旧简历（每用户限 1 份）

### 求职助手（JobAssistant.vue）
36. WS 流式对话 UI：预埋空 assistant 气泡 → `chat.stream` 逐 token 追加 → `chat.done` 解锁
37. 多轮对话上下文由后端 checkpoint 自动恢复，前端不再传完整 history
38. 断连清理：流式回复中 WS 断开 → 删除未完成消息对 → 补 `[连接中断]` 通知
39. 非发送过程断连提示：code 1001（被其他页面顶替）时显示提示
40. 发送失败回滚：`ws.send()` 返回 `false` 时 pop 预埋消息对
41. 并发拒绝处理：后端 Agent 正忙时 `chat.busy` → 回滚 + 系统通知 + 解锁
42. system 角色消息：黄色居中样式，不与对话气泡混淆
43. token 追加健壮性：`onStream` 从后往前查找 assistant 消息
44. LLM 调用工具时前端实时显示"（正在检索简历...）"

### 环境与配置
45. 环境变量：`.env.development` / `.env.production` + `env.d.ts` 类型声明
46. WebSocket 代理：Vite 开发服务器 `ws://` 转发到后端 `/ws/chat`
47. 路由守卫：未登录 → 跳登录页 / 已登录访问登录页 → 跳主页

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
    │   ├── client.ts      # Axios（Token 自动附加 / ApiResponse 解包 / 401 跳登录）
    │   ├── health.ts      # GET /health
    │   ├── auth.ts        # POST /auth/login + GET /auth/me
    │   ├── chat.ts        # POST /chat（HTTP 备用）
    │   ├── sessions.ts    # GET /sessions（会话列表）+ GET /sessions/{id}（消息历史）
    │   └── resumes.ts     # POST /resumes/upload + GET /resumes + DELETE /resumes/{id}
    ├── router/
    │   └── index.ts       # 嵌套路由（MainLayout → 子页面）+ 全局守卫
    ├── stores/
    │   └── auth.ts        # 认证状态（token / user / login / logout / init）
    ├── layouts/
    │   └── MainLayout.vue # 毛玻璃 Header + SideNav + <router-view>
    ├── components/
    │   └── SideNav.vue    # 左侧导航栏（仪表盘/天气助手/求职助手）
    ├── views/
    │   ├── Login.vue      # 登录页
    │   ├── Home.vue       # 仪表盘（状态卡片）
    │   ├── Weather.vue    # 天气助手（HTTP 聊天对话框）
    │   └── JobAssistant.vue # 求职助手（WS 流式聊天 + 会话侧边栏 + 简历上传 + token 显示 + 断连/并发防护）
    ├── composables/
    │   └── useWebSocket.ts  # WS 单例（sessionId 持久化 + newSession + ticket 换票 + 心跳 + 重连）
    └── assets/            # 静态资源
```
