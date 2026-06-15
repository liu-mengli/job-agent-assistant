# Job Agent Assistant — 前端

## 技术栈

| 技术 | 用途 |
|---|---|
| Vue 3 | UI 框架（Composition API + `<script setup>`） |
| TypeScript | 类型安全 |
| Vite | 构建工具 + 开发服务器 |
| Vue Router | 前端路由 |
| Pinia | 状态管理 |
| Axios | HTTP 请求 |
| Element Plus | UI 组件库 |

## 新增的包

| 包 | 用途 |
|---|---|
| vue-router | 前端路由管理 + 全局守卫 |
| pinia | 全局状态管理（认证状态） |
| axios | HTTP 客户端，封装了请求/响应拦截器 |
| element-plus | UI 组件库（表单、按钮、消息提示等） |

## 配置文件

| 文件 | 用途 |
|---|---|
| `.env.development` | 开发环境变量（API 走 Vite 代理） |
| `.env.production` | 生产环境变量（直连后端） |
| `.env.example` | 环境变量模板 |
| `vite.config.ts` | Vite 配置（含 API 代理 `/api` → `localhost:8000`） |

## 已完成工作

1. 用 Vite 创建 Vue 3 + TypeScript 项目骨架
2. 安装并配置 Vue Router，创建首页路由 `/` 和登录路由 `/login`
3. 路由全局守卫：未登录自动跳转 `/login`
4. 安装并注册 Pinia 状态管理，`stores/auth.ts` 管理认证状态
5. 封装 Axios 实例（`src/api/client.ts`），配置 baseURL、超时、请求/响应拦截器
6. 响应拦截器对接后端 `ApiResponse` 统一格式，`code !== 0` 自动抛异常
7. 编写健康检查 API 调用（`src/api/health.ts`）
8. 编写登录 API 调用（`src/api/auth.ts`），对接后端 `POST /api/v1/auth/login`
9. 创建首页视图（`src/views/Home.vue`），自动检测后端连通性，含退出登录按钮
10. 创建登录页面（`src/views/Login.vue`），Element Plus 苹果风格白卡片设计
11. 登录成功后 JWT Token 存入 sessionStorage，拉取用户信息（调用 `/auth/me`）存入 Pinia
12. 请求拦截器自动附加 `Authorization: Bearer <token>` 请求头
13. 响应拦截器 401 时自动清除 Token 并跳转登录页
14. 页面刷新自动从 sessionStorage 恢复 Token → 调 `/auth/me` 恢复用户信息
15. 首页显示当前用户名（`authStore.user.username`）
16. 配置 Vite 开发代理，`/api` 请求转发到 `http://localhost:8000`
17. 环境变量配置：`.env.development` / `.env.production` + `env.d.ts` 类型声明
18. 清理 `App.vue`，仅保留 `<router-view />`
19. 安装并注册 Element Plus 组件库
20. WebSocket 双向通信：`useWebSocket` composable，Token 握手认证、自动心跳、断线重连
21. `App.vue` 监听 `authStore.token` 变化，登录/刷新自动连接 WS，退出自动断开

## 文件结构

```
frontend/job-agent-assistant-frontend/
├── .env.development       # 开发环境变量
├── .env.production        # 生产环境变量
├── .env.example           # 环境变量模板
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts         # Vite 配置（含 API 代理）
└── src/
    ├── main.ts            # 入口，注册 Pinia + Router + Element Plus，启动时恢复登录态
    ├── App.vue            # 根组件（<router-view /> + WS 生命周期管理）
    ├── style.css          # 全局样式
    ├── env.d.ts           # 环境变量类型声明
    ├── api/
    │   ├── client.ts      # Axios 实例（请求拦截器自动带 Token，401 自动跳登录）
    │   ├── health.ts      # GET /health 健康检查
    │   └── auth.ts        # POST /auth/login + GET /auth/me（WS 环境变量已配置）
    ├── router/
    │   └── index.ts       # Vue Router（路由配置 + beforeEach 守卫）
    ├── stores/
    │   └── auth.ts        # 认证状态（token / user / login / logout / init）
    ├── views/
    │   ├── Login.vue      # 登录页
    │   └── Home.vue       # 首页（显示欢迎用户）
    ├── composables/
    │   └── useWebSocket.ts  # WebSocket 封装（连接/收发/心跳/重连）
    ├── components/        # 公共组件
    └── assets/            # 静态资源
```
