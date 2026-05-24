# Text-to-SQL 后端 Dockerfile
# 前端使用 frontend/Dockerfile，由根目录 docker-compose.yml 统一编排

FROM python:3.11-slim

WORKDIR /app

# 使用国内 Debian 镜像加速 apt 安装
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null; \
    sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null; \
    true

# 安装 curl 用于 healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 使用清华镜像加速 pip
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple/ \
    --trusted-host pypi.tuna.tsinghua.edu.cn \
    -r requirements.txt

# 复制后端代码
COPY src/ ./src/

# 创建数据目录（实际数据库通过 volume 挂载）
RUN mkdir -p /app/data

# 环境变量
ENV PYTHONPATH=/app

EXPOSE 8010

# 启动 API 服务
CMD ["python", "-m", "uvicorn", "src.api_server:app", "--host", "0.0.0.0", "--port", "8010"]
