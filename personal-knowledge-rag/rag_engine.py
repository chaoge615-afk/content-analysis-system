"""
个人知识库RAG引擎
核心功能：加载markdown文件 → 分割chunk → 生成embedding → 存储到ChromaDB → 检索 + 生成回答
"""
import os
import requests
from typing import List, Dict
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_core.prompts import PromptTemplate
from langchain_core.embeddings import Embeddings

# 加载环境变量
load_dotenv()

class MinimaxEmbeddings(Embeddings):
    """SiliconFlow Embedding 适配"""
    def __init__(self, api_key: str, model: str = "BAAI/bge-large-zh-v1.5", base_url: str = "https://api.siliconflow.cn/v1"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量embed文档"""
        url = f"{self.base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "input": texts,
            "model": self.model
        }
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            result = response.json()

            # DeepSeek 返回格式: {"data": [{"embedding": [...]}]}
            if "data" in result:
                return [item["embedding"] for item in result["data"]]
            else:
                raise ValueError(f"Unexpected response format: {result}")
        except Exception as e:
            raise

    def embed_query(self, text: str) -> List[float]:
        """embed单个查询"""
        vectors = self.embed_documents([text])
        if not vectors or vectors[0] is None:
            raise ValueError("Embedding returned empty or None")
        return vectors[0]

class KnowledgeRAG:
    def __init__(self):
        # 从环境变量读取配置
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        self.group_id = os.getenv("MINIMAX_GROUP_ID")
        self.llm_model = os.getenv("LLM_MODEL", "MiniMax-M2.7")
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "embo-01")
        self.knowledge_dir = os.getenv("KNOWLEDGE_DIR", "./knowledge")
        self.persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
        self.chunk_size = int(os.getenv("CHUNK_SIZE", "500"))
        self.chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "50"))
        self.top_k = int(os.getenv("TOP_K", "5"))

        # API base URL，从环境变量读取
        self.base_url = os.getenv("BASE_URL", "https://api.minimaxi.com/anthropic")
        self.embedding_base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")

        # 初始化组件
        self._init_embeddings()
        self._init_llm()
        self._init_vector_db()
        self._init_prompt()

    def _init_embeddings(self):
        """初始化SiliconFlow embedding模型"""
        siliconflow_api_key = os.getenv("SILICONFLOW_API_KEY")
        if not siliconflow_api_key:
            raise ValueError("请在.env中配置SILICONFLOW_API_KEY")
        self.embeddings = MinimaxEmbeddings(
            api_key=siliconflow_api_key,
            model=self.embedding_model,
            base_url=self.embedding_base_url
        )

    def _init_llm(self):
        """初始化大语言模型"""
        # LLM 也需要GroupId吗？如果也是用Minimax OpenAI兼容格式，需要处理
        # 检查base_url是否需要追加group_id参数
        llm_base_url = self.base_url
        self.llm = ChatOpenAI(
            api_key=self.api_key,
            base_url=llm_base_url,
            model=self.llm_model,
            temperature=0.1,  # 知识问答温度低一点更准确
            extra_query={"GroupId": self.group_id} if self.group_id else {}
        )

    def _init_vector_db(self):
        """初始化Chroma向量数据库"""
        if os.path.exists(self.persist_dir) and len(os.listdir(self.persist_dir)) > 0:
            # 如果已有数据库，直接加载
            self.vector_db = Chroma(
                persist_directory=self.persist_dir,
                embedding_function=self.embeddings
            )
        else:
            # 新建空数据库
            self.vector_db = Chroma(
                persist_directory=self.persist_dir,
                embedding_function=self.embeddings
            )

    def _init_prompt(self):
        """初始化prompt模板"""
        # 自定义prompt，让回答更贴合知识库
        prompt_template = """你是一个基于用户个人知识库的问答助手。
请根据提供的上下文信息回答用户的问题。如果上下文中没有找到答案，请直接说"我在知识库中没有找到相关内容"。
不要编造信息，也不要引用无关内容。

上下文信息：
{context}

用户问题：{question}

回答："""

        self.prompt = PromptTemplate(
            template=prompt_template,
            input_variables=["context", "question"]
        )

    def load_knowledge(self) -> int:
        """加载knowledge目录下所有markdown文件，更新到向量库"""
        # 检查GroupId
        if not self.group_id:
            print("警告: MINIMAX_GROUP_ID 未配置，请检查 .env 文件", flush=True)
            return 0

        # 加载所有markdown文件
        loader = DirectoryLoader(
            self.knowledge_dir,
            glob="**/*.md",
            loader_cls=TextLoader,
            loader_kwargs={"encoding": "utf-8"}
        )

        documents = loader.load()
        if not documents:
            print(f"在 {self.knowledge_dir} 目录下没有找到任何markdown文件", flush=True)
            return 0

        print(f"找到 {len(documents)} 个markdown文件", flush=True)

        # 文本分块
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", "。", "，", " ", ""],
            keep_separator=True
        )

        chunks = text_splitter.split_documents(documents)
        print(f"分割为 {len(chunks)} 个文本块", flush=True)

        # 分批添加到向量库，避免请求过大导致413错误
        batch_size = 20
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            self.vector_db.add_documents(batch)
            print(f"已处理 {min(i + batch_size, len(chunks))}/{len(chunks)} 个文本块", flush=True)

        # ChromaDB 自动持久化，无需手动调用
        print(f"知识库更新完成，当前总共有 {self.vector_db._collection.count()} 个文档块", flush=True)

        return len(chunks)

    def clear_database(self):
        """清空向量数据库"""
        self.vector_db.delete_collection()
        self._init_vector_db()
        self._init_prompt()
        print("向量数据库已清空")

    def ask(self, question: str) -> str:
        """提问，获取回答"""
        if self.vector_db._collection.count() == 0:
            return "知识库还是空的，请先加载markdown文件"

        # 检索相关文档
        retriever = self.vector_db.as_retriever(search_kwargs={"k": self.top_k})
        docs = retriever.invoke(question)

        if not docs:
            return "没有找到相关文档，请尝试其他问题"

        # 拼接上下文
        context = "\n\n".join([doc.page_content for doc in docs])

        # 生成prompt
        prompt_text = self.prompt.format(context=context, question=question)

        # 调用LLM生成回答
        try:
            result = self.llm.invoke(prompt_text)
            if result is None:
                return "LLM返回了空结果，请检查API配置"

            content = result.content if hasattr(result, 'content') else str(result)
            if content is None:
                return "LLM返回的内容为空，请检查API配置"

            # 过滤掉思考过程标签
            import re
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            return content
        except Exception as e:
            return f"调用LLM时出错: {str(e)}"

    def get_stats(self) -> Dict:
        """获取知识库统计信息"""
        return {
            "total_chunks": self.vector_db._collection.count(),
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "top_k": self.top_k
        }
