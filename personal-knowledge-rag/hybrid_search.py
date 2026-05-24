"""
混合检索模块：BM25 关键词检索 + 向量语义检索
参考 relationship-analysis/semantic_search.py 的 rank-based 融合策略
"""

import math
import re
from collections import Counter
from typing import List, Tuple, Optional


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

    def _tokenize(self, text: str) -> List[str]:
        """简单分词：英文按单词，中文按单字"""
        return re.findall(r'\w+', text.lower())

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
        """对所有文档打分并排序，返回 [(score, doc_idx), ...]"""
        scores = [(self.score(query, i), i) for i in range(len(self.doc_tokens))]
        scores.sort(reverse=True)
        return scores


class HybridSearch:
    """
    混合检索：BM25 + 向量，使用 rank-based 融合策略
    参考 relationship-analysis 的 max(0, 3-rank) 打分策略
    """

    def __init__(self, rank_cap: int = 3):
        """
        Args:
            rank_cap: 融合打分时只取前 rank_cap 名的结果参与计分
        """
        self.rank_cap = rank_cap

    def build_bm25_index(self, texts: List[str]) -> BM25:
        """构建 BM25 索引"""
        bm25 = BM25()
        bm25.fit(texts)
        return bm25

    def search(
        self,
        query: str,
        bm25: Optional[BM25],
        vector_search_fn=None,
        top_k: int = 5,
    ) -> List[Tuple[int, float]]:
        """
        混合检索，返回 [(doc_idx, fusion_score), ...]

        Args:
            query: 查询文本
            bm25: BM25 索引实例（可选，为 None 则跳过关键词检索）
            vector_search_fn: 向量检索回调函数，签名 (query, top_k) -> [(score, doc_idx), ...]
                             如果为 None 则跳过向量检索
            top_k: 返回结果数

        Returns:
            [(doc_idx, fusion_score), ...] 按分数降序
        """
        combined = {}

        # BM25 检索
        if bm25 and len(bm25.doc_tokens) > 0:
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
