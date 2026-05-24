"""ChromaDB writer for video transcripts and summaries."""

import os
import sys
from pathlib import Path
import chromadb
from chromadb.config import Settings
from typing import List, Optional

# Add project root to path for shared modules
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared_embeddings import SiliconFlowEmbeddings


class ChromaWriter:
    """ChromaDB writer for video content."""

    def __init__(
        self,
        collection_name: str = "video_knowledge",
        persist_directory: Optional[str] = None,
    ):
        """
        Initialize ChromaDB writer with SiliconFlow embeddings.
        支持本地持久化和远程 ChromaDB 容器两种模式。
        设置 CHROMA_HOST 环境变量使用远程模式（与 RAG 服务共享）。
        """

        # Initialize SiliconFlow embeddings
        self.embeddings = SiliconFlowEmbeddings()

        # 检查是否使用远程 ChromaDB
        chroma_host = os.getenv("CHROMA_HOST")
        chroma_port = int(os.getenv("CHROMA_PORT", "8000"))

        if chroma_host:
            # 远程 ChromaDB 容器（与 RAG 服务共享）
            self.client = chromadb.HttpClient(
                host=chroma_host,
                port=chroma_port,
                settings=Settings(anonymized_telemetry=False),
            )
            self.persist_directory = f"remote://{chroma_host}:{chroma_port}"
            print(f"[ChromaWriter] 连接远程 ChromaDB: {chroma_host}:{chroma_port}")
        else:
            # 本地持久化（开发模式）
            if persist_directory is None:
                persist_directory = os.getenv(
                    "CHROMA_PERSIST_DIR",
                    str(Path(__file__).parent.parent / "data" / "chromadb"),
                )

            Path(persist_directory).mkdir(parents=True, exist_ok=True)

            # ChromaDB Rust 后端在 Windows 上不支持路径含非 ASCII 字符（如中文）
            # 临时切换到 bilibili-monitor 目录，使用相对路径初始化
            _original_cwd = os.getcwd()
            _project_dir = str(Path(__file__).parent.parent)
            try:
                os.chdir(_project_dir)
                _rel_path = os.path.relpath(persist_directory, _project_dir)
                self.client = chromadb.PersistentClient(
                    path=_rel_path,
                    settings=Settings(anonymized_telemetry=False),
                )
            finally:
                os.chdir(_original_cwd)

            self.persist_directory = persist_directory
            print(f"[ChromaWriter] 使用本地持久化: {persist_directory}")

        # Get or create collection（metadata 需与迁移脚本一致）
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "B站视频转写和精炼知识库"},
        )

        self.collection_name = collection_name
        self.persist_directory = persist_directory

    def add_documents(
        self,
        ids: List[str],
        documents: List[str],
        metadatas: Optional[List[dict]] = None,
    ):
        """Add documents to ChromaDB with embeddings."""
        # Generate embeddings using SiliconFlow
        embeddings = self.embeddings.embed_documents(documents)

        # Add to collection
        self.collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )

    def add_video_content(
        self,
        bvid: str,
        up_name: str,
        title: str,
        content: str,
        publish_date: str,
        category: str = "",
        tags: str = "",
    ):
        """
        Add video content to ChromaDB.

        Args:
            bvid: Video BV ID
            up_name: UP host name
            title: Video title
            content: Video transcript/summary content
            publish_date: Publication date
            category: Video category
            tags: Video tags
        """
        # Generate unique ID
        doc_id = f"{bvid}_{hash(content) % 10000:04d}"

        # Prepare metadata
        metadata = {
            "bvid": bvid,
            "up_name": up_name,
            "title": title,
            "publish_date": publish_date,
            "category": category,
            "tags": tags,
            "content_type": "full" if len(content) > 500 else "summary",
        }

        # Add to collection
        self.add_documents(
            ids=[doc_id],
            documents=[content],
            metadatas=[metadata],
        )

    def add_video_with_chunks(
        self,
        bvid: str,
        up_name: str,
        title: str,
        category: str,
        publish_date: str,
        full_text: Optional[str] = None,
        summary: Optional[str] = None,
        chunk_size: int = 500,
    ) -> int:
        """
        将视频内容分块写入 ChromaDB（全文分块 + 摘要单独存储）

        Args:
            bvid: 视频 BV ID
            up_name: UP 主名称
            title: 视频标题
            category: 视频分类
            publish_date: 发布日期
            full_text: 完整转写文本（可选，会按 chunk_size 分块）
            summary: 精炼摘要（可选，单独存储）
            chunk_size: 每块最大字符数

        Returns:
            写入的文档数量
        """
        ids = []
        documents = []
        metadatas = []

        base_meta = {
            "bvid": bvid,
            "up_name": up_name,
            "title": title,
            "publish_date": publish_date or "",
            "category": category or "",
        }

        # 全文分块
        if full_text and full_text.strip():
            text = full_text.strip()
            chunks = []
            for i in range(0, len(text), chunk_size):
                chunk = text[i:i + chunk_size].strip()
                if chunk:
                    chunks.append(chunk)

            for idx, chunk in enumerate(chunks):
                ids.append(f"{bvid}_chunk_{idx}")
                documents.append(chunk)
                meta = {**base_meta, "content_type": "chunk", "chunk_index": idx}
                metadatas.append(meta)

        # 摘要单独存储（过长时分块）
        if summary and summary.strip():
            text = summary.strip()
            if len(text) <= chunk_size:
                ids.append(f"{bvid}_summary")
                documents.append(text)
                meta = {**base_meta, "content_type": "summary"}
                metadatas.append(meta)
            else:
                # 摘要过长，分块存储
                for idx in range(0, len(text), chunk_size):
                    chunk = text[idx:idx + chunk_size].strip()
                    if chunk:
                        chunk_idx = idx // chunk_size
                        ids.append(f"{bvid}_summary_{chunk_idx}")
                        documents.append(chunk)
                        meta = {**base_meta, "content_type": "summary", "chunk_index": chunk_idx}
                        metadatas.append(meta)

        if not documents:
            return 0

        self.add_documents(ids=ids, documents=documents, metadatas=metadatas)
        return len(documents)

    def search(
        self,
        query: str,
        n_results: int = 5,
        where: Optional[dict] = None,
    ) -> dict:
        """
        Search for similar content.

        Args:
            query: Search query
            n_results: Number of results to return
            where: Metadata filter conditions

        Returns:
            Search results with documents, metadatas, and distances
        """
        # Generate query embedding
        query_embedding = self.embeddings.embed_query(query)

        # Build query parameters
        query_params = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
        }

        if where:
            query_params["where"] = where

        # Execute search
        results = self.collection.query(**query_params)

        return results

    def get_stats(self) -> dict:
        """Get collection statistics."""
        count = self.collection.count()
        return {
            "collection": self.collection_name,
            "document_count": count,
            "persist_directory": self.persist_directory,
        }

    def delete_by_bvid(self, bvid: str):
        """Delete all documents for a specific video."""
        # Get all documents with this bvid
        results = self.collection.get(
            where={"bvid": bvid},
        )

        if results["ids"]:
            self.collection.delete(ids=results["ids"])
            return len(results["ids"])
        return 0
