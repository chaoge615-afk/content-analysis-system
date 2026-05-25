"""
结果融合模块
处理 hybrid 查询：将 SQL 结果和 RAG 结果融合为最终回答
"""

import re
from openai import OpenAI

from src.config import CHAT_API_KEY, CHAT_API_URL, CHAT_MODEL

MERGE_PROMPT = """你是一个智能问答助手。你将收到两个来源的信息：一个来自数据库查询的结构化结果，一个来自知识库的语义检索结果。
请综合这两个来源，给出一个完整、准确、自然的回答。

## 规则
1. 如果两个来源都有相关信息，综合起来回答
2. 如果数据库查询返回了空结果（如"没有找到相关数据"、结果数为0），但知识库有相关内容 → **直接使用知识库内容回答**，在开头可简要说明数据库暂无匹配数据
3. 如果知识库也没有内容，但数据库有结果 → 使用数据库结果回答
4. 如果两个来源都没有相关信息，如实告知用户
5. 不要编造信息
6. 回答要简洁自然，像人说话一样

## 用户问题
{question}

## 数据库查询结果（结构化数据）
{sql_result}

## 知识库检索结果（语义内容）
{rag_result}

## 请综合回答：
"""


class ResultMerger:
    """结果融合器"""

    def __init__(self):
        self.client = OpenAI(
            api_key=CHAT_API_KEY,
            base_url=CHAT_API_URL,
        )
        self.model = CHAT_MODEL

    def merge(
        self,
        question: str,
        sql_result: dict,
        rag_result: dict,
    ) -> str:
        """
        融合 SQL 和 RAG 结果

        Args:
            question: 用户原始问题
            sql_result: Text-to-SQL 返回结果
            rag_result: RAG 返回结果

        Returns:
            融合后的最终回答
        """
        # 格式化 SQL 结果
        sql_text = self._format_sql_result(sql_result)

        # 格式化 RAG 结果
        rag_text = self._format_rag_result(rag_result)

        # 如果两个都失败了，返回错误信息
        if not sql_result.get("success") and rag_result.get("error"):
            return f"抱歉，查询遇到问题：\n- 数据库：{sql_result.get('error', '未知错误')}\n- 知识库：{rag_result.get('error', '未知错误')}"

        # 如果只有 SQL 有结果
        if sql_result.get("success") and not rag_result.get("answer"):
            return sql_result.get("answer", "数据库查询完成但无结果")

        # 如果只有 RAG 有结果
        if not sql_result.get("success") and rag_result.get("answer"):
            return rag_result["answer"]

        # 新增：SQL 查询成功但返回空结果，而 RAG 有内容 → 直接用 RAG 结果
        if sql_result.get("success") and not sql_result.get("result") and rag_result.get("answer"):
            return (
                f"数据库中暂未找到匹配的结构化数据。"
                f"以下是知识库中的相关内容：\n\n{rag_result['answer']}"
            )

        # 调用 LLM 融合
        try:
            prompt = MERGE_PROMPT.format(
                question=question,
                sql_result=sql_text,
                rag_result=rag_text,
            )

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1000,
            )

            content = response.choices[0].message.content
            if content:
                content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
                return content

            return "LLM 融合失败，返回原始结果"

        except Exception as e:
            return f"结果融合失败: {str(e)}\n\nSQL 结果: {sql_text}\n\nRAG 结果: {rag_text}"

    @staticmethod
    def _format_sql_result(result: dict) -> str:
        """格式化 SQL 查询结果为可读文本"""
        if not result.get("success"):
            return f"查询失败: {result.get('error', '未知错误')}"

        answer = result.get("answer")
        if answer:
            return answer

        sql = result.get("sql", "")
        data = result.get("result", [])
        if not data:
            return "查询无结果"

        # 将结果数据格式化为表格
        lines = [f"SQL: {sql}", f"共 {len(data)} 条结果:"]
        for i, row in enumerate(data[:20]):  # 最多显示 20 行
            lines.append(f"  {i + 1}. {row}")
        if len(data) > 20:
            lines.append(f"  ... 还有 {len(data) - 20} 条")

        return "\n".join(lines)

    @staticmethod
    def _format_rag_result(result: dict) -> str:
        """格式化 RAG 结果"""
        answer = result.get("answer", "")
        if not answer:
            return "知识库未找到相关内容"
        return answer
