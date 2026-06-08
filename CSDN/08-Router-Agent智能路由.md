## 系列文章目录

[B站视频内容智能分析系统（一）：项目介绍与架构设计](./01-项目介绍与架构设计.md)
[B站视频内容智能分析系统（二）：Docker Compose 一键部署](./02-Docker-Compose一键部署.md)
[B站视频内容智能分析系统（三）：B站视频自动采集](./03-B站视频自动采集.md)
[B站视频内容智能分析系统（四）：语音转写三级回退](./04-语音转写三级回退.md)
[B站视频内容智能分析系统（五）：LLM 内容精炼与多域分类](./05-LLM内容精炼与分类.md)
[B站视频内容智能分析系统（六）：Text-to-SQL 结构化查询](./06-Text-to-SQL结构化查询.md)
[B站视频内容智能分析系统（七）：RAG 语义检索](./07-RAG语义检索.md)
B站视频内容智能分析系统（八）：Router Agent 智能路由


### 文章目录

+ [系列文章目录](#_0)
+ [前言](#前言)
+ [一、Router Agent 的角色](#一router-agent-的角色)
+ [二、统一入口 /api/chat](#二统一入口-apichat)
+ [三、意图分类](#三意图分类)
    + [1. 三种路由类型](#1-三种路由类型)
    + [2. 分类 Prompt 设计](#2-分类-prompt-设计)
    + [3. Prompt Caching 省钱](#3-prompt-caching-省钱)
+ [四、查询分发](#四查询分发)
    + [1. structured → Text-to-SQL](#1-structured--text-to-sql)
    + [2. semantic → RAG](#2-semantic--rag)
    + [3. hybrid → 并行调用](#3-hybrid--并行调用)
+ [五、Hybrid 结果融合](#五hybrid-结果融合)
    + [1. 融合 Prompt](#1-融合-prompt)
    + [2. 智能降级](#2-智能降级)
+ [六、强制路由](#六强制路由)
+ [七、分类器的坑与修复](#七分类器的坑与修复)
    + [1. category 幻觉问题](#1-category-幻觉问题)
    + [2. up_name 简称不标准化](#2-up_name-简称不标准化)
+ [八、完整查询流程](#八完整查询流程)
+ [总结](#总结)




## 前言

前面两篇分别讲了 Text-to-SQL（结构化查询）和 RAG（语义检索）。但用户提问的时候不会告诉你"我要走 SQL"还是"我要走 RAG"——他们只会问"桃姐最近聊了什么"。

Router Agent 就是那个帮你做选择的人。它接收用户的自然语言问题，判断应该走哪个通道，分发查询，最后把结果返回。如果是混合查询，还要并行调用两个通道并用 LLM 融合结果。

这篇把 Router Agent 拆开来看——意图分类怎么做、查询怎么分发、Hybrid 模式怎么融合、以及开发过程中踩过的坑。


## 一、Router Agent 的角色

Router Agent 是整个系统的**统一入口**。所有用户请求都先到它这里，再由它决定分发给谁：

```
用户提问
    ↓
Router Agent (:8000)
    ├── 意图分类（MiniMax M2.7）
    ├── UP主名称标准化
    ├── 查询分发
    │     ├── structured → Text-to-SQL (:8010)
    │     ├── semantic   → RAG (:8090)
    │     └── hybrid     → 两者并行
    ├── 结果融合（hybrid 模式）
    └── 返回最终回答
```

除了核心问答，Router Agent 还负责：
- 采集触发（通过 Docker SDK 启动 bilibili-monitor）
- UP主管理（添加/删除/列表）
- ASR 转写管理（开关/预算/手动触发）
- 查询日志记录
- 系统监控指标

但这些都是辅助功能，核心还是意图分类 + 查询分发。


## 二、统一入口 /api/chat

所有问答请求都走同一个接口：

```python
@app.post("/api/chat")
async def chat(req: ChatRequest):
    """统一问答入口"""
    start_time = time.time()

    # Step 1: 意图分类
    if req.force_route:
        intent = {"route_type": req.force_route, "filters": {}}
    else:
        intent = classifier.classify(question)

    route_type = intent["route_type"]
    filters = intent.get("filters", {})

    # Step 2: 分发查询
    if route_type == "structured":
        sql_result = dispatcher.query_sql(question, filters, intent)
        return ChatResponse(answer=sql_result["answer"], route_type="structured", ...)

    elif route_type == "semantic":
        rag_result = dispatcher.query_rag(question, filters)
        return ChatResponse(answer=rag_result["answer"], route_type="semantic", ...)

    else:  # hybrid
        # 并行调用 SQL + RAG
        with ThreadPoolExecutor(max_workers=2) as executor:
            sql_future = executor.submit(dispatcher.query_sql, question, filters, intent)
            rag_future = executor.submit(dispatcher.query_rag, question, filters)
            sql_result = sql_future.result()
            rag_result = rag_future.result()

        # LLM 融合
        answer = merger.merge(question, sql_result, rag_result)
        return ChatResponse(answer=answer, route_type="hybrid", ...)
```

请求体：

```json
{
    "question": "桃姐最近聊了什么？她关于吵架的建议？",
    "force_route": null,
    "domain": null
}
```

响应体：

```json
{
    "answer": "桃姐最近发布了3个视频...",
    "route_type": "hybrid",
    "sql": "SELECT title, publish_date FROM video_meta WHERE up_name = '恋爱教头桃姐'...",
    "sql_result": [["吵架后怎么和好", "2026-05-28"], ...],
    "sources": [{"bvid": "BV1xxx", "up_name": "恋爱教头桃姐", ...}],
    "reasoning": "需要找桃姐的视频（结构化）+ 理解她关于吵架的建议（语义）",
    "response_time": 5.2
}
```

前端拿到这些数据后，可以同时展示自然语言回答、SQL 语句、查询结果表格和来源引用。


## 三、意图分类

### 1. 三种路由类型

IntentClassifier 把用户问题分成三类：

| 类型 | 走哪个通道 | 典型问题 |
|------|-----------|---------|
| **structured** | Text-to-SQL | "桃姐有几个视频？"、"各分类有多少视频？" |
| **semantic** | RAG | "博主们对冷暴力怎么看？"、"怎么改善沟通？" |
| **hybrid** | 两者并行 | "桃姐最近聊了什么？她关于吵架的建议？" |

判断逻辑很直观：
- 涉及数量、统计、排序、列表 → structured
- 涉及观点、建议、内容理解 → semantic
- 两者都有 → hybrid

### 2. 分类 Prompt 设计

分类器用的是 MiniMax M2.7，Prompt 里详细定义了三类的判断规则和示例：

```python
INTENT_CLASSIFY_PROMPT = """你是一个智能意图分类器。

## 分类规则

### structured（结构化查询）→ 走 Text-to-SQL
- 视频数量统计（"桃姐有几个视频？"）
- UP 主信息（"有哪些 UP 主？"）
- 视频列表（"最近发布了什么视频？"）
- 分类统计（"各分类有多少视频？"）

### semantic（语义查询）→ 走 RAG
- 观点/建议查询（"博主们对冷暴力怎么看？"）
- 情感/关系建议（"怎么改善沟通？"）
- 知识内容查询（"关于吵架有什么好的建议？"）

### hybrid（混合查询）→ 两者并行
- "桃姐最近聊了什么？她关于吵架的建议？"
- "最近一周有什么关于沟通的新内容？"

## 过滤条件提取
从问题中提取：
- up_name: UP主名称（需标准化为全名）
- category: 视频分类（只能从 31 个有效分类中选择）
- date_range: 时间范围
- keywords: 话题关键词

**重要：category 是目录分类名，不是话题关键词。
"冷暴力"是话题（用 keywords），不是分类。**
"""
```

Prompt 里给了 5 个 few-shot 示例，覆盖各种情况：

```python
## 示例

用户："桃姐最近发了几个视频？"
{"route_type": "structured", "filters": {"up_name": "恋爱教头桃姐", "date_range": "最近"}}

用户："博主们对冷暴力怎么看？"
{"route_type": "semantic", "filters": {"keywords": "冷暴力"}}

用户："桃姐关于吵架有什么建议？"
{"route_type": "hybrid", "filters": {"up_name": "恋爱教头桃姐", "keywords": "吵架"}}

用户："喜欢分类下有什么内容？"
{"route_type": "semantic", "filters": {"category": "01_喜欢"}}

用户："一共有多少个视频？"
{"route_type": "structured", "filters": {}}
```

### 3. Prompt Caching 省钱

分类 Prompt 很长（包含了所有 UP主名称列表 + 31 个分类 + 5 个示例），每次调用都传一遍很费 token。好在 MiniMax 的 Anthropic 兼容接口支持 Prompt Caching：

```python
response = self.client.messages.create(
    model=self.model,
    system=[
        {
            "type": "text",
            "text": INTENT_CLASSIFY_PROMPT,
            "cache_control": {"type": "ephemeral"},  # 缓存这个 block
        },
        {
            "type": "text",
            "text": f"## 已知UP主完整名称列表\n{up_names_text}",
            # 这个 block 不缓存（UP主列表可能变化）
        }
    ],
    messages=[{"role": "user", "content": question}],
)
```

把静态的分类规则和示例标记为 `cache_control: ephemeral`，MiniMax 会缓存这部分。后续请求只需要传动态部分（UP主列表 + 用户问题），API 费用降低约 90%。

Anthropic 官方的 Prompt Caching 有 5 分钟 TTL，MiniMax 的兼容接口行为类似。


## 四、查询分发

### 1. structured → Text-to-SQL

```python
def query_sql(self, question, filters=None, intent=None):
    # 将标准化的 UP主名称注入问题文本
    enhanced_question = question
    if filters and filters.get("up_name"):
        enhanced_question = f"{question}（UP主完整名称是：{filters['up_name']}）"

    # 带上 Router 的预分类意图，让 T2S 跳过 IntentAgent
    payload = {"question": enhanced_question}
    if intent:
        payload["pre_intent"] = intent

    resp = requests.post(f"{self.sql_url}/query", json=payload, timeout=self.timeout)
    return resp.json()
```

两个优化：
- **注入 UP主全名**：把"恋爱教头桃姐"直接塞到问题里，T2S 的 SQL 生成更准确
- **传递 pre_intent**：Router 已经做了意图分类，T2S 可以跳过自己的 IntentAgent，省一次 LLM 调用

### 2. semantic → RAG

```python
def query_rag(self, question, filters=None, use_hybrid=True):
    payload = {
        "question": question,
        "filters": filters or {},
        "use_hybrid": use_hybrid,
    }
    resp = requests.post(f"{self.rag_url}/api/ask_video", json=payload, timeout=self.timeout)
    return resp.json()
```

直接把过滤条件（up_name、category、keywords）传给 RAG，RAG 内部做 metadata 过滤 + 混合检索。

### 3. hybrid → 并行调用

Hybrid 模式下，SQL 和 RAG 同时调用，用 `ThreadPoolExecutor` 并行：

```python
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
    sql_future = executor.submit(dispatcher.query_sql, question, filters, intent)
    rag_future = executor.submit(dispatcher.query_rag, question, filters)

    sql_result = sql_future.result()  # 等待 SQL 完成
    rag_result = rag_future.result()  # 等待 RAG 完成
```

并行调用让 Hybrid 模式的响应时间约等于 max(SQL 耗时, RAG 耗时)，而不是两者之和。


## 五、Hybrid 结果融合

### 1. 融合 Prompt

Hybrid 模式的最后一步是用 LLM 把 SQL 结果和 RAG 结果融合成一个回答：

```python
MERGE_SYSTEM = """你是一个智能问答助手。你将收到两个来源的信息：
一个来自数据库查询的结构化结果，一个来自知识库的语义检索结果。
请综合这两个来源，给出一个完整、准确、自然的回答。

## 规则
1. 如果两个来源都有相关信息，综合起来回答
2. 如果数据库查询返回了空结果，但知识库有相关内容
   → 直接使用知识库内容回答
3. 如果知识库也没有内容，但数据库有结果
   → 使用数据库结果回答
4. 如果两个来源都没有相关信息，如实告知用户
5. 不要编造信息"""

MERGE_USER = """## 用户问题
{question}

## 数据库查询结果（结构化数据）
{sql_result}

## 知识库检索结果（语义内容）
{rag_result}

## 请综合回答："""
```

融合 Prompt 也用了 Prompt Caching（`cache_control: ephemeral`），因为系统指令是静态的。

### 2. 智能降级

融合不是简单的拼接，而是有多种降级策略：

```python
def merge(self, question, sql_result, rag_result):
    # 两个都失败了
    if not sql_result.get("success") and rag_result.get("error"):
        return f"查询遇到问题：数据库和知识库均不可用"

    # 只有 SQL 有结果
    if sql_result.get("success") and not rag_result.get("answer"):
        return sql_result.get("answer")

    # 只有 RAG 有结果
    if not sql_result.get("success") and rag_result.get("answer"):
        return rag_result["answer"]

    # SQL 成功但返回空结果，RAG 有内容
    if sql_result.get("success") and not sql_result.get("result") and rag_result.get("answer"):
        return f"数据库中暂未找到匹配的结构化数据。以下是知识库中的相关内容：\n\n{rag_result['answer']}"

    # 两个都有结果 → LLM 融合
    return self._llm_merge(question, sql_result, rag_result)
```

最有意思的是第四个条件——SQL 查询成功但结果为空（比如"桃姐关于出轨有什么建议"，SQL 用关键词搜不到任何标题包含"出轨"的视频），这时候直接用 RAG 的结果，不浪费一次 LLM 融合调用。


## 六、强制路由

有时候用户明确知道要走哪个通道，可以用 `force_route` 跳过意图分类：

```python
class ChatRequest(BaseModel):
    question: str
    force_route: Optional[str] = None  # "sql" | "rag" | None
```

前端通过斜杠命令实现强制路由：

```
/sql 各分类视频数量     → force_route="sql"
/rag 关于分手的建议     → force_route="rag"
```

```python
if req.force_route:
    intent = {
        "route_type": req.force_route,
        "filters": {},
        "reasoning": f"强制路由到 {req.force_route}",
    }
else:
    intent = classifier.classify(question)
```

强制路由跳过了意图分类的 LLM 调用，响应更快。


## 七、分类器的坑与修复

### 1. category 幻觉问题

最开始的 Prompt 没有明确告诉 LLM "category 只能用有效的分类名"，结果 LLM 经常把话题关键词当分类输出：

```
用户："博主们对冷暴力怎么看？"
❌ {"filters": {"category": "冷暴力"}}   ← "冷暴力"不是有效分类！
✅ {"filters": {"keywords": "冷暴力"}}   ← "冷暴力"是话题关键词
```

修复方法是在 Prompt 里反复强调：

```
**重要：category 是目录分类名，不是话题关键词。
"冷暴力"是话题（用 keywords），不是分类。**
```

同时在 Prompt 里列出所有 31 个有效分类名，让 LLM 只能从中选择。

### 2. up_name 简称不标准化

另一个常见问题是 LLM 把用户输入的简称直接当 up_name 输出：

```
用户："桃姐最近发了几个视频？"
❌ {"filters": {"up_name": "桃姐"}}              ← 数据库里没有"桃姐"
✅ {"filters": {"up_name": "恋爱教头桃姐"}}       ← 从已知列表中选择
```

修复方法同样是在 Prompt 里反复强调 + 给示例：

```
**极其重要 - up_name 标准化规则：**
- up_name 字段的值必须从"已知UP主完整名称列表"中选择
- ✅ 正确：up_name = "恋爱教头桃姐"
- ❌ 错误：up_name = "桃姐"
```

再加上代码里的后处理模糊匹配（第六篇讲的三层标准化），双重保险。


## 八、完整查询流程

看一个 Hybrid 查询的完整流程：

```
用户："桃姐最近聊了什么话题？她关于吵架的建议是什么？"
    ↓
[Step 1: 意图分类]
  MiniMax M2.7（Prompt Caching，省 90% 费用）
  → route_type: "hybrid"
  → filters: {"up_name": "恋爱教头桃姐", "keywords": "吵架"}
  → reasoning: "需要找桃姐的视频（结构化）+ 理解她关于吵架的建议（语义）"
    ↓
[Step 2: 并行查询]
  ┌─ ThreadPoolExecutor ─────────────────────────┐
  │                                               │
  │  [SQL 通道]                                  │
  │  enhanced_question: "...（UP主完整名称是：   │
  │    恋爱教头桃姐）"                           │
  │  pre_intent: {query_target: "video_list",    │
  │    filters: {up_name: "恋爱教头桃姐"}}        │
  │  → SELECT title, publish_date FROM video_meta│
  │    WHERE up_name = '恋爱教头桃姐'            │
  │    ORDER BY publish_date DESC LIMIT 10       │
  │  → [("吵架后怎么和好", "2026-05-28"),        │
  │     ("忽冷忽热怎么办", "2026-05-25"), ...]   │
  │                                               │
  │  [RAG 通道]                                  │
  │  query: "桃姐...吵架..." + keywords:"吵架"   │
  │  filter: {"up_name": "恋爱教头桃姐"}         │
  │  → BM25 + 向量混合检索                       │
  │  → "桃姐在视频《吵架后怎么和好》中提到：     │
  │    第一不要冷战超过24小时，第二..."          │
  │                                               │
  └───────────────────────────────────────────────┘
    ↓
[Step 3: LLM 融合]
  MiniMax M2.7（Prompt Caching）
  → "桃姐最近发布了3个视频，话题涉及吵架处理
     和忽冷忽热。关于吵架，她的建议是：
     1. 不要冷战超过24小时
     2. 主动承认自己的问题
     3. 用'我觉得'代替'你总是'"
    ↓
[返回]
  {
    "answer": "桃姐最近发布了3个视频...",
    "route_type": "hybrid",
    "sql": "SELECT title, publish_date...",
    "sql_result": [...],
    "sources": [{"bvid": "BV1xxx", "up_name": "恋爱教头桃姐"}],
    "reasoning": "需要找桃姐的视频 + 理解她关于吵架的建议",
    "response_time": 5.2
  }
```

整个过程大约 5 秒，其中意图分类 ~1s，SQL + RAG 并行 ~3s，LLM 融合 ~1s。

[截图：前端对话界面，展示一个 hybrid 查询的完整回答——路由标签为紫色（hybrid），包含自然语言回答、SQL 语句、结果表格和来源引用]


## 总结

Router Agent 是系统的"大脑"——它用一次 LLM 调用判断用户意图，决定走哪个通道，hybrid 模式下并行调用两个通道并用 LLM 融合结果。Prompt Caching 让意图分类的 API 费用降低 90%，智能降级确保即使某个通道失败也能返回有用的回答。分类器的两个坑（category 幻觉和 up_name 不标准化）都通过 Prompt 反复强调 + 代码后处理双重保障来解决。下一篇讲 React 前端和管理面板。
