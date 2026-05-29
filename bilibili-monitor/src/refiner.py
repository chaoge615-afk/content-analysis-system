"""
内容精炼模块（兼容包装）
实际逻辑在 refiner_domains.py 中，按 domain 参数自动切换精炼 prompt + 分类体系
"""
from refiner_domains import (
    refine_content,
    classify_content,
    refine_and_classify,
    get_domain_config,
    DOMAINS,
    CATEGORIES,
    REFINE_PROMPT,
)

# 向后兼容：默认 domain = "emotional"
CATEGORIES = DOMAINS["emotional"]["categories"]
REFINE_PROMPT = DOMAINS["emotional"]["refine_prompt"]