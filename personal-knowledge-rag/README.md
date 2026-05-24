# 个人知识库RAG问答系统

把你所有的markdown笔记做成可问答的知识库，随时提问找内容，不用自己翻文件。

## 功能特性

- 本地纯Python运行，数据存在自己电脑，隐私安全
- 自动加载 `knowledge/` 目录下所有markdown文件
- 基于 Minimax API，性价比高，国内直接调用不翻墙
- 使用 ChromaDB 做向量存储，无需额外部署服务
- 自定义适配 SiliconFlow Embedding 接口
- 支持 Web UI 和 API 两种交互方式
- 支持 Docker 部署，便于迁移

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置API Key

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的 API Key:

```
DASHSCOPE_API_KEY=你的-minimax-api-key
MINIMAX_GROUP_ID=你的-group-id
SILICONFLOW_API_KEY=你的-siliconflow-api-key
```

### 3. 添加你的知识库

把你的markdown文件放到 `knowledge/` 目录下，支持子目录。

### 4. 运行

```bash
# Web UI 方式（推荐）
python api.py
# 访问 http://localhost:8090

# 命令行方式
python main.py
```

### 5. 加载知识库

**Web UI**: 点击页面上的「📥 加载知识库」按钮

**命令行**: 输入 `load`

**CLI脚本**:
```bash
python load_cli.py                    # 加载知识库
python load_cli.py --stats            # 查看统计信息
python load_cli.py --clear            # 清空并重新加载
python load_cli.py --help             # 查看帮助
```

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | Web UI 页面 |
| `/api/ask` | POST | 提问，参数: `{"question": "问题"}` |
| `/api/load` | POST | 加载知识库 |
| `/api/clear` | POST | 清空知识库 |
| `/api/stats` | GET | 获取统计信息 |

## 使用说明

### 常用命令（命令行模式）

| 命令 | 作用 |
|------|------|
| `load` | 重新加载所有markdown文件更新索引 |
| `clear` | 清空知识库索引 |
| `stats` | 查看知识库统计信息 |
| `help` | 显示帮助 |
| `exit` | 退出 |

### 调优参数

在 `.env` 文件中可以调整：

```
# 分块大小，根据你的文档长度调整
CHUNK_SIZE=500
# 重叠大小，避免内容被从中间切开丢失上下文
CHUNK_OVERLAP=50
# 检索数量
TOP_K=5
```

如果发现回答找不到正确内容：
- 如果文档都比较长，可以试试 `CHUNK_SIZE=1000`
- 如果切分得不对，可以调大 `CHUNK_OVERLAP` 到 100

## Docker 部署

### 方式一：docker run

```bash
# 构建镜像
docker build -t personal-knowledge-rag .

# 运行容器
docker run -d -p 8090:8090 \
  -e DASHSCOPE_API_KEY=your_key \
  -e MINIMAX_GROUP_ID=your_group_id \
  -e SILICONFLOW_API_KEY=your_siliconflow_key \
  -v ./knowledge:/app/knowledge \
  -v ./chroma_db:/app/chroma_db \
  -v ./logs:/app/logs \
  personal-knowledge-rag
```

### 方式二：docker-compose（推荐）

```bash
# 复制环境变量配置
cp .env.example .env
# 编辑 .env 填入你的 API Key

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

## 项目结构

```
personal-knowledge-rag/
├── main.py              # 交互式命令行入口
├── api.py               # FastAPI Web服务入口
├── rag_engine.py        # RAG核心引擎
├── load_cli.py          # 命令行加载工具
├── templates/
│   └── index.html       # Web UI页面
├── requirements.txt     # 依赖列表
├── .env.example         # 环境变量示例
├── Dockerfile          # Docker构建文件
├── docker-compose.yml   # Docker Compose配置
├── knowledge/           # 你的markdown知识库放这里
├── chroma_db/           # 向量数据库持久化存储（自动生成）
└── logs/                # 日志目录（自动生成）
```

## 技术栈

- **LangChain**: RAG框架
- **ChromaDB**: 本地向量数据库
- **FastAPI**: Web服务
- **Minimax**: 大语言模型
- **SiliconFlow**: Embedding服务
- **OpenAI SDK**: 兼容 Minimax API 接口

## 成本说明

Minimax 价格非常便宜：
- 输入: 约 0.1-0.3 元/百万tokens
- 输出: 约 0.3-0.6 元/百万tokens
- Embedding: 约 0.02 元/百万tokens

100篇markdown文章，大概也就几分钱成本。