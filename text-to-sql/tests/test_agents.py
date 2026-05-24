"""Test cases for Text-to-SQL Multi-Agent System."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.orchestrator.pipeline import TextToSQLPipeline


# Test cases covering different query types
TEST_CASES = [
    # 热量查询
    ("今天我吃了多少热量？", "calorie", "today"),
    ("这周每天吃了多少热量？", "calorie", "this_week"),
    ("我昨天吃了多少卡路里？", "calorie", "yesterday"),

    # 蛋白质查询
    ("今天我吃了多少蛋白质？", "protein", "today"),
    ("这周每天蛋白质摄入多少？", "protein", "this_week"),
    ("我昨天摄入了多少蛋白质？", "protein", "yesterday"),

    # 脂肪查询
    ("今天我吃了多少脂肪？", "fat", "today"),

    # 碳水查询
    ("今天我吃了多少碳水？", "carb", "today"),

    # 目标对比
    ("我今天吃的蛋白质够不够？", "protein", "today"),
    ("我今天热量达标了吗？", "calorie", "today"),

    # 趋势分析
    ("这周每天的营养摄入怎么样？", "all", "this_week"),

    # 餐次查询
    ("我午餐吃了什么？", "meal_detail", "lunch"),
]


def run_tests():
    """Run all test cases."""
    print("\n" + "=" * 60)
    print("  Text-to-SQL Multi-Agent System - Test Suite")
    print("=" * 60)

    pipeline = TextToSQLPipeline()
    results = []

    for i, (question, target_type, time_range) in enumerate(TEST_CASES, 1):
        print(f"\n[Test {i}/{len(TEST_CASES)}]")
        print(f"问题: {question}")
        print(f"预期: target={target_type}, range={time_range}")

        try:
            result = pipeline.run(question)
            status = "✓ PASS" if result["success"] else "✗ FAIL"
            print(f"结果: {status}")

            if result["success"]:
                print(f"SQL: {result['sql']}")
                print(f"回答: {result['answer']}")
            else:
                print(f"错误: {result['error']}")

            results.append({
                "question": question,
                "expected": (target_type, time_range),
                "actual": result,
                "passed": result["success"],
            })
        except Exception as e:
            print(f"异常: {e}")
            results.append({
                "question": question,
                "expected": (target_type, time_range),
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
    import sys
    success = run_tests()
    sys.exit(0 if success else 1)
