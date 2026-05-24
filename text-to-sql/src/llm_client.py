"""LLM client utility for MiniMax (Anthropic-compatible API)."""

import anthropic
from typing import List, Union
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.config import MINIMAX_API_KEY, MINIMAX_BASE_URL, MODEL_NAME


class MiniMaxLLM:
    """MiniMax LLM client using Anthropic-compatible API."""

    def __init__(self, model: str = None, temperature: float = 0.1):
        self.model = model or MODEL_NAME
        self.temperature = temperature
        self.client = anthropic.Anthropic(
            api_key=MINIMAX_API_KEY,
            base_url=MINIMAX_BASE_URL,
        )

    def invoke(self, messages: List[Union[str, BaseMessage]]) -> str:
        """Invoke the LLM with messages and return the response content."""
        # Convert langchain messages to Anthropic format
        system_msg = ""
        anthropic_messages = []

        for msg in messages:
            if isinstance(msg, SystemMessage):
                system_msg = msg.content
            elif isinstance(msg, HumanMessage):
                anthropic_messages.append({
                    "role": "user",
                    "content": msg.content
                })

        response = self.client.messages.create(
            model=self.model,
            system=system_msg,
            messages=anthropic_messages,
            temperature=self.temperature,
            max_tokens=2048,
        )
        # Handle different content block types
        for block in response.content:
            if block.type == "text":
                return block.text
        return str(response.content)

    def __call__(self, messages: List[Union[str, BaseMessage]]) -> str:
        """Allow calling the client as a function."""
        return self.invoke(messages)
