FROM python:3.11-slim

WORKDIR /app

# Install Node.js for frontend
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    gnupg \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Configure apt sources to use Tsinghua mirror
RUN echo 'deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm main contrib non-free' > /etc/apt/sources.list && \
    echo 'deb https://mirrors.tuna.tsinghua.edu.cn/debian-security/ bookworm-security main contrib non-free' >> /etc/apt/sources.list && \
    echo 'deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm-updates main contrib non-free' >> /etc/apt/sources.list

# Copy requirements first for caching
COPY requirements.txt .
# Use Tsinghua mirror for pip
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt || \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY data/ ./data/
COPY frontend/ ./frontend/

# Install frontend dependencies
WORKDIR /app/frontend
RUN npm install

WORKDIR /app

# Create data directory if it doesn't exist
RUN mkdir -p /app/data

# Set environment variables
ENV PYTHONPATH=/app
ENV DATABASE_PATH=/app/data/nutrition.db

# Initialize database
RUN python -c "from src.database.duckdb_utils import init_database; init_database()"

# Expose ports
EXPOSE 8010 3000

# Start both services using a script
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

CMD ["/app/start.sh"]
