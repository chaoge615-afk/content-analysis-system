"""
内容域配置：情感 + 求职双轨精炼体系
"""
import os
import json
import time
import re
import urllib.request
from typing import Optional, Tuple
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv('REFINE_API_URL', 'http://10.168.165.50:3300/v1/chat/completions')
API_KEY = os.getenv('REFINE_API_KEY', os.getenv('MINIMAX_API_KEY', ''))
REFINE_MODEL = os.getenv('REFINE_MODEL', 'deepseek-v4-pro')
MAX_RETRIES = 2
REFINE_SLEEP = 30

DOMAINS = {
    "emotional": {
        "name": "情感/两性",
        "refine_prompt": """你是一个情感/两性知识内容创作者。请将下面的原始素材精炼成统一的三段式结构。

【格式要求】
**核心观点**
（一句话精准概括核心观点，不超过50字）

**案例摘要**
（浓缩案例核心，保留关键细节，100-200字）

**可行动建议**
（2-3条具体可执行的建议，每条不超过30字）

【原始素材】
""",
        "classify_prompt": "你是一个情感/两性知识内容分类专家。请根据以下精炼素材，判断它属于哪个分类。",
        "categories": {
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
        },
        "default_category": "22_追求",
    },
    "career": {
        "name": "求职/职场",
        "refine_prompt": """你是一个求职/职场/职业规划领域内容创作者。请将下面的原始素材精炼成统一的三段式结构。

【格式要求】
**核心观点**
（一句话精准概括核心观点，不超过50字）

**案例摘要**
（浓缩案例核心，保留关键细节，100-200字）

**可行动建议**
（2-3条具体可执行的建议，每条不超过30字）

【原始素材】
""",
        "classify_prompt": "你是一个求职/职场知识内容分类专家。请根据以下精炼素材，判断它属于哪个分类。",
        "categories": {
            "01_面试技巧": "面试准备/自我介绍/常见问题/压力面/群面",
            "02_简历优化": "简历修改/项目包装/关键词优化/简历模板",
            "03_薪资谈判": "薪资议价/福利谈判/薪资结构/涨薪",
            "04_行业选择": "行业分析/赛道选择/风口判断/公司对比",
            "05_职场沟通": "向上管理/同事关系/会议发言/邮件沟通",
            "06_跳槽策略": "跳槽时机/离职话术/竞业协议/背调",
            "07_职业规划": "职业方向/长期规划/技能路线/转型",
            "08_实习经验": "实习申请/实习转正/实习避坑",
            "09_转行经验": "跨行转行/零基础入行/转行准备",
            "10_职场心态": "职场焦虑/内卷应对/工作生活平衡/ burnout",
            "11_职场人际关系": "办公室政治/人脉经营/导师关系/同事竞争",
            "12_求职渠道": "招聘平台/内推/猎头/校招渠道",
            "13_笔试测评": "行测/性格测试/技术笔试/测评技巧",
            "14_offer选择": "多offer对比/拒offer/ accept 时机/违约金",
            "15_职场法律": "劳动合同/社保公积金/辞退赔偿/竞业限制",
            "16_技能提升": "硬技能/软技能/考证/学历提升",
            "17_创业经验": "创业准备/合伙人/融资/副业起步",
            "18_校招经验": "秋招/春招/管培生/应届生策略",
        },
        "default_category": "07_职业规划",
    },
}


def get_domain_config(domain: str) -> dict:
    """获取指定域配置，默认返回 emotional"""
    return DOMAINS.get(domain, DOMAINS["emotional"])


# === LLM 调用工具函数 ===

def _call_llm(prompt: str, max_tokens: int = 1500, temperature: float = 0.3) -> Optional[str]:
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
    text = re.sub(r" thinking[\s\S]*? response", "", text)
    text = re.sub(r"<thinking>[\s\S]*?</thinking>", "", text)
    text = re.sub(r"<Thought>[\s\S]*?</Thought>", "", text)
    text = re.sub(r"【思考】[\s\S]*?【/思考】", "", text)
    return text.strip()


def _validate_output(text: str) -> bool:
    return ('**核心观点**' in text and '**案例摘要**' in text and '**可行动建议**' in text)


# === 精炼 + 分类 ===

def refine_content(raw_text: str, domain: str = "emotional", max_length: int = 3000) -> Optional[str]:
    cfg = get_domain_config(domain)
    prompt = cfg["refine_prompt"] + raw_text[:max_length]

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


def classify_content(refined_text: str, domain: str = "emotional") -> str:
    cfg = get_domain_config(domain)
    categories = cfg["categories"]
    default_cat = cfg["default_category"]

    cat_list = "\n".join([f"{k} - {v}" for k, v in categories.items()])
    prompt = (
        f"{cfg['classify_prompt']}\n\n"
        f"【分类列表】\n{cat_list}\n\n"
        "【要求】\n只输出分类编号和分类名，格式：01 - 分类名\n"
        "不要输出任何解释性文字。\n\n"
        f"【精炼素材】\n{refined_text[:2000]}"
    )

    result = _call_llm(prompt, max_tokens=200, temperature=0.1)
    if not result:
        return default_cat

    nums = re.findall(r"(?:^|[^0-9])([0-9]{2})(?:[^0-9]|$)", result)
    if not nums:
        return default_cat

    last_num = nums[-1]
    for cat in categories:
        if cat.startswith(last_num):
            return cat

    return default_cat


def refine_and_classify(raw_text: str, domain: str = "emotional") -> Tuple[Optional[str], str]:
    refined = refine_content(raw_text, domain)
    if not refined:
        return None, get_domain_config(domain)["default_category"]

    category = classify_content(refined, domain)
    return refined, category