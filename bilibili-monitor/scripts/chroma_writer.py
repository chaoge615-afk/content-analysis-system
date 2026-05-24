"""ChromaDB writer for video transcripts and summaries."""

import os
import sys
from pathlib import Path
import chromadb
from chromadb.config import Settings
from typing import List, Optional

# Add project root to path for shared_config
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from shared_config import config


class SiliconFlowEmbeddings:
    """SiliconFlow Embeddings implementation using their API."""

    def __init__(self):
        self.api_key = config.embedding.api_key
        self.base_url = config.embedding.base_url
        self.model = config.embedding.model

        if not self.api_key:
            raise ValueError(
                "SiliconFlow API key not configured. "
                "Please set EMBEDDING_API_KEY in .env"
            )

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents."""
        import requests

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        embeddings = []
        # Process in batches to avoid hitting API limits
        batch_size = 10
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            data = {
                "model": self.model,
                "input": batch,
            }

            response = requests.post(
                f"{self.base_url}/embeddings",
                headers=headers,
                json=data,
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()

            # Extract embeddings from response
            batch_embeddings = [item["embedding"] for item in result["data"]]
            embeddings.extend(batch_embeddings)

        return embeddings

    def embed_query(self, text: str) -> List[float]:
        """Embed a single query."""
        return self.embed_documents([text])[0]


class ChromaWriter:
    """ChromaDB writer for video content."""

    def __init__(
        self,
        collection_name: str = "video_knowledge",
        persist_directory: Optional[str] = None,
    ):
        """Initialize ChromaDB writer with SiliconFlow embeddings."""

        # Set up persist directory
        # 默认使用 scripts/data/chromadb（与迁移脚本写入路径一致）
        if persist_directory is None:
            persist_directory = os.getenv(
                "CHROMA_PERSIST_DIR",
                str(Path(__file__).parent / "data" / "chromadb"),
            )

        Path(persist_directory).mkdir(parents=True, exist_ok=True)

        # ChromaDB Rust 后端在 Windows 上不支持路径含非 ASCII 字符（如中文）
        # 临时切换到脚本目录，使用相对路径初始化
        _original_cwd = os.getcwd()
        _scripts_dir = str(Path(__file__).parent)
        try:
            os.chdir(_scripts_dir)
            _rel_path = os.path.relpath(persist_directory, _scripts_dir)
            self.client = chromadb.PersistentClient(
                path=_rel_path,
                settings=Settings(anonymized_telemetry=False),
            )
        finally:
            os.chdir(_original_cwd)

        # Initialize SiliconFlow embeddings
        self.embeddings = SiliconFlowEmbeddings()

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
