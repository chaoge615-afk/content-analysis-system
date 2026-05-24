#!/usr/bin/env python3
"""
个人知识库问答系统
交互式命令行入口
"""
import warnings
warnings.filterwarnings("ignore")

from rag_engine import KnowledgeRAG

def print_help():
    print("\n=== 个人知识库问答系统 ===")
    print("可用命令：")
    print("  load    - 重新加载所有markdown文件到知识库")
    print("  clear   - 清空知识库")
    print("  stats   - 查看知识库统计信息")
    print("  help    - 显示帮助")
    print("  exit    - 退出程序")
    print("  直接输入问题即可提问\n")

def main():
    print("正在初始化RAG引擎...")
    try:
        rag = KnowledgeRAG()
        print("初始化完成！")
        print_help()
    except Exception as e:
        print(f"初始化失败：{e}")
        print("请检查：")
        print("1. 是否复制了 .env.example 为 .env 并填入了 DASHSCOPE_API_KEY")
        print("2. API Key 是否正确")
        return

    while True:
        try:
            user_input = input("\n> ").strip()

            if not user_input:
                continue

            if user_input.lower() == "exit":
                print("再见！")
                break
            elif user_input.lower() == "help":
                print_help()
                continue
            elif user_input.lower() == "load":
                print("正在加载知识库...")
                count = rag.load_knowledge()
                if count > 0:
                    print(f"加载完成，共 {count} 个文本块")
                continue
            elif user_input.lower() == "clear":
                confirm = input("确认清空知识库？这会删除所有索引 (y/N): ").strip().lower()
                if confirm == "y":
                    rag.clear_database()
                continue
            elif user_input.lower() == "stats":
                stats = rag.get_stats()
                print(f"\n知识库统计：")
                print(f"  总文本块数：{stats['total_chunks']}")
                print(f"  分块大小：{stats['chunk_size']}")
                print(f"  重叠大小：{stats['chunk_overlap']}")
                continue
            else:
                # 直接提问
                answer = rag.ask(user_input)
                print(f"\n{answer}")

        except KeyboardInterrupt:
            print("\n再见！")
            break
        except Exception as e:
            print(f"出错了：{e}")

if __name__ == "__main__":
    main()
