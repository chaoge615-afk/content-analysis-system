# 前端 Dockerfile（多阶段构建）
# 阶段1: 构建
FROM node:18-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --registry=https://registry.npmmirror.com

COPY . .
RUN npm run build

# 阶段2: Nginx 服务
FROM nginx:alpine

# 复制构建产物
COPY --from=build /app/dist /usr/share/nginx/html

# 复制 nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
