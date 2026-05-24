# 个人知识库RAG - Docker 构建文件
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY rag_engine.py .
COPY api.py .
COPY main.py .
COPY load_cli.py .
COPY templates/ ./templates/

# 创建空数据目录（供运行时挂载）
RUN mkdir -p /app/knowledge /app/chroma_db /app/logs

# 暴露端口
EXPOSE 8090

# 环境变量（容器内运行时可通过 -e 覆盖）
ENV KNOWLEDGE_DIR=/app/knowledge
ENV CHROMA_PERSIST_DIR=/app/chroma_db
ENV PORT=8090

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8090/api/stats || exit 1

# 启动命令
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8090"]