# 多阶段：Node 构建（含 ECharts）+ Nginx 运行
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json ./
RUN npm install --registry https://registry.npmmirror.com

COPY . .
RUN npm run build

# 运行阶段：Nginx 托管静态资源并代理 /api
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
