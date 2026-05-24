#!/usr/bin/env python3
"""
非交互式知识库加载入口
支持命令行参数，用于Docker环境后台运行
"""
import argparse
import logging
import sys
import os

from rag_engine import KnowledgeRAG


def main():
    parser = argparse.ArgumentParser(description="知识库加载工具")
    parser.add_argument(
        "--clear", "-c",
        action="store_true",
        help="加载前先清空现有知识库"
    )
    parser.add_argument(
        "--stats", "-s",
        action="store_true",
        help="只显示统计信息，不加载"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示详细日志"
    )
    args = parser.parse_args()

    # 配置日志
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )
    logger = logging.getLogger(__name__)

    try:
        logger.info("初始化RAG引擎...")
        rag = KnowledgeRAG()
        logger.info("RAG引擎初始化完成")

        if args.stats:
            stats = rag.get_stats()
            print("\n=== 知识库统计 ===")
            print(f"  总文本块数：{stats['total_chunks']}")
            print(f"  分块大小：{stats['chunk_size']}")
            print(f"  重叠大小：{stats['chunk_overlap']}")
            print(f"  Top-K：{stats['top_k']}")
            return

        if args.clear:
            logger.info("清空现有知识库...")
            rag.clear_database()

        logger.info("开始加载知识库...")
        count = rag.load_knowledge()

        if count > 0:
            logger.info(f"=== 加载完成，共 {count} 个文本块 ===")
        else:
            logger.warning("=== 加载完成，未找到任何文档 ===")
        sys.exit(0)
    except Exception as e:
        logger.error(f"=== 加载失败: {str(e)} ===", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()