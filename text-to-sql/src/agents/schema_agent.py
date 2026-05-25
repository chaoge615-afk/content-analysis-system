"""Schema Retrieval Agent - Agent 2."""

import json
from langchain_core.messages import HumanMessage, SystemMessage

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.llm_client import MiniMaxLLM
from src.prompts.templates import SCHEMA_SYSTEM_PROMPT, SCHEMA_USER_PROMPT


class SchemaAgent:
    """Agent 2: Schema 检索 - 根据意图从数据库中找到相关的表和字段."""

    def __init__(self):
        self.llm = MiniMaxLLM(temperature=0.1)

    def retrieve(self, intent: dict) -> dict:
        """Retrieve relevant schema information based on intent."""
        if "error" in intent:
            return {"error": f"Cannot retrieve schema due to intent error: {intent['error']}"}

        messages = [
            SystemMessage(content=SCHEMA_SYSTEM_PROMPT),
            HumanMessage(content=SCHEMA_USER_PROMPT.format(intent=json.dumps(intent, ensure_ascii=False))),
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

            schema = json.loads(content.strip())
            return schema
        except json.JSONDecodeError as e:
            return {
                "error": f"Failed to parse schema: {e}",
                "raw_response": content,
            }

    def run(self, intent: dict) -> dict:
        """Run the agent and return schema information."""
        return self.retrieve(intent)
