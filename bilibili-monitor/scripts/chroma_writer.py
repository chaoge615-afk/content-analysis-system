"""
ChromaDB 写入模块
存储视频转写文本和精炼摘要，支持语义检索
"""
import os
from pathlib import Path
from typing import List, Dict, Optional
import chromadb
from chromadb.config import Settings


class ChromaWriter:
    """ChromaDB 向量数据库写入器"""

    def __init__(self, persist_dir: str = None):
        """
        初始化 ChromaDB 客户端
        persist_dir: 持久化目录，默认使用环境变量或 ./data/chromadb
        """
        if persist_dir is None:
            persist_dir = os.getenv('CHROMADB_PATH', './data/chromadb')

        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        # 初始化 ChromaDB 客户端
        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=Settings(anonymized_telemetry=False)
        )

        # 获取或创建 video_knowledge collection
        self.collection = self.client.get_or_create_collection(
            name="video_knowledge",
            metadata={"description": "B站视频转写和精炼知识库"}
        )

    def add_video_content(
        self,
        bvid: str,
        up_name: str,
        title: str,
        category: str,
        publish_date: str,
        content: str,
        content_type: str = "full",
        chunk_index: int = 0
    ) -> bool:
        """
        添加视频内容到 ChromaDB
        bvid: 视频 BV 号
        up_name: UP 主名称
        title: 视频标题
        category: 分类
        publish_date: 发布日期 (YYYY-MM-DD)
        content: 文本内容
        content_type: "full" (转写全文) 或 "summary" (精炼摘要)
        chunk_index: 分块序号（长文本需要分块时使用）
        """
        try:
            # 生成唯一 ID
            doc_id = f"{bvid}_{content_type}_{chunk_index}"

            # 准备 metadata
            metadata = {
                "source": "bilibili",
                "bvid": bvid,
                "up_name": up_name,
                "title": title,
                "category": category,
                "publish_date": publish_date,
                "chunk_index": chunk_index,
                "content_type": content_type,
            }

            # 添加到 collection
            self.collection.add(
                documents=[content],
                metadatas=[metadata],
                ids=[doc_id]
            )
            return True
        except Exception as e:
            print(f"添加视频内容失败 ({bvid}): {e}")
            return False

    def add_video_with_chunks(
        self,
        bvid: str,
        up_name: str,
        title: str,
        category: str,
        publish_date: str,
        full_text: Optional[str] = None,
        summary: Optional[str] = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ) -> int:
        """
        添加视频内容（支持全文分块 + 摘要）
        返回成功添加的文档数量
        """
        count = 0

        # 1. 添加精炼摘要（如果有）
        if summary and summary.strip():
            if self.add_video_content(
                bvid=bvid,
                up_name=up_name,
                title=title,
                category=category,
                publish_date=publish_date,
                content=summary,
                content_type="summary",
                chunk_index=0
            ):
                count += 1

        # 2. 添加转写全文（分块）
        if full_text and full_text.strip():
            chunks = self._split_text(full_text, chunk_size, chunk_overlap)
            for idx, chunk in enumerate(chunks):
                if self.add_video_content(
                    bvid=bvid,
                    up_name=up_name,
                    title=title,
                    category=category,
                    publish_date=publish_date,
                    content=chunk,
                    content_type="full",
                    chunk_index=idx
                ):
                    count += 1

        return count

    def _split_text(self, text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
        """
        简单文本分块（按字符数）
        后续可以改用更智能的分块策略（如按句子/段落）
        """
        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = start + chunk_size
            chunk = text[start:end]
            if chunk.strip():
                chunks.append(chunk)
            start = end - chunk_overlap

        return chunks

    def get_stats(self) -> Dict:
        """获取 collection 统计信息"""
        count = self.collection.count()
        return {
            "collection": "video_knowledge",
            "total_documents": count,
            "persist_dir": str(self.persist_dir)
        }

    def delete_by_bvid(self, bvid: str) -> int:
        """
        删除指定 bvid 的所有文档
        返回删除的文档数量
        """
        try:
            # 查询该 bvid 的所有文档
            results = self.collection.get(
                where={"bvid": bvid}
            )
            if results and results['ids']:
                count = len(results['ids'])
                self.collection.delete(ids=results['ids'])
                return count
            return 0
        except Exception as e:
            print(f"删除 bvid={bvid} 失败: {e}")
            return 0
