# Router Agent - Docker 构建文件
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY api.py .
COPY src/ ./src/

# 暴露端口
EXPOSE 8000

# 环境变量
ENV ROUTER_PORT=8000
ENV ROUTER_HOST=0.0.0.0

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 启动
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
