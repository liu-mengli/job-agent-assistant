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
| `vite.config.ts` | Vite 配置（含 API + WebSocket 代理） |

## 已完成工作

### 基础设施
1. 用 Vite 创建 Vue 3 + TypeScript 项目骨架
2. 安装并配置 Vue Router，嵌套路由 + 全局守卫
3. 安装并注册 Pinia，`stores/auth.ts` 管理认证 + 用户信息

### 认证与 HTTP 层
4. 封装 Axios（baseURL、超时、Token 自动附加、401 自动跳登录）
5. 响应拦截器对接后端 `ApiResponse` 统一格式（`{ code, data, message }`）
6. 登录页面（`Login.vue`）：Element Plus 苹果风格白卡片
7. JWT Token 管理：登录存 sessionStorage，刷新自动恢复，退出清除

### 布局与导航
8. Apple 风格整体布局：毛玻璃 Header + 侧边导航 + 内容区
9. `MainLayout.vue`：布局框架，Header 含用户信息 + 退出
10. `SideNav.vue`：左侧导航栏（仪表盘 / 天气助手 / 求职助手）
11. 仪表盘（`Home.vue`）：系统状态卡片（后端状态、用户、模块）
12. 天气助手（`Weather.vue`）：HTTP 聊天对话框，气泡消息，多轮对话
13. 全局样式：Apple 系统字体栈（SF Pro / PingFang SC），毛玻璃效果

### WebSocket 通信层
14. `useWebSocket` composable：模块级单例，所有组件共享同一连接
15. WS 生命周期管理：`App.vue` 监听 authStore.token 自动 connect / disconnect
16. 心跳保活：30 秒间隔自动发 `ping`，非主动断开 5 秒自动重连
17. 事件注册/注销：`on(type, handler)` / `off(type, handler)`，持久化在模块级 handlers Map 中
18. 断连回调：`onClose` / `offClose`，WS 断开时通知页面清理未完成的消息
19. 发送保护：`send()` 返回 `boolean`，WS 未连通时拒绝发送并回滚 UI

### 求职助手（JobAssistant.vue）
20. WS 流式对话 UI：发送前预埋空 assistant 气泡 → 接收 `chat.stream` 逐 token 追加填充 → `chat.done` 解锁输入
21. 多轮对话上下文：构建 history 时过滤 `system` 消息，只传 `user` + `assistant` 给后端
22. 断连清理：当前正在流式回复时 WS 断开 → 删除未完成的消息对（用户提问 + 半截回复）→ 推送 `[连接中断]` system 通知
23. 发送失败回滚：`ws.send()` 返回 `false` 时 pop 掉预埋的消息对，显示「连接已断开」提示
24. system 角色消息：系统通知（错误/断连提示）使用 `role: 'system'` + 黄色居中样式，不与对话气泡混淆
25. 逐 token 追加时从后往前查找 assistant 消息（`onStream`），system 通知插入不影响 token 填充

### 环境与配置
26. 环境变量：`.env.development` / `.env.production` + `env.d.ts` 类型声明
27. WebSocket 代理：Vite 开发服务器 `ws://` 转发到后端 `/ws/chat`

## 文件结构

```
frontend/job-agent-assistant-frontend/
├── .env.development       # 开发环境变量
├── .env.production        # 生产环境变量
├── .env.example           # 环境变量模板
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts         # Vite 配置（含 API + WS 代理）
└── src/
    ├── main.ts            # 入口，注册 Pinia + Router + Element Plus
    ├── App.vue            # 根组件（<router-view /> + WS 生命周期）
    ├── style.css          # 全局样式（Apple 字体栈）
    ├── env.d.ts           # 环境变量类型声明
    ├── api/
    │   ├── client.ts      # Axios（Token 自动附加 / 401 跳登录）
    │   ├── health.ts      # GET /health
    │   ├── auth.ts        # POST /auth/login + GET /auth/me
    │   └── chat.ts        # POST /chat（多轮对话历史，HTTP 备用）
    ├── router/
    │   └── index.ts       # 嵌套路由（MainLayout → 子页面）
    ├── stores/
    │   └── auth.ts        # 认证状态（token / user / login / logout / init）
    ├── layouts/
    │   └── MainLayout.vue # 毛玻璃 Header + SideNav + <router-view>
    ├── components/
    │   └── SideNav.vue    # 左侧导航栏
    ├── views/
    │   ├── Login.vue      # 登录页
    │   ├── Home.vue       # 仪表盘（状态卡片）
    │   ├── Weather.vue    # 天气助手（HTTP 聊天对话框）
    │   └── JobAssistant.vue # 求职助手（WS 流式聊天，逐 token 显示）
    ├── composables/
    │   └── useWebSocket.ts  # WebSocket 单例（心跳、重连、事件注册、断连回调）
    └── assets/            # 静态资源
```
