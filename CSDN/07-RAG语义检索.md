## 系列文章目录

[B站视频内容智能分析系统（一）：项目介绍与架构设计](./01-项目介绍与架构设计.md)
[B站视频内容智能分析系统（二）：Docker Compose 一键部署](./02-Docker-Compose一键部署.md)
[B站视频内容智能分析系统（三）：B站视频自动采集](./03-B站视频自动采集.md)
[B站视频内容智能分析系统（四）：语音转写三级回退](./04-语音转写三级回退.md)
[B站视频内容智能分析系统（五）：LLM 内容精炼与多域分类](./05-LLM内容精炼与分类.md)
[B站视频内容智能分析系统（六）：Text-to-SQL 结构化查询](./06-Text-to-SQL结构化查询.md)
B站视频内容智能分析系统（七）：RAG 语义检索


### 文章目录

+ [系列文章目录](#_0)
+ [前言](#前言)
+ [一、RAG 的基本原理](#一rag-的基本原理)
+ [二、为什么用混合检索](#二为什么用混合检索)
+ [三、纯 Python 实现 BM25](#三纯-python-实现-bm25)
    + [1. BM25 算法简介](#1-bm25-算法简介)
    + [2. 中文分词策略](#2-中文分词策略)
    + [3. 完整实现](#3-完整实现)
+ [四、向量语义检索](#四向量语义检索)
    + [1. SiliconFlow Embedding](#1-siliconflow-embedding)
    + [2. ChromaDB 向量存储](#2-chromadb-向量存储)
+ [五、Rank-based Fusion 融合策略](#五rank-based-fusion-融合策略)
    + [1. 融合思路](#1-融合思路)
    + [2. 打分规则](#2-打分规则)
    + [3. 完整融合代码](#3-完整融合代码)
+ [六、Metadata 过滤检索](#六metadata-过滤检索)
    + [1. 过滤条件构建](#1-过滤条件构建)
    + [2. 关键词增强查询](#2-关键词增强查询)
+ [七、RAG 问答 LLM](#七rag-问答-llm)
    + [1. 双 LLM 支持](#1-双-llm-支持)
    + [2. Prompt 设计](#2-prompt-设计)
    + [3. 来源引用](#3-来源引用)
+ [八、完整检索流程](#八完整检索流程)
+ [总结](#总结)




## 前言

上一篇讲了 Text-to-SQL，解决了"桃姐发了几个视频"这类统计查询。但用户更常见的需求是语义类的——"博主们对冷暴力怎么看？""吵架后不应该做什么？"

这类问题没法用 SQL 回答，因为答案分散在几十个视频的转写文本里。需要用 RAG（Retrieval-Augmented Generation）——先从知识库里检索相关文档，再让 LLM 基于这些文档生成回答。

这篇讲 RAG 检索部分的实现。核心是一个**BM25 + 向量混合检索**的方案，用纯 Python 实现了 BM25（~130 行），不依赖任何 NLP 库。


## 一、RAG 的基本原理

RAG 的流程很直观：

```
用户问题："博主们对冷暴力怎么看？"
    ↓
① 检索：从知识库里找到和"冷暴力"相关的文档片段
    ↓
② 拼接：把检索到的文档拼成上下文
    ↓
③ 生成：让 LLM 基于上下文回答用户问题
```

关键在第一步——检索的质量直接决定了最终回答的质量。如果检索到的文档不相关，LLM 再厉害也编不出好答案。


## 二、为什么用混合检索

单一的检索方式各有短板：

**纯向量检索**（Embedding + 余弦相似度）：
- ✅ 能理解语义（"吵架"和"争执"是近义词）
- ❌ 对精确关键词匹配弱（"BV1Nh5r6PEZb"这种 ID 向量检索可能匹配不上）

**纯关键词检索**（BM25）：
- ✅ 精确匹配关键词很准
- ❌ 不理解语义（"冷暴力"和"沉默对待"是同义词但 BM25 不知道）

**混合检索** = BM25 + 向量，两者互补。一个文档如果在两种检索方式里都排名靠前，说明它确实高度相关。

这也是很多 RAG 系统的最佳实践——不是二选一，而是两个都用，然后融合结果。


## 三、纯 Python 实现 BM25

### 1. BM25 算法简介

BM25（Best Matching 25）是信息检索领域的经典算法，可以理解为"改进版的 TF-IDF"。它的核心思想：

- **TF**（词频）：一个词在文档中出现得越多，分数越高——但有饱和效应（出现 100 次不比 10 次高多少）
- **IDF**（逆文档频率）：一个词在大多数文档中都出现，那它就不重要（比如"的""了"）；只在少数文档中出现，则很重要
- **文档长度归一化**：长文档天然会获得更多词频，需要打折

BM25 的公式：

```
score(D, Q) = Σ IDF(qi) × (tf(qi,D) × (k1+1)) / (tf(qi,D) + k1 × (1 - b + b × |D|/avgdl))
```

其中 `k1=1.5` 控制词频饱和速度，`b=0.75` 控制文档长度归一化程度。

### 2. 中文分词策略

BM25 需要分词。对于中文，正规的做法是用 jieba 之类的分词库。但我做了一个更简单的选择——**按 `\w+` 正则匹配**：

```python
def _tokenize(self, text: str) -> List[str]:
    """简单分词：英文按单词，中文按单字"""
    return re.findall(r'\w+', text.lower())
```

对于中文，`\w+` 会把每个汉字当成一个独立的 token。看起来很粗糙，但在这个场景下效果还不错：

- "冷暴力"会被分成 ["冷", "暴", "力"] 三个单字
- 如果另一个文档也包含"冷""暴""力"这三个字，BM25 的 IDF 机制会让它们获得较高的匹配分数
- 不需要安装 jieba，减少了 Docker 镜像大小和依赖复杂度

这个方案不完美，但对于几千个文档的规模来说完全够用。如果文档量大了，再换 jieba 也不迟。

### 3. 完整实现

整个 BM25 实现只有 ~65 行：

```python
class BM25:
    """BM25 关键词检索（纯 Python 实现，无需外部依赖）"""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_tokens: List[List[str]] = []
        self.doc_len: List[int] = []
        self.avgdl: float = 0
        self.idf: dict = {}

    def fit(self, corpus: List[str]):
        """构建 BM25 索引"""
        self.doc_tokens = [self._tokenize(doc) for doc in corpus]
        self.doc_len = [len(d) for d in self.doc_tokens]
        self.avgdl = sum(self.doc_len) / len(self.doc_len) if self.doc_len else 0

        # 计算 IDF
        df = {}
        for doc in self.doc_tokens:
            for w in set(doc):
                df[w] = df.get(w, 0) + 1
        N = len(corpus)
        self.idf = {
            w: math.log(N - df[w] + 0.5) - math.log(df[w] + 0.5) + 1
            for w in df
        }

    def score(self, query: str, doc_idx: int) -> float:
        """计算查询与指定文档的 BM25 分数"""
        score = 0.0
        doc = self.doc_tokens[doc_idx]
        freq = Counter(doc)
        dl = self.doc_len[doc_idx]
        for term in self._tokenize(query):
            if term not in freq:
                continue
            tf = freq[term]
            idf = self.idf.get(term, 0)
            score += idf * (tf * (self.k1 + 1)) / (
                tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
            )
        return score

    def score_all(self, query: str) -> List[Tuple[float, int]]:
        """对所有文档打分并排序"""
        scores = [(self.score(query, i), i) for i in range(len(self.doc_tokens))]
        scores.sort(reverse=True)
        return scores
```

核心就三步：
1. `fit()`：分词 + 计算 IDF
2. `score()`：对单个文档计算 BM25 分数
3. `score_all()`：对所有文档打分排序


## 四、向量语义检索

### 1. SiliconFlow Embedding

向量检索用的是 SiliconFlow 的 `BAAI/bge-large-zh-v1.5` 模型。这是一个中文优化的 Embedding 模型，能把文本转成 1024 维的向量。

```python
self.embeddings = SiliconFlowEmbeddings(
    api_key=siliconflow_api_key,
    model="BAAI/bge-large-zh-v1.5",
    base_url="https://api.siliconflow.cn/v1",
)
```

SiliconFlow 提供了免费的 Embedding API 额度，对于几千个文档来说完全够用。

### 2. ChromaDB 向量存储

向量存在 ChromaDB 里，用的是 `video_knowledge` collection：

```python
self.video_vector_db = Chroma(
    client=remote_client,
    collection_name="video_knowledge",
    embedding_function=self.embeddings,
)
```

每个文档在 ChromaDB 里存了三部分：
- **document**：文本内容（转写全文或精炼摘要）
- **embedding**：1024 维向量
- **metadata**：来源信息（UP主、分类、BV号等）

检索时，ChromaDB 把查询文本也转成向量，然后和库里所有向量做余弦相似度计算，返回最相似的 top_k 个文档。


## 五、Rank-based Fusion 融合策略

### 1. 融合思路

BM25 和向量检索各自返回一个排序列表。怎么把两个列表合并？

最直观的方法是加权求和——给 BM25 分数乘一个权重，向量分数乘另一个权重，然后相加。但问题是两种分数的量纲不一样：BM25 分数可能是 5.3，向量相似度可能是 0.87，没法直接比。

所以我用了 **Rank-based Fusion**——不看分数，只看排名。

### 2. 打分规则

规则很简单：**排名越靠前，得分越高**。

```python
rank_cap = 3  # 只取前 3 名参与计分

for rank, (score, doc_idx) in enumerate(results[:top_k * 2]):
    points = max(0, rank_cap - rank)
    # rank=0 → 3分, rank=1 → 2分, rank=2 → 1分, rank≥3 → 0分
    if points > 0:
        combined[doc_idx] = combined.get(doc_idx, 0) + points
```

具体来说：
- 排名第 1 → 3 分
- 排名第 2 → 2 分
- 排名第 3 → 1 分
- 排名第 4 及以后 → 0 分

BM25 和向量检索各自独立打分，然后同一个文档的分数相加。如果一个文档在两种检索里都排第 1，它会得到 3+3=6 分，排在最前面。

### 3. 完整融合代码

```python
class HybridSearch:
    def __init__(self, rank_cap: int = 3):
        self.rank_cap = rank_cap

    def search(self, query, bm25, vector_search_fn, top_k=5):
        combined = {}

        # BM25 检索
        if bm25:
            bm25_scores = bm25.score_all(query)
            for rank, (score, i) in enumerate(bm25_scores[:top_k * 2]):
                points = max(0, self.rank_cap - rank)
                if points > 0:
                    combined[i] = combined.get(i, 0) + points

        # 向量检索
        if vector_search_fn:
            try:
                vector_scores = vector_search_fn(query, top_k * 2)
                for rank, (score, i) in enumerate(vector_scores[:top_k * 2]):
                    points = max(0, self.rank_cap - rank)
                    if points > 0:
                        combined[i] = combined.get(i, 0) + points
            except Exception as e:
                print(f"[混合检索] 向量检索失败，仅使用 BM25: {e}")

        # 融合排序
        results = sorted(combined.items(), key=lambda x: -x[1])[:top_k]
        return results
```

这个方案的好处是**鲁棒**——即使向量检索挂了（比如 API 超时），BM25 还能继续工作，只是少了一半的分数。


## 六、Metadata 过滤检索

### 1. 过滤条件构建

RAG 检索不只是"找相似的文档"，还需要按条件过滤。比如用户问"桃姐对冷暴力怎么看"，我们只想检索桃姐的视频，不想混入其他博主的内容。

ChromaDB 支持 `where` 过滤：

```python
def _build_where_filter(self, metadata_filter: dict) -> dict:
    """构建 ChromaDB where 过滤条件"""
    conditions = []
    if metadata_filter.get("up_name"):
        conditions.append({"up_name": metadata_filter["up_name"]})
    if metadata_filter.get("category"):
        conditions.append({"category": metadata_filter["category"]})
    if metadata_filter.get("bvid"):
        conditions.append({"bvid": metadata_filter["bvid"]})

    if len(conditions) == 0:
        return {}
    elif len(conditions) == 1:
        return conditions[0]
    else:
        return {"$and": conditions}
```

过滤后的检索：

```python
# 只在桃姐的视频中检索
docs = self.video_vector_db.similarity_search(
    query="冷暴力",
    k=5,
    filter={"up_name": "恋爱教头桃姐"}
)
```

### 2. 关键词增强查询

Router Agent 传过来的过滤条件里可能包含 `keywords`（比如"冷暴力""吵架"）。这些关键词不适合作为 ChromaDB 的 where 过滤（因为 metadata 里没有 keywords 字段），但可以拼接到查询文本里增强检索效果：

```python
query_text = question
metadata_filter = dict(metadata_filter or {})
if "keywords" in metadata_filter:
    kw = metadata_filter.pop("keywords", "")
    if kw:
        query_text = f"{question} {kw}"
```

比如：
- 原始问题："桃姐关于吵架有什么建议？"
- keywords: "吵架"
- 增强后的查询："桃姐关于吵架有什么建议？ 吵架"

多了一个"吵架"，BM25 和向量检索都会更精准地匹配到相关内容。


## 七、RAG 问答 LLM

### 1. 双 LLM 支持

RAG 问答支持两种 LLM，通过环境变量切换：

```python
self.llm_provider = os.getenv("LLM_PROVIDER", "minimax")
if self.llm_provider == "deepseek":
    self.llm = openai.OpenAI(
        api_key=self.deepseek_api_key,
        base_url=self.deepseek_base_url,
    )
else:
    self.llm = anthropic.Anthropic(
        api_key=self.api_key,
        base_url=self.base_url,
    )
```

- **DeepSeek V4 Flash**（默认）：便宜、快、中文好
- **MiniMax M2.7**（备选）：Anthropic API 兼容

### 2. Prompt 设计

RAG 的 Prompt 拆成两部分——静态系统指令 + 动态用户内容：

```python
# 静态系统指令（可被 Prompt Caching 缓存）
self.system_prompt = """你是一个基于用户个人知识库的问答助手。
请根据提供的上下文信息回答用户的问题。
如果上下文中没有找到答案，请直接说"我在知识库中没有找到相关内容"。
不要编造信息，也不要引用无关内容。"""

# 动态用户内容
self.user_template = """上下文信息：
{context}

用户问题：{question}

回答："""
```

上下文拼接时附带来源信息：

```python
for doc in docs:
    meta = doc.metadata
    source_info = ""
    if meta.get("up_name"):
        source_info += f"[UP主: {meta['up_name']}] "
    if meta.get("category"):
        source_info += f"[分类: {meta['category']}] "
    context_parts.append(f"{source_info}\n{doc.page_content}")
```

这样 LLM 生成的回答里可以引用来源——"根据桃姐在'忽冷忽热'分类下的视频..."。

### 3. 来源引用

RAG 回答会附带来源信息，让用户知道答案是从哪些视频里检索出来的：

```python
sources = []
for doc in docs:
    meta = doc.metadata
    bvid = meta.get("bvid", "")
    if bvid and bvid not in seen_bvids:
        seen_bvids.add(bvid)
        sources.append({
            "bvid": bvid,
            "title": meta.get("title", ""),
            "up_name": meta.get("up_name", ""),
            "category": meta.get("category", ""),
        })
```

前端会展示这些来源，用户可以点击跳转到原始视频。


## 八、完整检索流程

串起来看一个完整的 RAG 查询：

```
用户："博主们对冷暴力怎么看？"
    ↓
[Router Agent]
  意图分类 → semantic
  过滤条件 → {"keywords": "冷暴力"}
    ↓
[RAG Engine]
  ① 构建查询："博主们对冷暴力怎么看？ 冷暴力"（关键词增强）
  ② BM25 检索：
     - 找到包含"冷""暴""力"的文档
     - rank 1: doc_42, rank 2: doc_108, rank 3: doc_7
  ③ 向量检索：
     - 找到语义相似的文档
     - rank 1: doc_42, rank 2: doc_15, rank 3: doc_108
  ④ Rank-based Fusion：
     - doc_42: BM25 rank1(3) + Vector rank1(3) = 6分 ✅
     - doc_108: BM25 rank2(2) + Vector rank3(1) = 3分
     - doc_7: BM25 rank3(1) = 1分
     - doc_15: Vector rank2(2) = 2分
  ⑤ 排序：doc_42 > doc_108 > doc_15 > doc_7
  ⑥ 取 top 5，拼接上下文
    ↓
[LLM 生成回答]
  "根据知识库中多位博主的观点：
   1. 恋爱教头桃姐认为冷暴力是一种情感操控...
   2. 安佳建议遇到冷暴力时不要主动讨好...
   
   来源：
   - [03_撩妹] 冷暴力的本质是什么 [BV1Nh5r6PEZb]
   - [25_关系] 吵架后的正确处理方式 [BV1Xk4y1M7az]"
    ↓
[返回给用户]
```

[截图：前端对话界面，展示一个语义查询的回答，包含回答内容和来源引用]


## 总结

RAG 检索的核心是 BM25 + 向量混合检索 + Rank-based Fusion。BM25 用纯 Python 实现（~130 行），不依赖任何 NLP 库，中文按单字分词在这个场景下够用。向量检索用 SiliconFlow 的 Embedding + ChromaDB 存储。融合策略不看分数只看排名，简单但有效。metadata 过滤让检索可以精确到"只看某个博主的某个分类"。下一篇讲 Router Agent 智能路由——它怎么决定一个问题该走 Text-to-SQL 还是 RAG。
