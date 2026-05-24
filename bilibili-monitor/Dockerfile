# bilibili-monitor Dockerfile
# 构建上下文: 根目录（需要访问 shared_config.py 和 shared_embeddings.py）
FROM python:3.11-slim

# 使用国内 Debian 镜像加速 apt 安装
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null; \
    sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null; \
    true

# 安装系统依赖
RUN apt-get update && apt-get install -y --fix-missing \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制共享模块（根目录）
COPY shared_config.py shared_embeddings.py ./

# 复制依赖文件
COPY bilibili-monitor/requirements.txt .

# 安装 Python 依赖（使用阿里云 pip 镜像加速）
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    -r requirements.txt

# 复制项目文件
COPY bilibili-monitor/scripts/ ./scripts/
COPY bilibili-monitor/config/ ./config/

# 创建必要目录
RUN mkdir -p downloads transcripts data chromadb

# 默认环境变量
ENV PYTHONUNBUFFERED=1
ENV WHISPER_DEVICE=cpu
ENV WHISPER_MODEL=small
ENV COMPUTE_TYPE=int8

# 批量任务容器，无需 HEALTHCHECK（运行完成即退出）

# 默认命令
CMD ["python", "scripts/monitor_all.py"]
