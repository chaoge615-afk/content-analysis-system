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
import time
from difflib import SequenceMatcher
from typing import Optional
import anthropic

from src.config import CHAT_API_KEY, CHAT_API_URL, CHAT_MODEL, DUCKDB_PATH

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
- up_name: UP 主名称。**重要**：
  - 用户可能使用简称/昵称（如"桃姐"、"安佳"、"啊柚"），你必须将其标准化为已知UP主完整名称列表中的完整名称
  - **不要将用户输入的简称直接作为 up_name 的值**，而应匹配到完整名称
  - 如果用户名无法匹配任何已知UP主的完整名称，则**不要设置 up_name**，改用 keywords 记录用户提到的名称
  - 例如：用户说"桃姐" → up_name 应设为 "恋爱教头桃姐"
  - 例如：用户说"小桃" → 无法匹配任何已知UP主 → 不设 up_name，keywords="小桃"
- category: 视频分类（**只能从以下有效分类中选择**，不要用话题关键词作为分类）：
  01_喜欢, 02_聊天, 03_撩妹, 04_筛选, 05_拒绝, 06_备胎, 07_修养, 08_婚姻,
  09_推进, 10_分手, 11_话术, 12_深夜, 13_表白, 14_约会, 15_复合, 16_社交,
  17_暧昧, 18_生理, 19_挽回, 20_出轨, 21_相亲, 22_追求, 23_回复, 24_心态,
  25_情商, 26_吸引力, 27_恋爱技巧, 28_技巧, 29_感情, 30_两性知识, 31_自我提升, 32_两性健康
  如果问题没有明确提到某个分类，**不要设置 category**，改用 keywords
- date_range: 时间范围（如 最近、本周、本月）
- keywords: 关键词（用于语义搜索，如 冷暴力、吵架、沟通 等话题词）

**重要：category 是目录分类名，不是话题关键词。"冷暴力"是话题（用 keywords），不是分类。**

**极其重要 - up_name 标准化规则：**
- up_name 字段的值**必须**从"已知UP主完整名称列表"中选择，**绝对不能**使用用户输入的原始简称
- ✅ 正确：up_name = "恋爱教头桃姐"（从列表中选择）
- ❌ 错误：up_name = "桃姐"（用户的原始输入，不在列表中）
- 如果你在 reasoning 中说"桃姐标准化为恋爱教头桃姐"，那 up_name 就必须是 "恋爱教头桃姐"

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
{"route_type": "structured", "filters": {"up_name": "恋爱教头桃姐", "date_range": "最近"}, "reasoning": "查询特定UP主的视频数量，桃姐标准化为恋爱教头桃姐"}

用户："博主们对冷暴力怎么看？"
{"route_type": "semantic", "filters": {"keywords": "冷暴力"}, "reasoning": "查询博主观点和建议，需要语义理解，冷暴力是话题关键词而非分类"}

用户："桃姐关于吵架有什么建议？"
{"route_type": "hybrid", "filters": {"up_name": "恋爱教头桃姐", "keywords": "吵架"}, "reasoning": "需要找恋爱教头桃姐的视频（结构化）+ 理解她关于吵架的建议（语义）"}

用户："喜欢分类下有什么内容？"
{"route_type": "semantic", "filters": {"category": "01_喜欢"}, "reasoning": "明确提到喜欢分类，使用 category 过滤"}

用户："一共有多少个视频？"
{"route_type": "structured", "filters": {}, "reasoning": "简单统计查询"}
"""


class IntentClassifier:
    """意图分类器"""

    def __init__(self):
        self.client = anthropic.Anthropic(
            api_key=CHAT_API_KEY,
            base_url=CHAT_API_URL,
        )
        self.model = CHAT_MODEL
        self._up_names: list[str] = []
        self._up_names_loaded_at: float = 0.0

    def _load_up_names(self) -> list[str]:
        """从 video_meta 表加载所有 UP主 名称（缓存5分钟）"""
        now = time.time()
        if self._up_names and (now - self._up_names_loaded_at) < 300:
            return self._up_names

        import duckdb
        try:
            conn = duckdb.connect(DUCKDB_PATH, read_only=True)
            rows = conn.execute(
                "SELECT DISTINCT up_name FROM video_meta WHERE up_name IS NOT NULL AND up_name != '' ORDER BY up_name"
            ).fetchall()
            conn.close()
            self._up_names = [r[0] for r in rows]
            self._up_names_loaded_at = now
        except Exception as e:
            print(f"[意图分类] 加载UP主名称失败: {e}")
        return self._up_names

    def _normalize_up_name(self, name: str) -> Optional[str]:
        """将用户输入的简称/昵称匹配到已知UP主全名

        匹配策略：
        1. 精确匹配（最快）
        2. 全名包含简称（如"桃姐" in "恋爱教头桃姐"）
        3. 简称是全名的子序列（如"啊柚" → "啊柚的碎碎念"）
        """
        if not name or not self._up_names:
            return None

        # 1. 精确匹配
        if name in self._up_names:
            return name

        # 2. 全名包含简称
        matches = [n for n in self._up_names if name in n]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            # 选最短的（最可能匹配）
            selected = min(matches, key=len)
            print(f"[意图分类] 名称模糊匹配多候选: {matches}, 选择: {selected}", flush=True)
            return selected

        # 3. 子序列匹配（如"啊柚" → "啊柚的碎碎念"）
        best_match = None
        best_score = 0.0
        for n in self._up_names:
            score = SequenceMatcher(None, name, n).ratio()
            if score > best_score and score >= 0.6:
                best_score = score
                best_match = n
        return best_match

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
            # 加载已知UP主名称列表
            up_names = self._load_up_names()
            up_names_text = "\n".join(f"- {name}" for name in up_names) if up_names else "（暂无数据）"

            # 使用 prompt caching：静态 prompt 缓存，动态 UP主 列表不缓存
            system_blocks = [
                {
                    "type": "text",
                    "text": INTENT_CLASSIFY_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                },
                {
                    "type": "text",
                    "text": f"""

## 已知UP主完整名称列表
以下是从数据库中查询到的所有UP主完整名称。用户可能使用简称或昵称，你需要将其标准化为以下完整名称之一：

{up_names_text}
""",
                },
            ]

            response = self.client.messages.create(
                model=self.model,
                system=system_blocks,
                messages=[{"role": "user", "content": question}],
                temperature=0.1,
                max_tokens=500,
            )

            # 过滤 ThinkingBlock，收集 TextBlock
            text_parts = []
            for block in response.content:
                if hasattr(block, 'text'):
                    text_parts.append(block.text)
            content = "".join(text_parts) if text_parts else None
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

        # 代码层面标准化 up_name（兜底 LLM 未标准化的场景）
        filters = result.get("filters", {})
        raw_up_name = filters.get("up_name", "")
        if raw_up_name and raw_up_name.strip():
            normalized = self._normalize_up_name(raw_up_name.strip())
            if normalized and normalized != raw_up_name:
                print(f"[意图分类] 名称标准化: '{raw_up_name}' → '{normalized}'", flush=True)
                filters["up_name"] = normalized
            elif not normalized:
                # 无法匹配，转为 keywords
                print(f"[意图分类] 名称无法匹配: '{raw_up_name}'，转为 keywords", flush=True)
                existing_kw = filters.get("keywords", "")
                filters["keywords"] = f"{existing_kw} {raw_up_name}".strip() if existing_kw else raw_up_name
                del filters["up_name"]

        return {
            "route_type": route_type,
            "filters": filters,
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
