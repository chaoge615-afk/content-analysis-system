"""SQL Review Agent - Agent 4."""

import json
from langchain_core.messages import HumanMessage, SystemMessage

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.llm_client import MiniMaxLLM
from src.prompts.templates import REVIEW_SYSTEM_PROMPT, REVIEW_USER_PROMPT


class ReviewAgent:
    """Agent 4: SQL 审查 - 检查生成的 SQL 是否正确、合理."""

    def __init__(self):
        self.llm = MiniMaxLLM(temperature=0.1)

    def review(self, sql: str, intent: dict, schema: dict) -> dict:
        """Review the generated SQL."""
        if isinstance(sql, dict) and "error" in sql:
            return {"passed": False, "issues": [{"severity": "error", "type": "syntax", "description": sql["error"]}]}

        messages = [
            SystemMessage(content=REVIEW_SYSTEM_PROMPT),
            HumanMessage(content=REVIEW_USER_PROMPT.format(
                sql=sql,
                intent=json.dumps(intent, ensure_ascii=False),
                schema=json.dumps(schema, ensure_ascii=False)
            )),
        ]

        content = self.llm.invoke(messages, cache_system=True)

        try:
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]

            result = json.loads(content.strip())
            return result
        except json.JSONDecodeError as e:
            return {
                "passed": False,
                "issues": [{"severity": "error", "type": "syntax", "description": f"Failed to parse review: {e}"}],
                "raw_response": content,
            }

    def run(self, sql: str, intent: dict, schema: dict) -> dict:
        """Run the agent and return review result."""
        return self.review(sql, intent, schema)

    def is_passed(self, review_result: dict) -> bool:
        """Check if the SQL passed the review."""
        return review_result.get("passed", False)
