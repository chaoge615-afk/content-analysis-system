#!/usr/bin/env python3
"""情感素材精炼分类通用脚本"""

import urllib.request, json, os, re, sys, time, shutil

API_URL = os.environ.get('REFINE_API_URL', 'http://140.143.147.125:3300/v1/chat/completions')
API_KEY = os.environ.get('REFINE_API_KEY', os.environ.get('RESOFT_API_KEY', os.environ.get('MINIMAX_API_KEY', '')))
if not API_KEY:
    print("错误: 未设置 REFINE_API_KEY / RESOFT_API_KEY / MINIMAX_API_KEY 环境变量")
    sys.exit(1)
REFINE_MODEL = os.environ.get('REFINE_MODEL', 'deepseek-v4-pro')
BATCH_SIZE = 50
REFINE_SLEEP = 5
CLASSIFY_SLEEP = 3
MAX_RETRIES = 3

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

REJECTION_KEYWORDS = [
    "抱歉，我无法提供", "我无法帮您完成", "我不能回答这个问题",
    "请提供其他问题", "不在我的知识范围内", "违反内容政策",
]

ENGLISH_CLEAN_PATTERNS = [
    r"\*\*核心观点\*\*.*?\(用1-2句话.*?\)",
    r"\*\*案例摘要\*\*.*?\(.*?\)",
    r"\*\*可行动建议\*\*.*?\(.*?\)",
    r"\(Within \d+ characters.*?\)",
    r"\(1-2 sentences.*?\)",
    r"50 characters.*?\)\s*",
    r"\d+ characters max\)\s*",
    r"characters? (max|limit).*?\)\s*",
    r"Let's count:.*?(?=\n\n|\Z)",
    r"Count: Chinese characters:.*?(?=\n\n|\Z)",
    r"The user then provides.*",
    r"We'll produce.*",
    r"Now (check|ensure|count|produce).*",
    r"Now check.*",
    r"For example:.*?(?=\n\n|\Z)",
    r"Thus we respond.*",
    r"We respond accordingly.*",
    r"No (policy violation|extra commentary|additional).*",
    r"This is normal content.*",
    r"It's (okay|fine|acceptable|normal).*",
    r"Below is the refined.*",
    r"Here is the refined.*",
    r"精炼后.*",
    r"字数统计.*",
]

def parse_thinking_for_category(raw):
    text = raw
    text = re.sub(r"<br>\s*", "<BR>", text)
    text = re.sub(r"<BR>", "\n", text)
    text = re.sub(r"<\\br>.*?</", "", text, flags=re.DOTALL)
    text = re.sub(r"<br>.*?</", "", text, flags=re.DOTALL)
    text = text.strip()
    nums = re.findall(r"(?:^|[^0-9])([0-9]{2})(?:[^0-9]|$)", text)
    if not nums:
        return "22_追求"
    last_num = nums[-1]
    for cat in CATEGORIES:
        if cat.startswith(last_num):
            return cat
    return "22_追求"

def is_rejection(text):
    """检测输出是否包含拒绝类内容"""
    text_lower = text.lower()
    for kw in REJECTION_KEYWORDS:
        if kw.lower() in text_lower:
            return True
    return False

def clean_response(text):
    """清除思考标签和格式说明残留"""
    text = re.sub(r"<think>.*?\n\n", "", text, count=1)
    text = re.sub(r"<Thought>[\s\S]*?</Thought>", "", text)
    text = re.sub(r"【思考】[\s\S]*?【/思考】", "", text)
    text = text.strip()
    return text

def clean_english_residue(text):
    """清除混入的英文格式说明残留"""
    for pattern in ENGLISH_CLEAN_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.DOTALL)
    # 清理残留的英文标点和空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    return text

def validate_output(text):
    """校验输出是否包含完整的三个部分"""
    has_k = '**核心观点**' in text
    has_a = '**案例摘要**' in text
    has_s = '**可行动建议**' in text
    return has_k and has_a and has_s

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

