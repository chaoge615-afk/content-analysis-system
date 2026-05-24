import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from semantic_search import build_index

if __name__ == "__main__":
    print("开始构建素材库 embedding 索引...")
    build_index()