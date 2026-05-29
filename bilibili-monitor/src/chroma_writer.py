"""ChromaDB writer for video transcripts and summaries."""
import os
import sys
from pathlib import Path
import chromadb
from chromadb.config import Settings
from typing import List, Optional

# Add shared/ directory to path for shared modules
sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))
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
        Supports local persistence and remote ChromaDB container modes.
        Set CHROMA_HOST env var to use remote mode (shared with RAG service).
        """

        # Initialize SiliconFlow embeddings
        self.embeddings = SiliconFlowEmbeddings()

        # Check for remote ChromaDB
        chroma_host = os.getenv("CHROMA_HOST")
        chroma_port = int(os.getenv("CHROMA_PORT", "8000"))

        if chroma_host:
            # Remote ChromaDB container (shared with RAG service)
            self.client = chromadb.HttpClient(
                host=chroma_host,
                port=chroma_port,
                settings=Settings(anonymized_telemetry=False),
            )
            self.persist_directory = f"remote://{chroma_host}:{chroma_port}"
            print(f"[ChromaWriter] Connected to remote ChromaDB: {chroma_host}:{chroma_port}")
        else:
            # Local persistence (dev mode)
            if persist_directory is None:
                persist_directory = os.getenv(
                    "CHROMA_PERSIST_DIR",
                    str(Path(__file__).parent.parent / "data" / "chromadb"),
                )

            Path(persist_directory).mkdir(parents=True, exist_ok=True)

            # ChromaDB Rust backend doesn't support non-ASCII paths on Windows
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
            print(f"[ChromaWriter] Using local persistence: {persist_directory}")

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "Bilibili video transcript and refinement knowledge base"},
        )

        self.collection_name = collection_name

    def add_documents(
        self,
        ids: List[str],
        documents: List[str],
        metadatas: Optional[List[dict]] = None,
    ):
        """Add documents to ChromaDB with embeddings."""
        embeddings = self.embeddings.embed_documents(documents)

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
        domain: str = "",
    ):
        """Add video content to ChromaDB."""
        doc_id = f"{bvid}_{hash(content) % 10000:04d}"

        metadata = {
            "bvid": bvid,
            "up_name": up_name,
            "title": title,
            "publish_date": publish_date,
            "category": category,
            "tags": tags,
            "domain": domain,
            "content_type": "full" if len(content) > 500 else "summary",
        }

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
        domain: str = "",
    ) -> int:
        """Add video content to ChromaDB in chunks (full text chunks + summary)."""
        ids = []
        documents = []
        metadatas = []

        base_meta = {
            "bvid": bvid,
            "up_name": up_name,
            "title": title,
            "publish_date": publish_date or "",
            "category": category or "",
            "domain": domain or "",
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
