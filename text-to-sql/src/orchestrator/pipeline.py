"""Main orchestration pipeline for Text-to-SQL Multi-Agent System."""

import json
from typing import Dict, Any, Tuple, Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.intent_agent import IntentAgent
from src.agents.schema_agent import SchemaAgent
from src.agents.sql_gen_agent import SQLGenAgent
from src.agents.review_agent import ReviewAgent
from src.database.duckdb_utils import execute_sql
from src.config import MAX_RETRIES
from src.llm_client import MiniMaxLLM
from src.prompts.templates import RESULT_FORMAT_PROMPT
from langchain_core.messages import HumanMessage


class TextToSQLPipeline:
    """Main pipeline orchestrating all agents."""

    def __init__(self):
        self.intent_agent = IntentAgent()
        self.schema_agent = SchemaAgent()
        self.sql_gen_agent = SQLGenAgent()
        self.review_agent = ReviewAgent()
        self.llm = MiniMaxLLM(temperature=0.3)

    def format_result(self, query_result: list, question: str, sql: str) -> str:
        """Format query result into natural language response using LLM."""
        if not query_result:
            return "没有找到相关数据。"

        # 将查询结果序列化为可读格式
        result_str = ""
        if len(query_result) == 1 and isinstance(query_result[0], tuple) and len(query_result[0]) == 1:
            result_str = str(query_result[0][0])
        else:
            result_str = "\n".join(str(row) for row in query_result)

        # 用 LLM 生成自然语言回答
        try:
            prompt = RESULT_FORMAT_PROMPT.format(
                question=question,
                query_result=result_str
            )
            answer = self.llm.invoke([HumanMessage(content=prompt)])
            return answer.strip()
        except Exception as e:
            # LLM 失败时降级为简单拼接
            return f"查询结果：{result_str}"

    # 静态 Schema（系统只有 2 张表，无需 LLM 调用）
    STATIC_SCHEMA = {
        "tables": [
            {
                "name": "video_meta",
                "description": "视频元数据表",
                "columns": ["bvid", "up_name", "up_uid", "title", "publish_date",
                           "category", "duration", "play_count", "summary", "tags", "created_at"]
            },
            {
                "name": "up_info",
                "description": "UP主信息表",
                "columns": ["uid", "name", "total_videos", "last_update",
                           "config_file", "created_at"]
            },
        ],
        "joins": ["video_meta.up_uid = up_info.uid"],
        "reasoning": "Static schema — only 2 tables in the system",
    }

    def _convert_router_intent(self, router_intent: dict, question: str) -> dict:
        """将 Router Agent 的意图格式转换为 T2S IntentAgent 格式。

        使用关键词启发式推断 query_target，无法推断时回退到 None（由 SQLGenAgent 自行判断）。
        """
        filters = router_intent.get("filters", {})

        # 启发式推断 query_target
        q = question.lower()
        if any(kw in q for kw in ["几个", "多少", "数量", "统计", "共有", "一共", "总数"]):
            query_target = "video_count"
            aggregation = "count"
        elif any(kw in q for kw in ["up主", "up 主", "博主", "有哪些人"]):
            query_target = "up_info"
            aggregation = "none"
        elif any(kw in q for kw in ["分类", "各分类"]):
            query_target = "category_stats"
            aggregation = "count"
        elif any(kw in q for kw in ["摘要", "总结", "内容", "聊了什么", "讲了什么"]):
            query_target = "video_summary"
            aggregation = "none"
        else:
            query_target = "video_list"
            aggregation = "none"

        # 转换 date_range
        date_range = None
        raw_date = filters.get("date_range", "")
        if raw_date:
            if "周" in str(raw_date) or "week" in str(raw_date).lower():
                date_range = {"type": "this_week"}
            elif "月" in str(raw_date) or "month" in str(raw_date).lower():
                date_range = {"type": "this_month"}
            elif "最近" in str(raw_date) or "recent" in str(raw_date).lower():
                date_range = {"type": "recent"}

        return {
            "query_type": "video",
            "query_target": query_target,
            "filters": {
                "up_name": filters.get("up_name"),
                "category": filters.get("category"),
                "date_range": date_range,
            },
            "aggregation": aggregation,
            "limit": 10,
        }

    def run(self, question: str, pre_intent: Optional[dict] = None) -> Dict[str, Any]:
        """
        Run the full pipeline for a user question.

        Args:
            question: 用户问题
            pre_intent: 来自 Router Agent 的预分类意图（可选，提供后跳过 IntentAgent）

        Returns:
            Dict with keys: success, sql, result, answer, error, iterations
        """
        iterations = 0
        last_error = None
        sql = None

        while iterations < MAX_RETRIES:
            iterations += 1

            # Step 1: Intent Understanding（有 pre_intent 时跳过 LLM 调用）
            if pre_intent:
                intent = self._convert_router_intent(pre_intent, question)
                print(f"[Pipeline] 使用 Router 预分类意图: query_target={intent['query_target']}")
            else:
                intent = self.intent_agent.run(question)
            if "error" in intent:
                return {
                    "success": False,
                    "error": f"Intent parsing failed: {intent['error']}",
                    "iterations": iterations,
                }

            # Step 2: Schema Retrieval（使用静态 schema，跳过 LLM 调用）
            schema = self.STATIC_SCHEMA

            # Step 3: SQL Generation（重试时传入上次错误作为提示）
            sql_result = self.sql_gen_agent.run(intent, schema, retry_hint=last_error)
            if "error" in sql_result:
                return {
                    "success": False,
                    "error": f"SQL generation failed: {sql_result['error']}",
                    "iterations": iterations,
                }

            sql = sql_result.get("sql", "")
            if not sql:
                return {
                    "success": False,
                    "error": "No SQL generated",
                    "iterations": iterations,
                }

            # Step 4: SQL Review
            review = self.review_agent.run(sql, intent, schema)
            if review.get("passed", False):
                # SQL passed review, execute it
                try:
                    query_result = execute_sql(sql)
                    answer = self.format_result(query_result, question, sql)
                    return {
                        "success": True,
                        "sql": sql,
                        "result": query_result,
                        "answer": answer,
                        "iterations": iterations,
                    }
                except Exception as e:
                    last_error = f"SQL execution failed: {e}"
            else:
                # SQL failed review, get error info
                issues = review.get("issues", [])
                error_msgs = [f"- {issue['description']} (suggestion: {issue.get('suggestion', 'N/A')})" for issue in issues]
                last_error = "SQL 审查未通过，问题如下：\n" + "\n".join(error_msgs)

        # Max retries exceeded
        return {
            "success": False,
            "sql": sql,
            "error": f"重试次数已达上限 ({MAX_RETRIES})。最后错误: {last_error}",
            "iterations": iterations,
        }


def query(question: str) -> Dict[str, Any]:
    """Convenience function to run a single query."""
    pipeline = TextToSQLPipeline()
    return pipeline.run(question)
