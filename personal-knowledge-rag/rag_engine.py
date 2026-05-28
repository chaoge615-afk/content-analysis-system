"""
视频知识库RAG引擎
核心功能：
  - video_knowledge collection（B站视频精炼）
  - metadata 过滤检索（按 UP主、分类、日期等）
  - BM25 + 向量混合检索
"""

import os
import re
import anthropic
import openai
from typing import List, Dict, Optional
from pathlib import Path
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document

# 混合检索模块
from hybrid_search import BM25, HybridSearch

# 共享 Embeddings 模块（shared/ 目录）
import sys
_SHARED_DIR = str(Path(__file__).parent.parent / "shared")
if _SHARED_DIR not in sys.path:
    sys.path.insert(0, _SHARED_DIR)
from shared_embeddings import SiliconFlowEmbeddings

# 加载环境变量
load_dotenv()


def extract_video_metadata(file_path: str) -> dict:
    """
    从文件路径提取视频 metadata
    文件命名约定: {bvid}_{title}.txt 或 {title}.txt
    目录结构: <base_dir>/<category>/xxx.txt
    """
    path = Path(file_path)
    metadata = {
        "content_type": "full",
        "source": str(file_path),
    }

    # 从文件名提取 bvid（BV 开头的 ID）
    filename = path.stem  # 不含扩展名
    bvid_match = re.search(r'(BV[a-zA-Z0-9]+)', filename)
    if bvid_match:
        metadata["bvid"] = bvid_match.group(1)

    # 从目录名提取分类（如 01_喜欢、02_沟通 等）
    parent = path.parent.name
    if parent and parent != ".":
        metadata["category"] = parent

    # 从文件名提取 UP 主名（如果有）
    # 常见格式: up_name_bvid_title.txt 或 bvid_title.txt
    parts = filename.split("_")
    if len(parts) >= 3 and not parts[0].startswith("BV"):
        # 第一段不是 BV 开头，可能是 UP 主名
        metadata["up_name"] = parts[0]

    return metadata


