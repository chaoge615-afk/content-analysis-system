# Text-to-SQL 后端 Dockerfile
# 前端使用 frontend/Dockerfile，由根目录 docker-compose.yml 统一编排

FROM python:3.11-slim

WORKDIR /app

# 安装 curl 用于 healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 使用阿里云镜像加速 pip
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
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
