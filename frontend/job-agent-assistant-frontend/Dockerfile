FROM node:20-alpine AS builder
WORKDIR /app

# 国内 npm 镜像（构建时通过 --build-arg 传入）
ARG NPM_MIRROR=""
ARG VITE_API_BASE_URL=/api/v1
ARG VITE_WS_BASE_URL=ws://localhost/api/v1
ARG VITE_APP_TITLE=AI 找工作助手

ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_WS_BASE_URL=$VITE_WS_BASE_URL
ENV VITE_APP_TITLE=$VITE_APP_TITLE

COPY package.json package-lock.json ./
RUN if [ -n "$NPM_MIRROR" ]; then npm config set registry "$NPM_MIRROR"; fi && npm ci

COPY . .
RUN npx vite build

FROM nginx:alpine

RUN rm /etc/nginx/conf.d/default.conf
COPY nginx/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
