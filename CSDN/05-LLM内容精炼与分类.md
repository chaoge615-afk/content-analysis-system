## 系列文章目录

[B站视频内容智能分析系统（一）：项目介绍与架构设计](./01-项目介绍与架构设计.md)
[B站视频内容智能分析系统（二）：Docker Compose 一键部署](./02-Docker-Compose一键部署.md)
[B站视频内容智能分析系统（三）：B站视频自动采集](./03-B站视频自动采集.md)
[B站视频内容智能分析系统（四）：语音转写三级回退](./04-语音转写三级回退.md)
B站视频内容智能分析系统（五）：LLM 内容精炼与多域分类


### 文章目录

+ [系列文章目录](#_0)
+ [前言](#前言)
+ [一、为什么需要精炼](#一为什么需要精炼)
+ [二、精炼流程总览](#二精炼流程总览)
+ [三、双域精炼体系](#三双域精炼体系)
    + [1. 情感域（emotional）](#1-情感域emotional)
    + [2. 求职域（career）](#2-求职域career)
    + [3. 域选择](#3-域选择)
+ [四、精炼 Prompt 设计](#四精炼-prompt-设计)
    + [1. 三段式结构](#1-三段式结构)
    + [2. Prompt 模板](#2-prompt-模板)
    + [3. 输出校验](#3-输出校验)
    + [4. 清理 LLM 思考痕迹](#4-清理-llm-思考痕迹)
+ [五、分类体系](#五分类体系)
    + [1. 31 个情感分类](#1-31-个情感分类)
    + [2. 18 个求职分类](#2-18-个求职分类)
    + [3. 分类 Prompt](#3-分类-prompt)
    + [4. 分类结果解析](#4-分类结果解析)
+ [六、LLM 调用细节](#六llm-调用细节)
    + [1. API 调用封装](#1-api-调用封装)
    + [2. 重试机制](#2-重试机制)
    + [3. 速率控制](#3-速率控制)
+ [七、精炼结果入库](#七精炼结果入库)
    + [1. 写入 DuckDB](#1-写入-duckdb)
    + [2. 写入 ChromaDB](#2-写入-chromadb)
+ [八、完整精炼流程](#八完整精炼流程)
+ [总结](#总结)




## 前言

上一篇讲了怎么把音频转成文字。但转写出来的原始文本通常很长、很散——一个 20 分钟的视频，转写文本可能有 5000-8000 字，里面夹杂着口语化的表达、重复的内容、无关的闲聊。

如果直接把这些原文存进知识库，后面做 RAG 检索时效果会很差——搜索"吵架后怎么和好"，可能会匹配到一大堆不相关的内容。

所以需要在入库前做一步**LLM 精炼**：用大模型把长篇大论浓缩成结构化的摘要，同时自动分类。这样后续检索时，既能精准命中，又能在搜索结果里直接看到核心观点。


## 一、为什么需要精炼

先看一个实际例子。一个 20 分钟的视频"女生不回消息怎么办"，转写出来大概是这样的：

```
大家好欢迎来到我的频道 今天我们来聊一个很多兄弟都会遇到的问题
就是女生突然不回你消息了怎么办 我有个学员他就遇到了这种情况
他跟我说 老师我跟一个女生聊了一个月了 聊得挺好的 但是
突然有一天她就不回我了 我发了好几条消息她都不回 然后
我就很着急 打了好几个电话她也没接 ...（省略5000字）...
所以总结一下 就是遇到这种情况 第一 不要焦虑 第二 给空间
第三 过几个小时再自然地开启新话题 好了今天的分享就到这里
```

精炼后的结果：

```
**核心观点**
女生不回消息时不要焦虑追问，冷静给空间后用新话题自然重启对话。

**案例摘要**
学员与女生聊了一个月后对方突然不回消息，连发多条消息和电话均未获回应。
博主分析可能原因包括对方忙碌、话题无趣或情绪测试，建议避免追问式沟通。

**可行动建议**
- 收到不回消息后等待 2-3 小时再回复，不要连续发消息
- 用轻松有趣的新话题重新开启对话，不提"为什么不回我"
- 保持自己的生活节奏，不把注意力全放在一个人身上
```

精炼后的内容：信息密度高、结构清晰、方便检索。而且自动分到了"10_忽冷忽热"这个分类。


## 二、精炼流程总览

精炼发生在转写之后、入库之前：

```
转写文本（5000+ 字）
    ↓
  ① refine_content()：LLM 生成三段式摘要
    ↓
  ② classify_content()：LLM 自动分类
    ↓
  ③ 写入 DuckDB（结构化元数据 + 摘要）
    ↓
  ④ 写入 ChromaDB（全文 + 摘要的向量）
```

精炼和分类是两步独立调用，用同一个模型（DeepSeek V4 Flash），但用不同的 Prompt。


## 三、双域精炼体系

### 1. 情感域（emotional）

这是主要的内容域，覆盖恋爱、两性关系相关的话题。精炼 Prompt 的角色设定是"情感/两性知识内容创作者"，分类体系有 31 个类别。

### 2. 求职域（career）

后来扩展的域，覆盖求职面试、职业规划相关的话题。精炼 Prompt 的角色设定是"求职/职场/职业规划领域内容创作者"，分类体系有 18 个类别。

两个域的精炼格式完全一样（三段式），只是 Prompt 的角色和分类体系不同。

### 3. 域选择

域信息存在每个 UP主 的 YAML 配置里：

```yaml
# config/恋爱教头桃姐.yaml
name: "恋爱教头桃姐"
uid: "3546912280021515"
domain: "emotional"    # ← 情感域

# config/职场老张.yaml
name: "职场老张"
uid: "123456789"
domain: "career"       # ← 求职域
```

精炼时根据 `domain` 字段自动选择对应的 Prompt 和分类体系：

```python
DOMAINS = {
    "emotional": {
        "name": "情感/两性",
        "refine_prompt": "你是一个情感/两性知识内容创作者...",
        "classify_prompt": "你是一个情感/两性知识内容分类专家...",
        "categories": {...},  # 31 个分类
    },
    "career": {
        "name": "求职/职场",
        "refine_prompt": "你是一个求职/职场/职业规划领域内容创作者...",
        "classify_prompt": "你是一个求职/职场知识内容分类专家...",
        "categories": {...},  # 18 个分类
    },
}

def get_domain_config(domain: str) -> dict:
    return DOMAINS.get(domain, DOMAINS["emotional"])
```


## 四、精炼 Prompt 设计

### 1. 三段式结构

精炼的输出格式是固定的三段式：

```
**核心观点**
（一句话精准概括核心观点，不超过50字）

**案例摘要**
（浓缩案例核心，保留关键细节，100-200字）

**可行动建议**
（2-3条具体可执行的建议，每条不超过30字）
```

为什么是这三段？

- **核心观点**：一句话告诉你这个视频在说什么，用于搜索结果预览
- **案例摘要**：保留具体案例和关键细节，用于 RAG 检索时的上下文
- **可行动建议**：可以直接执行的行动步骤，这是用户最关心的部分

### 2. Prompt 模板

完整的精炼 Prompt：

```python
refine_prompt = """你是一个情感/两性知识内容创作者。请将下面的原始素材精炼成统一的三段式结构。

【格式要求】
**核心观点**
（一句话精准概括核心观点，不超过50字）

**案例摘要**
（浓缩案例核心，保留关键细节，100-200字）

**可行动建议**
（2-3条具体可执行的建议，每条不超过30字）

【原始素材】
"""
```

调用时把原始文本拼到 Prompt 后面：

```python
def refine_content(raw_text: str, domain: str = "emotional", max_length: int = 3000):
    cfg = get_domain_config(domain)
    prompt = cfg["refine_prompt"] + raw_text[:max_length]
    result = _call_llm(prompt, max_tokens=1500, temperature=0.3)
    return result
```

`max_length=3000` 限制了输入长度，避免超长文本浪费 token。实际上 3000 字的输入对于提炼核心观点来说足够了——再长的内容，核心信息通常也在前半部分。

`temperature=0.3` 用较低的温度，因为精炼是一个"提取+总结"任务，不需要太多创造性。

### 3. 输出校验

LLM 有时候会"偷懒"，输出的格式不符合要求。所以我做了格式校验：

```python
def _validate_output(text: str) -> bool:
    return ('**核心观点**' in text
            and '**案例摘要**' in text
            and '**可行动建议**' in text)
```

三个标题都出现才算通过。不通过就重试，最多重试 2 次：

```python
for attempt in range(MAX_RETRIES):
    result = _call_llm(prompt, max_tokens=1500, temperature=0.3)
    if not result:
        continue

    result = _clean_response(result)

    if _validate_output(result):
        return result
    else:
        print(f"精炼格式不完整，第{attempt+1}次重试")
```

### 4. 清理 LLM 思考痕迹

DeepSeek V4 Flash 是一个推理模型，输出里可能包含 `<think>...</think>` 标签。这些思考过程对我们没用，需要清理掉：

```python
def _clean_response(text: str) -> str:
    text = re.sub(r"<thinking>[\s\S]*?</thinking>", "", text)
    text = re.sub(r"<Thought>[\s\S]*?</Thought>", "", text)
    text = re.sub(r"【思考】[\s\S]*?【/思考】", "", text)
    return text.strip()
```

用正则把各种思考标签和内容全部干掉，只保留最终输出。


## 五、分类体系

### 1. 31 个情感分类

情感域的分类是我根据实际内容手动整理的，覆盖了恋爱关系的各个阶段：

```python
"categories": {
    "01_喜欢":      "喜欢/心动/爱",
    "02_聊天":      "聊天技巧/话题/冷场/破冰",
    "03_撩妹":      "撩/暧昧/调情/升温",
    "04_筛选":      "筛选女生/识别渣女/捞女",
    "05_拒绝":      "表白/拒绝/好人卡/被发卡",
    "06_备胎":      "备胎/海王/鱼塘/养鱼",
    "07_修养":      "男生修养/特质/气场/框架",
    "08_婚姻":      "婚姻/相亲/彩礼/条件",
    "09_推进":      "关系推进/牵手/确认关系",
    "10_忽冷忽热":  "忽冷忽热/冷淡/不回消息",
    "11_话术":      "话术/公式/万能回复/幽默",
    # ... 共 31 个分类
    "32_两性健康":  "两性健康/生理知识",
}
```

分类编号用两位数字前缀（01-32），方便排序和过滤。分类名后面跟着关键词描述，帮助 LLM 理解每个分类的含义。

注意编号不是连续的——中间跳过了 20（原来是"出轨"，后来合并到其他分类了），直接到 21。这种历史遗留问题在项目中很常见。

### 2. 18 个求职分类

```python
"categories": {
    "01_面试技巧":    "面试准备/自我介绍/常见问题",
    "02_简历优化":    "简历修改/项目包装/关键词优化",
    "03_薪资谈判":    "薪资议价/福利谈判/薪资结构",
    # ... 共 18 个分类
    "18_校招经验":    "秋招/春招/管培生/应届生策略",
}
```

### 3. 分类 Prompt

分类是在精炼之后做的，输入是精炼后的摘要：

```python
def classify_content(refined_text: str, domain: str = "emotional") -> str:
    cfg = get_domain_config(domain)
    categories = cfg["categories"]

    # 构建分类列表
    cat_list = "\n".join([f"{k} - {v}" for k, v in categories.items()])

    prompt = (
        f"{cfg['classify_prompt']}\n\n"
        f"【分类列表】\n{cat_list}\n\n"
        "【要求】\n只输出分类编号和分类名，格式：01 - 分类名\n"
        "不要输出任何解释性文字。\n\n"
        f"【精炼素材】\n{refined_text[:2000]}"
    )

    result = _call_llm(prompt, max_tokens=200, temperature=0.1)
```

几个关键点：
- **`max_tokens=200`**：分类只需要输出一个编号，不需要长回答
- **`temperature=0.1`**：极低温度，确保分类结果稳定一致
- **"不要输出任何解释性文字"**：明确要求只输出编号，避免 LLM 啰嗦

### 4. 分类结果解析

LLM 可能输出各种格式，所以我用正则提取编号：

```python
def classify_content(refined_text, domain):
    result = _call_llm(prompt, max_tokens=200, temperature=0.1)

    # 提取两位数字编号
    nums = re.findall(r"(?:^|[^0-9])([0-9]{2})(?:[^0-9]|$)", result)
    if not nums:
        return default_cat  # 解析失败，用默认分类

    # 取最后一个编号（LLM 有时候会先猜一个再修正）
    last_num = nums[-1]
    for cat in categories:
        if cat.startswith(last_num):
            return cat

    return default_cat
```

`nums[-1]` 取最后一个编号——因为推理模型有时候会先说"可能是 24_心态"，然后修正为"最终判断：25_关系"，取最后一个更接近最终结论。

如果解析失败（LLM 输出了完全不符合格式的内容），就用默认分类（情感域默认 `22_追求`，求职域默认 `07_职业规划`）。


## 六、LLM 调用细节

### 1. API 调用封装

LLM 调用用的是最原始的 `urllib.request`（没用 requests 库，减少依赖）：

```python
def _call_llm(prompt: str, max_tokens: int = 1500, temperature: float = 0.3) -> Optional[str]:
    payload = {
        "model": REFINE_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    headers = {"Authorization": "Bearer " + API_KEY, "Content-Type": "application/json"}

    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()
```

API 配置全部从 `.env` 读取，改 `.env` 就能切换端点和模型，不用改代码：

```python
API_URL = os.getenv('REFINE_API_URL', '')
API_KEY = os.getenv('REFINE_API_KEY', os.getenv('MINIMAX_API_KEY', ''))
REFINE_MODEL = os.getenv('REFINE_MODEL', '')
```

### 2. 重试机制

精炼函数有重试逻辑，最多 2 次：

```python
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
```

重试的原因可能是：
- API 调用失败（网络问题、限流）
- LLM 输出格式不正确

### 3. 速率控制

每次 API 调用之间有一个 `REFINE_SLEEP = 30` 秒的间隔。这是因为 DeepSeek API 有速率限制，连续请求太快会被封。30 秒的间隔在实际使用中基本不会触发限流。


## 七、精炼结果入库

精炼和分类完成后，结果要写入两个地方。

### 1. 写入 DuckDB

精炼摘要和分类写入 `video_meta` 表：

```python
video_records.append({
    'bvid': bvid,
    'up_name': up_name,
    'up_uid': uid,
    'title': title,
    'publish_date': pub_date,
    'category': category,        # ← LLM 分类结果
    'duration': duration,
    'summary': refined_text,     # ← 三段式精炼摘要
    'tags': tags,
    'domain': domain,            # ← emotional / career
})
db.insert_videos(video_records)
```

`summary` 字段存的就是精炼后的三段式文本，`category` 存的是 LLM 选择的分类。

### 2. 写入 ChromaDB

精炼结果和原始全文都会写入 ChromaDB 做向量化：

```python
# 全文写入（用于 RAG 检索）
chroma_writer.add_document(
    text=raw_text,
    metadata={"bvid": bvid, "up_name": up_name, "category": category,
              "content_type": "full"}
)

# 精炼摘要也写入（用于精准匹配）
chroma_writer.add_document(
    text=refined_text,
    metadata={"bvid": bvid, "up_name": up_name, "category": category,
              "content_type": "summary"}
)
```

同一个视频在 ChromaDB 里至少有两条记录：一条全文、一条摘要。RAG 检索时可以根据 `content_type` 过滤，也可以混合搜索。

metadata 里的 `category` 和 `up_name` 可以在检索时做过滤，比如"只看桃姐的忽冷忽热分类的内容"。


## 八、完整精炼流程

把所有步骤串起来，看完整的精炼+入库流程：

```python
def refine_and_classify(raw_text: str, domain: str = "emotional"):
    """精炼 + 分类一体化"""
    refined = refine_content(raw_text, domain)
    if not refined:
        return None, get_domain_config(domain)["default_category"]

    category = classify_content(refined, domain)
    return refined, category
```

在 `monitor.py` 的批次处理中调用：

```python
# 对每个转写文件做精炼
for txt_file in transcripts_dir.glob("*.txt"):
    raw_text = txt_file.read_text(encoding="utf-8")

    # 精炼 + 分类
    refined, category = refine_and_classify(raw_text, domain=domain)

    if refined:
        # 写入 DuckDB
        db.insert_video(bvid=bvid, summary=refined, category=category, ...)

        # 写入 ChromaDB
        chroma.add_document(text=raw_text, metadata={...})
        chroma.add_document(text=refined, metadata={"content_type": "summary", ...})
    else:
        print(f"  ⚠️ {txt_file.name} 精炼失败，使用原始文本")
        # 精炼失败也不丢数据，直接把原文入库
```

精炼失败了也不会丢数据——会把原始文本直接写入数据库，只是没有结构化的摘要和精确分类。


## 总结

精炼是连接"原始数据"和"知识检索"的桥梁。通过三段式 Prompt 把散乱的转写文本浓缩成核心观点+案例+建议，再通过分类 Prompt 自动归类到 31 个情感分类（或 18 个求职分类）之一。精炼和分类的结果同时写入 DuckDB（结构化查询）和 ChromaDB（语义检索），为后面的 Text-to-SQL 和 RAG 提供高质量的数据基础。下一篇讲 Text-to-SQL 的 4-Agent Pipeline。
