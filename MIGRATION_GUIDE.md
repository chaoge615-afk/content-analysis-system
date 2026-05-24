# 历史数据迁移执行指南

> 本文档指导 Agent 执行历史数据迁移任务
> 创建时间：2026-05-24

---

## 概述

将两个数据源的历史数据迁移到统一的知识库系统（DuckDB + ChromaDB）：

1. **Phase 1.8**：原始转写文本（56 个文件）
2. **Phase 1.9**：精炼后文本（1413 个文件）

---

## 环境准备

### 1. 确认 Python 环境

```bash
cd C:/Users/25022/Desktop/ai项目/bilibili-monitor/scripts
python --version  # 应该是 3.11+
```

### 2. 确认依赖已安装

```bash
cd C:/Users/25022/Desktop/ai项目
pip list | grep -E "(duckdb|chromadb|requests)"
```

如果缺失，安装：
```bash
pip install duckdb chromadb requests
```

### 3. 确认 API 配置

```bash
cd C:/Users/25022/Desktop/ai项目
python -c "from shared_config import config; config.print_status()"
```

应该看到：
- ✅ EMBEDDING: siliconflow - BAAI/bge-large-zh-v1.5
- ✅ CHAT: minimax - MiniMax-M2.7
- ✅ REFINE: N/A - deepseek-v4-pro

### 4. 确认数据源可访问

```bash
# 原始转写文件
ls "E:/情感素材库/" | head

# 精炼文件
ls "C:/Users/25022/Desktop/ai项目/relationship-analysis/references/情感素材库/" | head
```

---

## Phase 1.8：迁移原始转写文件

### 数据源

- **位置**：`E:/情感素材库/`（包括子目录）
- **文件数**：56 个 `.txt` 文件
- **文件名格式**：`标题 [BVxxx].txt`
- **内容**：Whisper 转写的原始文本（未精炼）

### 处理流程

```
提取 BVID → 调 B站 API → 精炼（DeepSeek V4 Pro）→ 写入 DuckDB + ChromaDB
```

### 执行步骤

#### Step 1: Dry-run 预览（不写入数据库）

```bash
cd C:/Users/25022/Desktop/ai项目/bilibili-monitor/scripts
python migrate_history.py --dry-run
```

**预期输出**：
```
============================================================
历史数据迁移: E:/情感素材库
文件数: 56
模式: DRY RUN
精炼: 启用
============================================================

扫描结果:
  有 BVID: 56
  无 BVID: 0
```

#### Step 2: 小批量测试（前 3 个文件）

修改脚本临时限制文件数，或使用 `head` 命令：

```bash
# 创建一个临时测试目录
mkdir -p /tmp/migrate_test
cp "E:/情感素材库/"*.txt /tmp/migrate_test/ 2>/dev/null || true
cp -r "E:/情感素材库/"*/ /tmp/migrate_test/ 2>/dev/null || true

# 只复制前 3 个文件
find /tmp/migrate_test -name "*.txt" | head -3 | while read f; do
    echo "测试文件: $f"
done
```

然后运行迁移（会自动处理所有文件，但可以观察前几个的行为）：

```bash
python migrate_history.py --source /tmp/migrate_test --delay 2.0
```

**观察点**：
- B站 API 是否返回元数据
- 精炼是否成功（DeepSeek 代理 10.168.165.50:3300 需要可达）
- DuckDB 写入是否成功
- ChromaDB 写入是否成功

#### Step 3: 正式迁移（全部 56 个文件）

```bash
cd C:/Users/25022/Desktop/ai项目/bilibili-monitor/scripts
python migrate_history.py --source "E:/情感素材库" --delay 1.5
```

**参数说明**：
- `--source`：数据源目录（默认 `E:/情感素材库`）
- `--delay`：B站 API 请求间隔（秒），避免限流（默认 1.0）
- `--skip-refine`：跳过精炼，直接入库原始文本（不推荐）
- `--dry-run`：只扫描不写入

**预期耗时**：
- 每个文件：~3-5 秒（B站 API 1秒 + 精炼 2-3 秒 + 入库 0.5 秒）
- 总计：约 3-5 分钟

