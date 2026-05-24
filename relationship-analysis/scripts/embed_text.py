#!/usr/bin/env python3
"""单独封装 embedding 模型调用"""
import sys, json
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')
text = sys.argv[1] if len(sys.argv) > 1 else ""
emb = model.encode(text, normalize_embeddings=True)
print(json.dumps(list(emb)))