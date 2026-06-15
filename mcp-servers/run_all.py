"""统一启动入口 — 在单个进程中运行 3 个 MCP Server

使用 multiprocessing 让每个 Server 运行在独立进程中，
共享同一个 Python 环境，简化部署。
"""
import multiprocessing
import sys


def run_sql():
    from sql_mcp_server import run
    run()


def run_rag():
    from rag_mcp_server import run
    run()


def run_bilibili():
    from bilibili_mcp_server import run
    run()


def main():
    """启动所有 MCP Server"""
    print("=" * 50)
    print("MCP Server 包装层启动")
    print("  - Bilibili MCP: :9001/sse")
    print("  - RAG MCP:      :9002/sse")
    print("  - SQL MCP:      :9003/sse")
    print("=" * 50)

    processes = [
        multiprocessing.Process(target=run_bilibili, name="bilibili-mcp", daemon=True),
        multiprocessing.Process(target=run_rag, name="rag-mcp", daemon=True),
        multiprocessing.Process(target=run_sql, name="sql-mcp", daemon=True),
    ]

    for p in processes:
        p.start()
        print(f"[OK] {p.name} 已启动 (pid={p.pid})")

    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        print("\n[STOP] 正在关闭所有 MCP Server...")
        for p in processes:
            p.terminate()
        for p in processes:
            p.join(timeout=5)
        print("[BYE] 所有 MCP Server 已关闭")
        sys.exit(0)


if __name__ == "__main__":
    # Windows 需要 spawn 模式
    multiprocessing.set_start_method("spawn", force=True)
    main()