**预期输出示例**：
```
[1/56] 不主动的女生才是最好追的 [BV1Nh5r6PEZb].txt...
  BVID: BV1Nh5r6PEZb，获取元数据...
  ✅ UP主: 某UP主, 标题: 不主动的女生才是最好追的
  精炼中...
  ✅ 精炼完成
  ✅ DuckDB 写入成功
  ✅ ChromaDB 写入成功（3 个文档）

[2/56] ...

============================================================
迁移完成:
  总文件: 56
  有 BVID: 56
  无 BVID: 0
  API 成功: 54
  API 失败: 2
  精炼成功: 54
  DuckDB: 56
  ChromaDB: 56
  跳过: 0
============================================================
```

#### Step 4: 验证迁移结果

```bash
cd C:/Users/25022/Desktop/ai项目/bilibili-monitor/scripts
python -c "
from db_writer import DBWriter
from chroma_writer import ChromaWriter

# DuckDB 统计
db = DBWriter()
count = db.get_video_count()
print(f'DuckDB 视频数: {count}')
videos = db.get_videos(limit=5)
for v in videos:
    print(f'  - {v[\"title\"][:40]} | {v[\"up_name\"]} | {v[\"bvid\"]}')
db.close()

# ChromaDB 统计
chroma = ChromaWriter()
stats = chroma.get_stats()
print(f'ChromaDB 文档数: {stats[\"total_documents\"]}')
"
```

---

## Phase 1.9：迁移精炼文件

### 数据源

- **位置**：`C:/Users/25022/Desktop/ai项目/relationship-analysis/references/情感素材库/`
- **文件数**：1413 个 `.txt` 文件（分布在 31 个分类子目录）
- **文件名格式**：`标题.txt`（约 16% 有 BVID）
- **内容**：已精炼的三段式摘要（**核心观点** + **案例摘要** + **可行动建议**）

### 处理流程

```
提取 BVID（有则提取）→ 调 B站 API（如有 BVID）→ 写入 DuckDB + ChromaDB
（内容已精炼，跳过精炼步骤）
```

### 执行步骤

#### Step 1: Dry-run 预览

```bash
cd C:/Users/25022/Desktop/ai项目/bilibili-monitor/scripts
python migrate_refined.py --dry-run
```

**预期输出**：
```
============================================================
精炼数据迁移: C:\Users\25022\Desktop\ai项目\relationship-analysis\references\情感素材库
文件数: 1413
模式: DRY RUN
范围: 全部
============================================================

扫描结果:
  有 BVID: 239 (16%)
  无 BVID: 1174 (83%)
  分类数: 31

分类分布:
  01_喜欢: 221
  02_聊天: 164
  03_撩妹: 160
  ...
  32_两性健康: 64
```

#### Step 2: 小批量测试（只处理有 BVID 的前 10 个）

```bash
python migrate_refined.py --with-bvid-only --delay 2.0
```

观察前 10 个文件的处理情况，确认：
- B站 API 调用正常
- 精炼内容正确写入 summary 字段
- ChromaDB 向量化正常

如果测试通过，按 `Ctrl+C` 中断，然后正式迁移全部文件。

#### Step 3: 正式迁移（全部 1413 个文件）

```bash
cd C:/Users/25022/Desktop/ai项目/bilibili-monitor/scripts
python migrate_refined.py --delay 0.5
```

**参数说明**：
- `--source`：数据源目录（默认 `relationship-analysis/references/情感素材库`）
- `--delay`：B站 API 请求间隔（秒），默认 0.5（因为只有 16% 有 BVID，API 调用少）
- `--with-bvid-only`：只处理有 BVID 的文件（可选）
- `--dry-run`：只扫描不写入

**预期耗时**：
- 有 BVID 的文件（239个）：~2 秒/个（API 调用）
- 无 BVID 的文件（1174个）：~0.5 秒/个（无 API 调用）
- 总计：约 15-20 分钟

**进度显示**：
```
[1/1413] 01_喜欢/3招让你喜欢的女生对你主动...

[50/1413] 02_聊天/和女生聊天的3个禁区...

--- 进度: 100/1413 | DuckDB: 98 | ChromaDB: 100 ---

[150/1413] ...

============================================================
迁移完成:
  总文件: 1413
  有 BVID: 239
  无 BVID: 1174
  API 成功: 235
  API 失败: 4
  DuckDB: 1413
  ChromaDB: 1413
  跳过: 0
============================================================
```

#### Step 4: 验证迁移结果

