"""SQL Generation Agent - Agent 3."""

import json
from langchain_core.messages import HumanMessage, SystemMessage

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.llm_client import MiniMaxLLM
from src.prompts.templates import SQL_GEN_SYSTEM_PROMPT, SQL_GEN_USER_PROMPT


class SQLGenAgent:
    """Agent 3: SQL 生成 - 根据意图 + Schema 信息生成可执行的 SQL."""

    def __init__(self):
        self.llm = MiniMaxLLM(temperature=0.1)

    def generate(self, intent: dict, schema: dict, retry_hint: str = None) -> dict:
        """Generate SQL based on intent and schema.

        Args:
            intent: 结构化查询意图
            schema: Schema 信息
            retry_hint: 上次失败的错误信息，用于重试时纠正
        """
        if "error" in intent:
            return {"error": f"Cannot generate SQL due to intent error: {intent['error']}"}
        if "error" in schema:
            return {"error": f"Cannot generate SQL due to schema error: {schema['error']}"}

        user_content = SQL_GEN_USER_PROMPT.format(
            intent=json.dumps(intent, ensure_ascii=False),
            schema=json.dumps(schema, ensure_ascii=False)
        )

        # 重试时附加错误提示，让 LLM 纠正上次的问题
        if retry_hint:
            user_content += f"\n\n## 上次生成的 SQL 有误，请修正\n{retry_hint}"

        messages = [
            SystemMessage(content=SQL_GEN_SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ]

        content = self.llm.invoke(messages)

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
                "error": f"Failed to parse SQL: {e}",
                "raw_response": content,
            }

    def run(self, intent: dict, schema: dict, retry_hint: str = None) -> dict:
        """Run the agent and return generated SQL."""
        return self.generate(intent, schema, retry_hint)
