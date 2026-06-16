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

1. 用 Vite 创建 Vue 3 + TypeScript 项目骨架
2. 安装并配置 Vue Router，嵌套路由 + 全局守卫
3. 安装并注册 Pinia，`stores/auth.ts` 管理认证 + 用户信息
4. 封装 Axios（baseURL、超时、Token 自动附加、401 自动跳登录）
5. 响应拦截器对接后端 `ApiResponse` 统一格式
6. 登录页面（`Login.vue`）：Element Plus 苹果风格白卡片
7. JWT Token 管理：登录存 sessionStorage，刷新自动恢复，退出清除
8. Apple 风格整体布局：毛玻璃 Header + 侧边导航 + 内容区
9. `MainLayout.vue`：布局框架，Header 含用户信息 + 退出
10. `SideNav.vue`：左侧导航栏（仪表盘 / 天气助手）
11. 仪表盘（`Home.vue`）：系统状态卡片（后端状态、用户、模块）
12. 天气助手（`Weather.vue`）：聊天对话框，气泡消息，多轮对话
13. WebSocket：`useWebSocket` composable，Token 握手、心跳、断线重连
14. `App.vue` 监听 authStore 自动管理 WS 连接生命周期
15. 环境变量：`.env.development` / `.env.production` + `env.d.ts`
16. 全局样式：Apple 系统字体栈，SF Pro / PingFang SC

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
    │   └── chat.ts        # POST /chat（多轮对话历史）
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
    │   └── Weather.vue    # 天气助手（聊天对话框）
    ├── composables/
    │   └── useWebSocket.ts  # WebSocket 封装
    └── assets/            # 静态资源
```