```bash
cd C:/Users/25022/Desktop/ai项目/bilibili-monitor/scripts
python -c "
from db_writer import DBWriter
from chroma_writer import ChromaWriter

# DuckDB 统计
db = DBWriter()
count = db.get_video_count()
print(f'DuckDB 总视频数: {count}')

# 按分类统计
result = db.conn.execute('''
    SELECT category, COUNT(*) as cnt
    FROM video_meta
    GROUP BY category
    ORDER BY cnt DESC
    LIMIT 10
''').fetchall()
print(f'\\nTop 10 分类:')
for cat, cnt in result:
    print(f'  {cat}: {cnt}')
db.close()

# ChromaDB 统计
chroma = ChromaWriter()
stats = chroma.get_stats()
print(f'\\nChromaDB 总文档数: {stats[\"total_documents\"]}')
"
```

---

## 常见问题处理

### 问题 1: B站 API 返回空或失败

**现象**：
```
⚠️ B站 API 错误: 啥都木有
```

**原因**：
- 视频已被删除
- BVID 格式错误
- API 限流

**处理**：
- 脚本会自动降级，使用文件名信息
- 如果大量失败，增加 `--delay` 参数（如 `--delay 3.0`）

### 问题 2: DeepSeek 精炼 API 连接失败

**现象**：
```
⚠️ 精炼异常: <urlopen error [WinError 10061]...>
```

**原因**：
- DeepSeek 代理 `10.168.165.50:3300` 不可达
- 代理服务未启动

**处理**：
- 确认代理服务器正在运行
- 检查网络连接：`ping 10.168.165.50`
- 如果无法解决，使用 `--skip-refine` 跳过精炼：
  ```bash
  python migrate_history.py --skip-refine
  ```

### 问题 3: ChromaDB 写入失败

**现象**：
```
❌ ChromaDB 写入失败
```

**原因**：
- Embedding API 调用失败（SiliconFlow 配额用完）
- ChromaDB 数据库损坏

**处理**：
- 检查 SiliconFlow API 配额：https://siliconflow.cn/
- 清空 ChromaDB 重试（会丢失所有数据！）：
  ```bash
  rm -rf C:/Users/25022/Desktop/ai项目/bilibili-monitor/data/chromadb
  ```

### 问题 4: 内存不足（NAS 环境）

**现象**：
```
MemoryError: ...
```

**原因**：
- 1413 个文件同时加载到内存

**处理**：
- 分批处理：先处理有 BVID 的，再处理无 BVID 的
  ```bash
  python migrate_refined.py --with-bvid-only
  python migrate_refined.py  # 剩余文件会快速处理
  ```

### 问题 5: 重复迁移（BVID 冲突）

**现象**：
- 脚本正常运行，但数据没有增加

**原因**：
- DuckDB 使用 `ON CONFLICT DO UPDATE`，相同 BVID 会覆盖
- ChromaDB 使用 `bvid_content_type_chunk` 作为 ID，会覆盖

**处理**：
- 这是预期行为，重复运行是安全的
- 如果需要保留历史版本，需要先备份数据库

---

## 迁移后验证清单

### ✅ DuckDB 数据完整性

```bash
cd C:/Users/25022/Desktop/ai项目/bilibili-monitor/scripts
python -c "
from db_writer import DBWriter
db = DBWriter()

# 总记录数
total = db.get_video_count()
print(f'✓ 总视频数: {total}')

# 有 summary 的记录数
with_summary = db.conn.execute('SELECT COUNT(*) FROM video_meta WHERE summary IS NOT NULL').fetchone()[0]
print(f'✓ 有精炼摘要: {with_summary} ({with_summary*100//total}%)')

# 有元数据的记录数
with_meta = db.conn.execute('SELECT COUNT(*) FROM video_meta WHERE up_name != \"unknown\"').fetchone()[0]
print(f'✓ 有完整元数据: {with_meta} ({with_meta*100//total}%)')

# 最近的 5 条记录
print(f'\\n最近入库:')
for v in db.get_videos(limit=5):
    print(f'  - {v[\"bvid\"]} | {v[\"title\"][:30]} | {v[\"up_name\"]}')

db.close()
"
```

**预期结果**：
- 总视频数：~1469（56 + 1413）
- 有精炼摘要：~1469（100%）
- 有完整元数据：~295（239 BVID + 56 原始）

### ✅ ChromaDB 数据完整性

