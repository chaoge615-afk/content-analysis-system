#!/usr/bin/env python3
"""
语义+关键词检索脚本 - 混合模式
1. BM25 关键词检索（即时可用）
2. 本地 sentence-transformers 向量检索（all-MiniLM-L6-v2）

用法:
  python3 semantic_search.py --build     # 构建/更新索引
  python3 semantic_search.py "问题" [top_k]  # 检索（默认top3）
"""

import os, sys, json, math, re
from collections import Counter

MATERIAL_DIR = "/vol1/@apphome/trim.openclaw/data/workspace/skills/relationship-analysis/references/情感素材库"
INDEX_FILE = "/vol1/@apphome/trim.openclaw/data/workspace/skills/relationship-analysis/references/.search_index.json"
VENV_PYTHON = "/vol1/@apphome/trim.openclaw/data/workspace/skills/relationship-analysis/.venv-semantic/bin/python3"

# SiliconFlow embedding API
SILICON_API_URL = "https://api.siliconflow.cn/v1/embeddings"
SILICON_API_KEY = "sk-dhqdknytqmbnvmlxzuvynnozozzyjysmmhbintubceyrzjxg"

def get_embedding(text):
    """调用 SiliconFlow Qwen3-VL-Embedding-8B API"""
    import urllib.request, json
    payload = json.dumps({
        "input": text,
        "model": "Qwen/Qwen3-VL-Embedding-8B"
    }).encode()
    req = urllib.request.Request(
        SILICON_API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {SILICON_API_KEY}",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            items = data.get("data", [])
            if items and len(items) > 0:
                return items[0].get("embedding", [])
            return None
    except Exception as e:
        print(f"Embedding API error: {e}")
        return None

def cosine_sim(a, b):
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    return dot  # 归一化后直接点积即为余弦相似度

# ============ BM25 检索 ============
class BM25:
    def __init__(self, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.doc_len = []
        self.avgdl = 0
        self.idf = {}
        self.doc_tokens = []

    def fit(self, corpus):
        self.doc_tokens = [[w for w in self._tokenize(doc)] for doc in corpus]
        self.doc_len = [len(d) for d in self.doc_tokens]
        self.avgdl = sum(self.doc_len) / len(self.doc_len) if self.doc_len else 0
        df = {}
        for doc in self.doc_tokens:
            for w in set(doc):
                df[w] = df.get(w, 0) + 1
        N = len(corpus)
        self.idf = {w: math.log(N - df[w] + 0.5) - math.log(df[w] + 0.5) + 1 for w in df}

    def _tokenize(self, text):
        return re.findall(r'\w+', text.lower())

    def score(self, query, doc_idx):
        score = 0.0
        doc = self.doc_tokens[doc_idx]
        freq = Counter(doc)
        dl = self.doc_len[doc_idx]
        for term in self._tokenize(query):
            if term not in freq:
                continue
            tf = freq[term]
            idf = self.idf.get(term, 0)
            score += idf * (tf * (self.k1 + 1)) / (tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
        return score

# ============ 索引管理 ============
def extract_search_text(content):
    """从精炼文件中提取检索文本（核心观点 + 案例摘要）"""
    if "**核心观点**" not in content:
        return content[:300]
    try:
        start = content.index("**核心观点**") + len("**核心观点**")
        end_marker = "**案例摘要**"
        end = start + content[start:].index(end_marker) if end_marker in content[start:] else start + 300
        core = content[start:end].strip()
        if "**案例摘要**" in content:
            case_start = content.index("**案例摘要**") + len("**案例摘要**")
            case_end_marker = "**结论"
            case_end = case_start + content[case_start:].index(case_end_marker) if case_end_marker in content[case_start:] else case_start + 200
            case = content[case_start:case_end].strip()
            return core + " " + case
        return core
    except:
        return content[:300]

def load_index():
    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def save_index(index):
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

def build_index():
    """构建检索索引（BM25 + 向量）"""
    print("开始构建检索索引...")
    corpus = []
    files = []
    vectors = []

    for root, dirs, filenames in os.walk(MATERIAL_DIR):
        for fname in sorted(filenames):
            if not fname.endswith(".txt"):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
                search_text = extract_search_text(content)
                if not search_text.strip():
                    continue
                rel_path = os.path.relpath(fpath, os.path.dirname(MATERIAL_DIR))
                corpus.append(search_text)
                files.append(rel_path)
                emb = get_embedding(search_text)
                vectors.append(emb if emb else None)
                status = "✅" if emb else "⚠️"
                print(f"  {status} {rel_path}")
            except Exception as e:
                print(f"  ❌ {fname}: {e}")

    bm25 = BM25()
    bm25.fit(corpus)

    index = {
        "corpus": corpus,
        "files": files,
        "vectors": vectors,
        "vector_enabled": any(v is not None for v in vectors),
        "bm25_k1": bm25.k1,
        "bm25_b": bm25.b,
        "bm25_doc_len": bm25.doc_len,
        "bm25_avgdl": bm25.avgdl,
        "bm25_idf": bm25.idf,
        "bm25_doc_tokens": bm25.doc_tokens,
    }
    save_index(index)
    print(f"\n索引构建完成: {len(files)} 条, 向量启用: {index['vector_enabled']}")
    return index

def load_and_check_index():
    idx = load_index()
    if not idx or not idx.get("corpus"):
        print("索引为空，正在重建...")
        idx = build_index()
    return idx

# ============ 检索 ============
def search(query, top_k=3):
    idx = load_and_check_index()
    corpus = idx["corpus"]
    files = idx["files"]
    vectors = idx.get("vectors", [])

    # BM25
    bm25 = BM25(k1=idx.get("bm25_k1", 1.5), b=idx.get("bm25_b", 0.75))
    bm25.doc_len = idx.get("bm25_doc_len", [])
    bm25.avgdl = idx.get("bm25_avgdl", 0)
    bm25.idf = idx.get("bm25_idf", {})
    bm25.doc_tokens = idx.get("bm25_doc_tokens", [])

    bm25_scores = [(bm25.score(query, i), i) for i in range(len(corpus))]
    bm25_scores.sort(reverse=True)

    # 向量
    vector_scores = []
    if idx.get("vector_enabled"):
        q_emb = get_embedding(query)
        if q_emb:
            vector_scores = [(cosine_sim(q_emb, v), i) for i, v in enumerate(vectors) if v]
            vector_scores.sort(reverse=True)

    # 融合排名
    combined = {}
    for rank, (score, i) in enumerate(sorted(bm25_scores, key=lambda x: -x[0])[:top_k * 2]):
        combined[i] = combined.get(i, 0) + max(0, 3 - rank)
    for rank, (score, i) in enumerate(vector_scores[:top_k * 2]):
        combined[i] = combined.get(i, 0) + max(0, 3 - rank)

    results = sorted(combined.items(), key=lambda x: -x[1])[:top_k]
    return [(files[i], corpus[i][:200]) for _, i in results]

# ============ CLI ============
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  python3 semantic_search.py --build     # 构建/更新索引")
        print("  python3 semantic_search.py \"问题\" [top_k]  # 检索")
        sys.exit(0)

    if sys.argv[1] == "--build":
        build_index()
    else:
        query = sys.argv[1]
        top_k = int(sys.argv[2]) if len(sys.argv) > 2 else 3
        print(f"\n🔍 查询: {query}\n")
        results = search(query, top_k)
        if not results:
            print("未找到相关内容")
        else:
            for i, (path, preview) in enumerate(results, 1):
                print(f"--- 结果 {i} ---")
                print(f"文件: {path}")
                print(f"预览: {preview[:150]}...")
                print()