"""
意图分类模块
使用 MiniMax LLM 对用户问题进行意图分类，并提取过滤条件

分类结果：
- structured: 结构化查询 → Text-to-SQL（统计数据、列表查询、计数等）
- semantic: 语义查询 → RAG（观点、建议、知识内容等）
- hybrid: 混合查询 → 两者并行 + LLM 融合
"""

import json
import re
from typing import Optional
from openai import OpenAI

from src.config import CHAT_API_KEY, CHAT_API_URL, CHAT_MODEL

INTENT_CLASSIFY_PROMPT = """你是一个智能意图分类器。根据用户的问题，判断查询类型并提取过滤条件。

## 分类规则

### structured（结构化查询）→ 走 Text-to-SQL
适用于可以用数据库查询回答的问题：
- 视频数量统计（"桃姐有几个视频？"）
- UP 主信息（"有哪些 UP 主？"）
- 视频列表（"最近发布了什么视频？"）
- 分类统计（"各分类有多少视频？"）
- 时间范围查询（"这周发布了几个视频？"）
- 视频元数据查询（"某个视频的时长/发布日期"）

### semantic（语义查询）→ 走 RAG
适用于需要理解内容含义的问题：
- 观点/建议查询（"博主们对冷暴力怎么看？"）
- 情感/关系建议（"怎么改善沟通？"）
- 知识内容查询（"关于吵架有什么好的建议？"）
- 概念解释（"什么是情感操控？"）

### hybrid（混合查询）→ 两者并行
同时包含结构化和语义需求的问题：
- "桃姐最近聊了什么？她关于吵架的建议？"（需要知道桃姐的视频 + 她的具体观点）
- "最近一周有什么关于沟通的新内容？"（需要时间过滤 + 内容理解）

## 过滤条件提取
从问题中提取以下过滤条件（如果提到的话）：
- up_name: UP 主名称（只在问题中明确提到某位 UP 主时提取）
- category: 视频分类（**只能从以下有效分类中选择**，不要用话题关键词作为分类）：
  01_喜欢, 02_聊天, 03_撩妹, 04_筛选, 05_拒绝, 06_备胎, 07_修养, 08_婚姻,
  09_推进, 10_分手, 11_话术, 12_深夜, 13_表白, 14_约会, 15_复合, 16_社交,
  17_暧昧, 18_生理, 19_挽回, 20_出轨, 21_相亲, 22_追求, 23_回复, 24_心态,
  25_情商, 26_吸引力, 27_恋爱技巧, 28_技巧, 29_感情, 30_两性知识, 31_自我提升, 32_两性健康
  如果问题没有明确提到某个分类，**不要设置 category**，改用 keywords
- date_range: 时间范围（如 最近、本周、本月）
- keywords: 关键词（用于语义搜索，如 冷暴力、吵架、沟通 等话题词）

**重要：category 是目录分类名，不是话题关键词。"冷暴力"是话题（用 keywords），不是分类。**

## 输出格式
严格输出 JSON，不要包含其他内容：
{
    "route_type": "structured|semantic|hybrid",
    "filters": {
        "up_name": "UP主名称（可选）",
        "category": "分类（可选）",
        "date_range": "时间范围（可选）",
        "keywords": "关键词（可选）"
    },
    "reasoning": "分类理由（一句话）"
}

## 示例

用户："桃姐最近发了几个视频？"
{"route_type": "structured", "filters": {"up_name": "桃姐", "date_range": "最近"}, "reasoning": "查询特定UP主的视频数量，是结构化统计查询"}

用户："博主们对冷暴力怎么看？"
{"route_type": "semantic", "filters": {"keywords": "冷暴力"}, "reasoning": "查询博主观点和建议，需要语义理解，冷暴力是话题关键词而非分类"}

用户："桃姐关于吵架有什么建议？"
{"route_type": "hybrid", "filters": {"up_name": "桃姐", "keywords": "吵架"}, "reasoning": "需要找桃姐的视频（结构化）+ 理解她关于吵架的建议（语义）"}

用户："喜欢分类下有什么内容？"
{"route_type": "semantic", "filters": {"category": "01_喜欢"}, "reasoning": "明确提到喜欢分类，使用 category 过滤"}

用户："一共有多少个视频？"
{"route_type": "structured", "filters": {}, "reasoning": "简单统计查询"}
"""


class IntentClassifier:
    """意图分类器"""

    def __init__(self):
        self.client = OpenAI(
            api_key=CHAT_API_KEY,
            base_url=CHAT_API_URL,
        )
        self.model = CHAT_MODEL

    def classify(self, question: str) -> dict:
        """
        对用户问题进行意图分类

        Returns:
            {
                "route_type": "structured" | "semantic" | "hybrid",
                "filters": { ... },
                "reasoning": "..."
            }
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": INTENT_CLASSIFY_PROMPT},
                    {"role": "user", "content": question},
                ],
                temperature=0.1,
                max_tokens=500,
            )

            content = response.choices[0].message.content
            if content is None:
                return self._default_result()

            # 过滤思考标签
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

            # 解析 JSON
            return self._parse_response(content)

        except Exception as e:
            print(f"[意图分类] 调用 LLM 失败: {e}")
            return self._default_result()

    def _parse_response(self, content: str) -> dict:
        """解析 LLM 返回的 JSON"""
        try:
            # 尝试直接解析
            result = json.loads(content)
        except json.JSONDecodeError:
            # 尝试从 markdown code block 中提取
            json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    return self._default_result()
            else:
                # 尝试找到第一个 { ... }
                brace_match = re.search(r"\{.*\}", content, re.DOTALL)
                if brace_match:
                    try:
                        result = json.loads(brace_match.group())
                    except json.JSONDecodeError:
                        return self._default_result()
                else:
                    return self._default_result()

        # 验证必填字段
        route_type = result.get("route_type", "semantic")
        if route_type not in ("structured", "semantic", "hybrid"):
            route_type = "semantic"

        return {
            "route_type": route_type,
            "filters": result.get("filters", {}),
            "reasoning": result.get("reasoning", ""),
        }

    @staticmethod
    def _default_result() -> dict:
        """默认分类结果（降级到语义查询）"""
        return {
            "route_type": "semantic",
            "filters": {},
            "reasoning": "分类失败，降级到语义查询",
        }