```bash
cd C:/Users/25022/Desktop/ai项目/bilibili-monitor/scripts
python -c "
from chroma_writer import ChromaWriter
chroma = ChromaWriter()

stats = chroma.get_stats()
print(f'✓ Collection: {stats[\"collection\"]}')
print(f'✓ 总文档数: {stats[\"total_documents\"]}')

# 抽样查询
results = chroma.collection.query(
    query_texts=['如何追女生'],
    n_results=3
)
print(f'\\n语义检索测试（query: 如何追女生）:')
for doc in results['documents'][0]:
    print(f'  - {doc[:80]}...')
"
```

**预期结果**：
- 总文档数：~3000-5000（每个视频 1 个 summary + 多个 full_text chunks）
- 语义检索能返回相关结果

### ✅ 端到端测试

```bash
cd C:/Users/25022/Desktop/ai项目/bilibili-monitor/scripts
python -c "
from db_writer import DBWriter
db = DBWriter()

# 测试 1: 查询特定 UP 主
videos = db.get_videos(up_name='啊柚的碎碎念', limit=5)
print(f'UP主「啊柚的碎碎念」的视频数: {len(videos)}')
for v in videos:
    print(f'  - {v[\"title\"][:40]}')

# 测试 2: 查询特定分类
result = db.conn.execute('''
    SELECT bvid, title, summary
    FROM video_meta
    WHERE category = \"01_喜欢\"
    LIMIT 3
''').fetchall()
print(f'\\n分类「01_喜欢」的视频:')
for bvid, title, summary in result:
    print(f'  - {title[:40]}')
    print(f'    摘要: {summary[:60] if summary else \"无\"}...')

db.close()
"
```

---

## 执行摘要（给 Agent 的快速参考）

```bash
# 1. 环境检查
cd C:/Users/25022/Desktop/ai项目
python -c "from shared_config import config; config.print_status()"

# 2. Phase 1.8: 迁移原始文件（56个，~5分钟）
cd bilibili-monitor/scripts
python migrate_history.py --dry-run  # 预览
python migrate_history.py --delay 1.5  # 正式迁移

# 3. Phase 1.9: 迁移精炼文件（1413个，~20分钟）
python migrate_refined.py --dry-run  # 预览
python migrate_refined.py --with-bvid-only  # 先迁移有 BVID 的（测试）
python migrate_refined.py  # 迁移全部

# 4. 验证
python -c "
from db_writer import DBWriter
from chroma_writer import ChromaWriter
db = DBWriter()
chroma = ChromaWriter()
print(f'DuckDB: {db.get_video_count()} videos')
print(f'ChromaDB: {chroma.get_stats()[\"total_documents\"]} docs')
db.close()
"
```

**预期总耗时**：25-30 分钟

**成功标志**：
- DuckDB: ~1469 条视频记录
- ChromaDB: ~3000-5000 个文档
- 语义检索能返回相关结果

---

## 回滚方案

如果迁移失败或数据异常，可以清空数据库重试：

```bash
# 清空 DuckDB
rm C:/Users/25022/Desktop/ai项目/bilibili-monitor/data/content.db

# 清空 ChromaDB
rm -rf C:/Users/25022/Desktop/ai项目/bilibili-monitor/data/chromadb

# 重新运行迁移
cd C:/Users/25022/Desktop/ai项目/bilibili-monitor/scripts
python migrate_history.py
python migrate_refined.py
```

**注意**：这会丢失所有已迁移的数据，请谨慎操作！

---

## 附录：数据结构说明

### DuckDB video_meta 表

| 字段 | 类型 | 说明 |
|------|------|------|
| bvid | TEXT (PK) | B站视频 ID（如 BV1xxx） |
| up_name | TEXT | UP 主名称 |
| up_uid | TEXT | UP 主 UID |
| title | TEXT | 视频标题 |
| publish_date | DATE | 发布日期 |
| category | TEXT | 分类（B站分类或情感分类） |
| duration | INT | 视频时长（秒） |
| summary | TEXT | 精炼摘要（三段式） |
| tags | TEXT | 标签 |
| created_at | TIMESTAMP | 入库时间 |

### ChromaDB video_knowledge collection

**Metadata 字段**：
- `bvid`: 视频 ID
- `up_name`: UP 主名称
- `title`: 视频标题
- `category`: 分类
- `publish_date`: 发布日期
- `content_type`: "full"（转写全文）或 "summary"（精炼摘要）
- `chunk_index`: 分块序号
- `source`: "bilibili"

**Document ID 格式**：`{bvid}_{content_type}_{chunk_index}`

---

**文档版本**：v1.0  
**最后更新**：2026-05-24  
**维护者**：智能内容分析系统开发团队
