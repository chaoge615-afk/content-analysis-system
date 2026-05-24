"""
内容精炼模块
基于 refine_batch.py 的核心逻辑，将 Whisper 转写的原始文本精炼为结构化摘要
"""
import os
import re
import time
import json
import urllib.request
from typing import Optional, Tuple
from dotenv import load_dotenv

load_dotenv()

# API 配置
API_URL = os.getenv('REFINE_API_URL', 'http://10.168.165.50:3300/v1/chat/completions')
API_KEY = os.getenv('REFINE_API_KEY', os.getenv('MINIMAX_API_KEY', ''))
REFINE_MODEL = os.getenv('REFINE_MODEL', 'deepseek-v4-pro')

MAX_RETRIES = 3
REFINE_SLEEP = 5

# 精炼 Prompt
REFINE_PROMPT = """你是一个情感/两性知识内容创作者。请将下面的原始素材精炼成统一的三段式结构。

【格式要求】
**核心观点**
（一句话精准概括核心观点，不超过50字）

**案例摘要**
（浓缩案例核心，保留关键细节，100-200字）

**可行动建议**
（2-3条具体可执行的建议，每条不超过30字）

【原始素材】
"""

# 分类列表（来自 refine_batch.py）
CATEGORIES = {
    "01_喜欢": "喜欢/心动/爱",
    "02_聊天": "聊天技巧/话题/冷场/破冰",
    "03_撩妹": "撩/暧昧/调情/升温",
    "04_筛选": "筛选女生/识别渣女/捞女",
    "05_拒绝": "表白/拒绝/好人卡/被发卡",
    "06_备胎": "备胎/海王/鱼塘/养鱼",
    "07_修养": "男生修养/特质/气场/框架",
    "08_婚姻": "婚姻/相亲/彩礼/条件",
    "09_推进": "关系推进/牵手/确认关系",
    "10_忽冷忽热": "忽冷忽热/冷淡/不回消息",
    "11_话术": "话术/公式/万能回复/幽默",
    "12_深夜": "深夜/晚安/失眠",
    "13_接触": "肢体接触/亲密/牵手/拥抱",
    "14_约会": "约会/邀约/见面/去哪儿",
    "15_外貌": "外貌/形象/穿搭/发型",
    "16_社交": "朋友圈/社交媒体/展示面",
    "17_单身": "单身/为什么单身/脱单",
    "18_生理": "生理/身体/性相关",
    "19_跪舔": "跪舔/讨好/单方面付出",
    "21_前任": "前任/分手/挽回/失恋",
    "22_追求": "追女生/追求方法/表白时机",
    "23_回复": "回复技巧/怎么回/接话",
    "24_心态": "心态/心理建设/内核/认知偏差/情绪管理/内耗/恋爱脑",
    "25_关系": "关系维护/信任/吵架/长期关系",
    "26_情况": "特殊情况/异地/姐弟恋/师生",
    "27_反应": "反应处理/打压/冷漠/拒绝",
    "28_技巧": "技巧/策略/套路",
    "29_信号": "信号判断/潜台词/她喜不喜欢",
    "30_自保": "自我保护/止损/不值得",
    "31_祛魅_抗性": "祛魅/抗性/低价值",
    "32_两性健康": "两性健康/生理知识/男科/妇科/性疾病/性功能",
}


def _call_llm(prompt: str, max_tokens: int = 1500, temperature: float = 0.3) -> Optional[str]:
    """调用 LLM API"""
    if not API_KEY:
        print("错误: 未设置 REFINE_API_KEY 或 MINIMAX_API_KEY")
        return None

    payload = {
        "model": REFINE_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    headers = {"Authorization": "Bearer " + API_KEY, "Content-Type": "application/json"}

    try:
        req = urllib.request.Request(
            API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"LLM API 调用失败: {e}")
        return None


def _clean_response(text: str) -> str:
    """清除思考标签和格式说明残留"""
    text = re.sub(r"<think>.*?\n\n", "", text, count=1)
    text = re.sub(r"<Thought>[\s\S]*?</Thought>", "", text)
    text = re.sub(r"【思考】[\s\S]*?【/思考】", "", text)
    return text.strip()


def _validate_output(text: str) -> bool:
    """校验输出是否包含完整的三个部分"""
    return ('**核心观点**' in text and '**案例摘要**' in text and '**可行动建议**' in text)


def refine_content(raw_text: str, max_length: int = 3000) -> Optional[str]:
    """
    精炼原始文本为三段式摘要
    raw_text: 原始转写文本
    max_length: 截取原文最大长度
    返回: 精炼后的三段式文本，失败返回 None
    """
    prompt = REFINE_PROMPT + raw_text[:max_length]

    for attempt in range(MAX_RETRIES):
        result = _call_llm(prompt, max_tokens=1500, temperature=0.3)
        if not result:
            time.sleep(REFINE_SLEEP)
            continue

        result = _clean_response(result)

        if _validate_output(result):
            return result
        else:
            print(f"精炼格式不完整，第{attempt+1}次重试")
            time.sleep(REFINE_SLEEP)

    return None


def classify_content(refined_text: str) -> str:
    """
    对精炼后的内容进行分类
    refined_text: 精炼后的三段式文本
    返回: 分类编号（如 "01_喜欢"），失败返回 "22_追求"（默认）
    """
    cat_list = "\n".join([f"{k} - {v}" for k, v in CATEGORIES.items()])
    prompt = (
        "你是一个情感/两性知识内容分类专家。请根据以下精炼素材，判断它属于哪个分类。\n\n"
        f"【分类列表】\n{cat_list}\n\n"
        "【要求】\n只输出分类编号和分类名，格式：32 - 两性健康\n"
        "不要输出任何解释性文字。\n\n"
        f"【精炼素材】\n{refined_text[:2000]}"
    )

    result = _call_llm(prompt, max_tokens=200, temperature=0.1)
    if not result:
        return "22_追求"

    # 解析分类编号
    nums = re.findall(r"(?:^|[^0-9])([0-9]{2})(?:[^0-9]|$)", result)
    if not nums:
        return "22_追求"

    last_num = nums[-1]
    for cat in CATEGORIES:
        if cat.startswith(last_num):
            return cat

    return "22_追求"


def refine_and_classify(raw_text: str) -> Tuple[Optional[str], str]:
    """
    精炼 + 分类一体化
    返回: (精炼文本, 分类编号)
    """
    refined = refine_content(raw_text)
    if not refined:
        return None, "22_追求"

    category = classify_content(refined)
    return refined, category
