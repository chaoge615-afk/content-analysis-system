"""Intent Understanding Agent - Agent 1."""

import json
from datetime import date
from langchain_core.messages import HumanMessage, SystemMessage

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.llm_client import MiniMaxLLM
from src.prompts.templates import INTENT_SYSTEM_PROMPT, INTENT_USER_PROMPT


class IntentAgent:
    """Agent 1: 意图理解 - 把用户自然语言问题转成结构化的查询意图."""

    def __init__(self):
        self.llm = MiniMaxLLM(temperature=0.1)

    def parse(self, question: str) -> dict:
        """Parse user question into structured intent."""
        today = date.today()
        system_prompt = INTENT_SYSTEM_PROMPT.format(
            current_date=today.isoformat(),
            current_year=today.year
        )
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=INTENT_USER_PROMPT.format(question=question)),
        ]

        content = self.llm.invoke(messages)

        # Parse JSON from response
        try:
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]

            intent = json.loads(content.strip())
            return intent
        except json.JSONDecodeError as e:
            return {
                "error": f"Failed to parse intent: {e}",
                "raw_response": content,
            }

    def run(self, question: str) -> dict:
        """Run the agent and return structured intent."""
        return self.parse(question)
