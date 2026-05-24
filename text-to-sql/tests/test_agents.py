"""Text-to-SQL Agent 集成测试（需要真实 LLM API）"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.orchestrator.pipeline import TextToSQLPipeline


# 测试用例：(问题, 预期涉及的关键表)
TEST_CASES = [
    # UP主查询
    ("桃姐最近发了几个视频？", "video_meta"),
    ("一共有多少个UP主？", "video_meta"),

    # 视频统计
    ("一共有多少个视频？", "video_meta"),
    ("各分类有多少视频？", "video_meta"),
    ("视频平均时长是多少？", "video_meta"),

    # 时间范围
    ("最近一周有什么新视频？", "video_meta"),
    ("这个月发布了多少视频？", "video_meta"),

    # 排序/限制
    ("最近的10个视频是什么？", "video_meta"),
    ("哪个UP主视频最多？", "video_meta"),

    # 关键词搜索
    ("有没有关于冷暴力的视频？", "video_meta"),
]


def run_tests():
    """Run all test cases."""
    print("\n" + "=" * 60)
    print("  Text-to-SQL Multi-Agent System - 集成测试")
    print("=" * 60)

    pipeline = TextToSQLPipeline()
    results = []

    for i, (question, expected_table) in enumerate(TEST_CASES, 1):
        print(f"\n[Test {i}/{len(TEST_CASES)}]")
        print(f"问题: {question}")
        print(f"预期涉及表: {expected_table}")

        try:
            result = pipeline.run(question)
            status = "✓ PASS" if result["success"] else "✗ FAIL"
            print(f"结果: {status}")

            if result["success"]:
                print(f"SQL: {result['sql']}")
                print(f"回答: {result['answer'][:100]}")
                # 验证 SQL 是否涉及预期表
                if expected_table.lower() in result['sql'].lower():
                    print(f"✓ SQL 包含预期表 {expected_table}")
                else:
                    print(f"✗ SQL 未包含预期表 {expected_table}")
            else:
                print(f"错误: {result['error'][:200]}")

            results.append({
                "question": question,
                "expected_table": expected_table,
                "actual": result,
                "passed": result["success"],
            })
        except Exception as e:
            print(f"异常: {e}")
            results.append({
                "question": question,
                "expected_table": expected_table,
                "actual": {"error": str(e)},
                "passed": False,
            })

    # Summary
    print("\n" + "=" * 60)
    print("  Test Summary")
    print("=" * 60)
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    print(f"通过: {passed}/{total}")

    for i, r in enumerate(results, 1):
        status = "✓" if r["passed"] else "✗"
        print(f"  {status} [{i}] {r['question']}")

    return passed == total


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