class KnowledgeRAG:
    def __init__(self):
        # 从环境变量读取配置
        self.api_key = os.getenv("MINIMAX_API_KEY")
        self.group_id = os.getenv("MINIMAX_GROUP_ID")
        self.llm_model = os.getenv("LLM_MODEL", "MiniMax-M2.7")
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5")
        self.persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
        self.chunk_size = int(os.getenv("CHUNK_SIZE", "500"))
        self.chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "50"))
        self.top_k = int(os.getenv("TOP_K", "5"))

        # 视频知识库目录
        self.video_knowledge_dir = os.getenv(
            "VIDEO_KNOWLEDGE_DIR", "./video_knowledge"
        )

        # ChromaDB 远程连接（用于 video_knowledge collection）
        self.chroma_host = os.getenv("CHROMA_HOST")  # 如 "localhost"
        self.chroma_port = int(os.getenv("CHROMA_PORT", "8000"))

        # API base URL
        self.base_url = os.getenv("BASE_URL", "https://api.minimaxi.com/anthropic")
        self.embedding_base_url = os.getenv(
            "SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1"
        )

        # LLM 提供者选择：minimax（默认）或 deepseek
        self.llm_provider = os.getenv("LLM_PROVIDER", "minimax")
        if self.llm_provider == "deepseek":
            self.deepseek_api_key = os.getenv("REFINE_API_KEY", "")
            self.deepseek_base_url = os.getenv("REFINE_API_URL", "http://10.168.165.50:3300/v1")
            # REFINE_API_URL 指向 /v1/chat/completions，OpenAI SDK 需要 /v1
            if self.deepseek_base_url.endswith("/chat/completions"):
                self.deepseek_base_url = self.deepseek_base_url.rsplit("/chat/completions", 1)[0]

        # 混合检索
        self._hybrid_search = HybridSearch(rank_cap=3)
        self._video_bm25: Optional[BM25] = None

        # 初始化组件
        self._init_embeddings()
        self._init_llm()
        self._init_vector_db()
        self._init_prompt()

    def _init_embeddings(self):
        """初始化 SiliconFlow embedding 模型"""
        siliconflow_api_key = os.getenv("SILICONFLOW_API_KEY")
        if not siliconflow_api_key:
            raise ValueError("请在 .env 中配置 SILICONFLOW_API_KEY")
        self.embeddings = SiliconFlowEmbeddings(
            api_key=siliconflow_api_key,
            model=self.embedding_model,
            base_url=self.embedding_base_url,
        )

    def _init_llm(self):
        """初始化大语言模型（支持 MiniMax/anthropic 和 DeepSeek/openai 两种接口）"""
        if self.llm_provider == "deepseek":
            if not self.deepseek_api_key:
                raise ValueError("请在 .env 中配置 REFINE_API_KEY（DeepSeek API Key）")
            self.llm = openai.OpenAI(
                api_key=self.deepseek_api_key,
                base_url=self.deepseek_base_url,
            )
            print(f"[RAG] LLM 使用 DeepSeek: {self.deepseek_base_url} ({self.llm_model})")
        else:
            if not self.api_key:
                raise ValueError("请在 .env 中配置 MINIMAX_API_KEY（MiniMax API Key）")
            self.llm = anthropic.Anthropic(
                api_key=self.api_key,
                base_url=self.base_url,
            )
            print(f"[RAG] LLM 使用 MiniMax: {self.base_url} ({self.llm_model})")

    def _init_vector_db(self):
        """初始化 ChromaDB 向量数据库（video_knowledge collection）"""
        if self.chroma_host:
            # 远程 ChromaDB 容器
            import chromadb

            remote_client = chromadb.HttpClient(
                host=self.chroma_host, port=self.chroma_port
            )
            self.video_vector_db = Chroma(
                client=remote_client,
                collection_name="video_knowledge",
                embedding_function=self.embeddings,
            )
            print(
                f"[RAG] video_knowledge 连接远程 ChromaDB: {self.chroma_host}:{self.chroma_port}"
            )
        else:
            # 本地持久化（开发模式）
            video_persist_dir = os.path.join(self.persist_dir, "_video")
            self.video_vector_db = Chroma(
                collection_name="video_knowledge",
                persist_directory=video_persist_dir,
                embedding_function=self.embeddings,
            )
            print(f"[RAG] video_knowledge 使用本地持久化: {video_persist_dir}")

    def _init_prompt(self):
        """初始化 prompt 模板（拆分为静态系统指令 + 动态用户内容）"""
        # 静态系统指令（可缓存）
        self.system_prompt = """你是一个基于用户个人知识库的问答助手。
请根据提供的上下文信息回答用户的问题。如果上下文中没有找到答案，请直接说"我在知识库中没有找到相关内容"。
不要编造信息，也不要引用无关内容。"""

        # 动态用户内容模板
        self.user_template = """上下文信息：
{context}

用户问题：{question}

回答："""

        # 保留旧的 PromptTemplate 以兼容 DeepSeek 路径
        prompt_template = self.system_prompt + "\n\n" + self.user_template
        self.prompt = PromptTemplate(
            template=prompt_template, input_variables=["context", "question"]
        )

    # ========== 知识库加载 ==========

    def load_video_knowledge(self, source_dir: str = None) -> int:
        """
        加载视频精炼内容到 video_knowledge collection
        自动从文件名/路径提取 metadata（bvid、up_name、category 等）

        Args:
            source_dir: 视频精炼文件目录，默认使用 VIDEO_KNOWLEDGE_DIR 环境变量
        """
        source_dir = source_dir or self.video_knowledge_dir

        if not os.path.exists(source_dir):
            print(f"视频知识目录不存在: {source_dir}", flush=True)
            return 0

        # 加载所有 txt 文件
        loader = DirectoryLoader(
            source_dir,
            glob="**/*.txt",
            loader_cls=TextLoader,
            loader_kwargs={"encoding": "utf-8"},
        )

        documents = loader.load()
        if not documents:
            print(f"在 {source_dir} 目录下没有找到任何 txt 文件", flush=True)
            return 0

        print(f"找到 {len(documents)} 个视频精炼文件", flush=True)

        # 文本分块（视频精炼内容通常较短，用较小的 chunk_size）
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", "。", "，", " ", ""],
            keep_separator=True,
        )

        chunks = text_splitter.split_documents(documents)

        # 为每个 chunk 附加 metadata
        for idx, chunk in enumerate(chunks):
            source = chunk.metadata.get("source", "")
            video_meta = extract_video_metadata(source)
            chunk.metadata.update(video_meta)
            # 标记 chunk 在原文中的序号
            chunk.metadata["chunk_index"] = idx

        print(f"分割为 {len(chunks)} 个文本块（含 metadata）", flush=True)

        # 分批添加到 video_knowledge collection
        batch_size = 20
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            self.video_vector_db.add_documents(batch)
            print(
                f"已处理 {min(i + batch_size, len(chunks))}/{len(chunks)} 个文本块",
                flush=True,
            )

        # 清空 BM25 缓存，下次搜索时重建
        self._video_bm25 = None

        count = self.video_vector_db._collection.count()
        print(f"视频知识库更新完成，当前总共有 {count} 个文档块", flush=True)
        return len(chunks)

    # ========== 检索 ==========

    def _get_video_docs_text(self) -> List[str]:
        """获取 video_knowledge 所有文档的文本（用于 BM25 索引）"""
        try:
            results = self.video_vector_db._collection.get()
            return results.get("documents", [])
        except Exception as e:
            print(f"[RAG] 获取视频文档失败: {e}")
            return []

    def ask_video(
        self,
        question: str,
        metadata_filter: dict = None,
        use_hybrid: bool = True,
    ) -> str:
        """
        针对 video_knowledge 的问答（支持 metadata 过滤 + 混合检索）

        Args:
            question: 用户问题
            metadata_filter: 过滤条件，如 {"up_name": "桃姐", "category": "01_喜欢"}
            use_hybrid: 是否使用 BM25+向量混合检索
        """
        if self.video_vector_db._collection.count() == 0:
            return "视频知识库还是空的，请先加载视频精炼内容"

        # 提取 keywords 用于增强查询文本（不传给 ChromaDB where filter）
        query_text = question
        metadata_filter = dict(metadata_filter or {})
        if "keywords" in metadata_filter:
            kw = metadata_filter.pop("keywords", "")
            if kw:
                query_text = f"{question} {kw}"

        # 构建 ChromaDB where 过滤条件（不含 keywords）
        where_filter = self._build_where_filter(metadata_filter)

        if use_hybrid:
            docs = self._hybrid_search_video(query_text, where_filter)
        else:
            # 纯向量检索
            search_kwargs = {"k": self.top_k}
            if where_filter:
                search_kwargs["filter"] = where_filter
            retriever = self.video_vector_db.as_retriever(
                search_kwargs=search_kwargs
            )
            docs = retriever.invoke(query_text)

        if not docs:
            return "在视频知识库中没有找到相关内容"

        # 拼接上下文（附带来源信息）
        context_parts = []
        for doc in docs:
            meta = doc.metadata
            source_info = ""
            if meta.get("up_name"):
                source_info += f"[UP主: {meta['up_name']}] "
            if meta.get("category"):
                source_info += f"[分类: {meta['category']}] "
            if meta.get("bvid"):
                source_info += f"[BV号: {meta['bvid']}] "
            context_parts.append(
                f"{source_info}\n{doc.page_content}" if source_info else doc.page_content
            )

        context = "\n\n---\n\n".join(context_parts)

        # 生成动态用户内容
        user_content = self.user_template.format(context=context, question=question)

        # 调用 LLM
        try:
            if self.llm_provider == "deepseek":
                # DeepSeek（OpenAI SDK）— 不支持 prompt caching，保持原有方式
                prompt_text = self.system_prompt + "\n\n" + user_content
                response = self.llm.chat.completions.create(
                    model=self.llm_model,
                    max_tokens=2048,
                    temperature=0.1,
                    messages=[{"role": "user", "content": prompt_text}],
                )
                content = response.choices[0].message.content if response.choices else ""
            else:
                # MiniMax（Anthropic SDK）— 使用 prompt caching
                response = self.llm.messages.create(
                    model=self.llm_model,
                    max_tokens=2048,
                    temperature=0.1,
                    system=[
                        {
                            "type": "text",
                            "text": self.system_prompt,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    messages=[{"role": "user", "content": user_content}],
                )
                # 提取文本内容（过滤掉 ThinkingBlock 等非文本块）
                text_parts = []
                for block in response.content:
                    if hasattr(block, 'text'):
                        text_parts.append(block.text)
                content = "\n".join(text_parts) if text_parts else ""
            if not content:
                return "LLM 返回的内容为空，请检查 API 配置"

            # 过滤掉思考过程标签
            content = re.sub(
                r"<think>.*?</think>", "", content, flags=re.DOTALL
            ).strip()
            return content
        except Exception as e:
            return f"调用 LLM 时出错: {str(e)}"

    def ask(
        self,
        question: str,
        collection: str = "video_knowledge",
        metadata_filter: dict = None,
    ) -> str:
        """
        通用问答方法

        Args:
            question: 用户问题
            collection: 目前仅支持 "video_knowledge"
            metadata_filter: 过滤条件
        """
        return self.ask_video(question, metadata_filter=metadata_filter)

    def _hybrid_search_video(
        self, question: str, where_filter: dict = None
    ) -> List[Document]:
        """BM25 + 向量混合检索视频知识库"""
        # 懒加载 BM25 索引
        if self._video_bm25 is None:
            print("[混合检索] 构建 BM25 索引...", flush=True)
            docs_text = self._get_video_docs_text()
            if docs_text:
                self._video_bm25 = self._hybrid_search.build_bm25_index(docs_text)
                print(
                    f"[混合检索] BM25 索引构建完成，{len(docs_text)} 个文档",
                    flush=True,
                )

        # 获取所有文档的 metadata（用于过滤）
        all_docs_data = self.video_vector_db._collection.get(include=["documents", "metadatas"])
        all_documents = all_docs_data.get("documents", [])
        all_metadatas = all_docs_data.get("metadatas", [])

        # 构建向量检索回调
        def vector_search_fn(query, top_k):
            search_kwargs = {"k": top_k}
            if where_filter:
                search_kwargs["filter"] = where_filter
            retriever = self.video_vector_db.as_retriever(
                search_kwargs=search_kwargs
            )
            docs = retriever.invoke(query)
            # 将检索结果映射回全局索引
            results = []
            for doc in docs:
                try:
                    idx = all_documents.index(doc.page_content)
                    # 计算简单的相似度分数（用排名代替）
                    results.append((1.0 / (len(results) + 1), idx))
                except ValueError:
                    continue
            return results

        # 执行混合检索
        fusion_results = self._hybrid_search.search(
            query=question,
            bm25=self._video_bm25,
            vector_search_fn=vector_search_fn,
            top_k=self.top_k,
        )

        # 将结果转换为 Document 列表
        result_docs = []
        for doc_idx, score in fusion_results:
            if doc_idx < len(all_documents):
                meta = all_metadatas[doc_idx] if doc_idx < len(all_metadatas) else {}

                # 应用 metadata 过滤
                if where_filter and not self._matches_filter(meta, where_filter):
                    continue

                result_docs.append(
                    Document(
                        page_content=all_documents[doc_idx],
                        metadata=meta,
                    )
                )

        return result_docs

    @staticmethod
    def _build_where_filter(metadata_filter: dict) -> Optional[dict]:
        """
        将简单的 metadata_filter 转换为 ChromaDB where 条件

        支持的过滤字段: up_name, category, bvid
        """
        if not metadata_filter:
            return None

        conditions = []
        for key, value in metadata_filter.items():
            if not value:
                continue
            if key in ("up_name", "category", "bvid", "content_type"):
                conditions.append({key: {"$eq": value}})

        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    @staticmethod
    def _matches_filter(metadata: dict, where_filter: dict) -> bool:
        """检查 metadata 是否匹配 where 过滤条件"""
        if "$and" in where_filter:
            return all(
                KnowledgeRAG._matches_filter(metadata, cond)
                for cond in where_filter["$and"]
            )
        for key, condition in where_filter.items():
            if key.startswith("$"):
                continue
            if isinstance(condition, dict) and "$eq" in condition:
                if metadata.get(key) != condition["$eq"]:
                    return False
            elif metadata.get(key) != condition:
                return False
        return True

    # ========== 统计 & 管理 ==========

    def get_stats(self) -> Dict:
        """获取知识库统计信息"""
        video_count = self.video_vector_db._collection.count()

        return {
            "video_chunks": video_count,
            "total_chunks": video_count,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "top_k": self.top_k,
            "collections": {
                "video_knowledge": {
                    "name": "video_knowledge",
                    "count": video_count,
                    "type": "remote" if self.chroma_host else "local",
                    "host": f"{self.chroma_host}:{self.chroma_port}"
                    if self.chroma_host
                    else "local",
                },
            },
        }

    def get_collections(self) -> List[Dict]:
        """获取所有 collection 信息"""
        stats = self.get_stats()
        return list(stats["collections"].values())

    def clear_database(self, collection: str = "video_knowledge"):
        """
        清空指定的 collection

        Args:
            collection: "video_knowledge"
        """
        self.video_vector_db.delete_collection()
        self._video_bm25 = None
        # 重新初始化
        self._init_vector_db()
        print("视频知识库已清空")