def refine_content(content, filename="未知文件"):
    prompt = REFINE_PROMPT + content[:3000]
    payload = {
        "model": REFINE_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1500,
        "temperature": 0.3,
    }
    headers = {"Authorization": "Bearer " + API_KEY, "Content-Type": "application/json"}

    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(API_URL, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                raw = data["choices"][0]["message"]["content"].strip()

            result = clean_response(raw)

            # 拒绝检测
            if is_rejection(result):
                print(f"  [{filename}] 检测到拒绝内容，第{attempt+1}次重试")
                time.sleep(REFINE_SLEEP)
                continue

            # 英文残留清除
            result = clean_english_residue(result)

            # 格式校验
            if not validate_output(result):
                print(f"  [{filename}] 格式不完整（第{attempt+1}次重试）")
                time.sleep(REFINE_SLEEP)
                continue

            return result

        except Exception as e:
            print(f"  [{filename}] 请求异常: {e}，第{attempt+1}次重试")
            time.sleep(REFINE_SLEEP)

    return ""  # 所有重试都失败

def classify_by_llm(refined_text):
    cat_list = "\n".join([k + " - " + v for k, v in CATEGORIES.items()])
    prompt = "你是一个情感/两性知识内容分类专家。请根据以下精炼素材，判断它属于哪个分类。\n\n【分类列表】\n" + cat_list + "\n\n【要求】\n只输出分类编号和分类名，格式：32 - 两性健康\n不要输出任何解释性文字。\n\n【精炼素材】\n" + refined_text[:2000]
    payload = {
        "model": REFINE_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 200,
        "temperature": 0.1,
    }
    headers = {"Authorization": "Bearer " + API_KEY, "Content-Type": "application/json"}
    req = urllib.request.Request(API_URL, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        raw = data["choices"][0]["message"]["content"].strip()
    return parse_thinking_for_category(raw)

def main():
    if len(sys.argv) < 3:
        print("用法: python3 refine_batch.py <输入目录> <素材库目录> [批次大小]")
        sys.exit(1)
    input_dir = sys.argv[1]
    material_dir = sys.argv[2]
    batch_size = int(sys.argv[3]) if len(sys.argv) > 3 else BATCH_SIZE
    TEMP_DIR = os.path.join(input_dir, "_refined_temp")
    RESULT_FILE = os.path.join(input_dir, ".batch_results.json")
    os.makedirs(TEMP_DIR, exist_ok=True)
    files = sorted([f for f in os.listdir(input_dir) if f.endswith(".txt") and not f.startswith("_")])
    if not files:
        print("没有找到txt文件")
        return
    if os.path.exists(RESULT_FILE):
        results = json.load(open(RESULT_FILE, "r", encoding="utf-8"))
    else:
        results = {}
    todo = [f for f in files if f not in results or not results[f].get("refined")]
    print(f"总数: {len(files)}, 待处理: {len(todo)}")
    if todo:
        print("\n========== Step1: 精炼 ==========")
        for i, filename in enumerate(todo):
            filepath = os.path.join(input_dir, filename)
            temp_path = os.path.join(TEMP_DIR, filename)
            if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
                refined = open(temp_path, "r", encoding="utf-8").read()
                if validate_output(refined):
                    print(f"[{i+1}/{len(todo)}] {filename[:50]}... skip (已有有效)")
                    results[filename] = results.get(filename, {})
                    results[filename]["refined"] = refined
                    continue
                else:
                    print(f"[{i+1}/{len(todo)}] {filename[:50]}... 已存在但格式无效，重新处理")
                    refined = refine_content(open(filepath, "r", encoding="utf-8").read(), filename[:30])
            else:
                print(f"[{i+1}/{len(todo)}] {filename[:50]}...", end=" ", flush=True)
                try:
                    content = open(filepath, "r", encoding="utf-8").read()
                    if len(content) < 30:
                        print(f"内容异常（{len(content)}字节），跳过")
                        refined = ""
                    else:
                        refined = refine_content(content, filename[:30])
                        if refined:
                            open(temp_path, "w", encoding="utf-8").write(refined)
                            print("ok")
                        else:
                            print("重试失败，跳过")
                            refined = ""
                except Exception as e:
                    print(f"err: {e}")
                    refined = ""
                time.sleep(REFINE_SLEEP)
            results[filename] = results.get(filename, {})
            results[filename]["refined"] = refined
            json.dump(results, open(RESULT_FILE, "w", encoding="utf-8"))
        print("\n========== Step2: LLM分类 ==========")
        for i, filename in enumerate(todo):
            if not results[filename].get("refined"):
                continue
            if "cat" not in results[filename]:
                print(f"[{i+1}/{len(todo)}] {filename[:50]}...", end=" ", flush=True)
                try:
                    cat = classify_by_llm(results[filename]["refined"])
                    results[filename]["cat"] = cat
                    print(f"-> {cat}")
                except Exception as e:
                    results[filename]["cat"] = "22_追求"
                    print(f"err: {e}")
                json.dump(results, open(RESULT_FILE, "w", encoding="utf-8"))
                time.sleep(CLASSIFY_SLEEP)
    else:
        print("没有待处理文件")
    print("\n" + "="*60)
    print("结果汇总")
    print("="*60)
    cats = {}
    for filename, info in results.items():
        cat = info.get("cat", "?")
        cats[cat] = cats.get(cat, 0) + 1
    for cat, n in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {n}")
    print(f"总计: {len(results)}")
    confirm = input("\n确认分发? [y/n]: ").strip().lower()
    if confirm == "y":
        os.makedirs(material_dir, exist_ok=True)
        distributed = 0
        for filename, info in results.items():
            cat = info.get("cat", "22_追求")
            src = os.path.join(TEMP_DIR, filename)
            if os.path.exists(src):
                dst = os.path.join(material_dir, cat, filename)
                os.makedirs(os.path.join(material_dir, cat), exist_ok=True)
                shutil.copy2(src, dst)
                distributed += 1
        print(f"已分发 {distributed} 个文件")
        shutil.rmtree(TEMP_DIR)
        os.remove(RESULT_FILE)
        print("临时文件已清理")

if __name__ == "__main__":
    main()