# 视频知识库RAG - Docker 构建文件
# 构建上下文: 根目录（需要访问 shared_config.py 和 shared_embeddings.py）
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 使用国内 Debian 镜像加速 apt 安装
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null; \
    sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null; \
    true

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制共享模块（根目录）
COPY shared_config.py shared_embeddings.py ./

# 复制 RAG 项目依赖文件
COPY personal-knowledge-rag/requirements.txt .

# 安装 Python 依赖（使用清华 pip 镜像加速）
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple/ \
    --trusted-host pypi.tuna.tsinghua.edu.cn \
    -r requirements.txt

# 复制 RAG 项目代码
COPY personal-knowledge-rag/rag_engine.py .
COPY personal-knowledge-rag/hybrid_search.py .
COPY personal-knowledge-rag/api.py .
COPY personal-knowledge-rag/main.py .
COPY personal-knowledge-rag/load_cli.py .
COPY personal-knowledge-rag/templates/ ./templates/

# 创建空数据目录（供运行时挂载）
RUN mkdir -p /app/video_knowledge /app/chroma_db /app/logs

# 暴露端口
EXPOSE 8090

# 环境变量（容器内运行时可通过 -e 覆盖）
ENV VIDEO_KNOWLEDGE_DIR=/app/video_knowledge
ENV CHROMA_PERSIST_DIR=/app/chroma_db
ENV PORT=8090

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8090/api/stats || exit 1

# 启动命令
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8090"]
