"""完整的 Pipeline 单元测试（使用 Mock LLM）"""

import sys
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock LLM 响应
INTENT_MOCK_RESPONSE = {
    "query_type": "video",
    "query_target": "video_count",
    "filters": {
        "up_name": "桃姐",
        "date_range": {
            "type": "this_month"
        }
    },
    "aggregation": "count",
    "limit": 10
}

SCHEMA_MOCK_RESPONSE = {
    "tables": ["video_meta"],
    "fields": {
        "video_meta": ["bvid", "title", "up_name", "publish_date", "duration"]
    },
    "joins": [],
    "reasoning": "查询桃姐本月的视频数量，从 video_meta 表获取"
}

SQL_MOCK_RESPONSE = {
    "sql": "SELECT COUNT(*) as video_count FROM video_meta WHERE up_name = '桃姐' AND publish_date >= DATE '2026-05-01'",
    "reasoning": "从 video_meta 表查询桃姐本月的视频数量"
}

REVIEW_MOCK_RESPONSE = {
    "passed": True,
    "issues": [],
    "suggestions": []
}


class MockLLMClient:
    """Mock LLM 客户端，用于测试"""

    def __init__(self, response_data):
        self.response_data = response_data

    def invoke(self, messages):
        """返回预定义的响应"""
        return json.dumps(self.response_data)

    def __call__(self, messages):
        return self.invoke(messages)


def test_intent_agent():
    """Test Intent Understanding Agent"""
    print("\n=== Test Intent Agent ===")

    from src.agents.intent_agent import IntentAgent

    # Use Mock
    mock_response = json.dumps(INTENT_MOCK_RESPONSE)
    with patch.object(IntentAgent, '__init__', lambda self: setattr(self, 'llm', MockLLMClient(INTENT_MOCK_RESPONSE))):
        agent = IntentAgent.__new__(IntentAgent)
        agent.llm = MockLLMClient(INTENT_MOCK_RESPONSE)

        result = agent.run("桃姐这个月发了几个视频？")

        assert "error" not in result, f"Intent agent returned error: {result.get('error')}"
        assert result["query_target"] == "video_count", f"Expected video_count, got {result.get('query_target')}"
        assert result["filters"]["up_name"] == "桃姐", f"Expected 桃姐, got {result.get('filters', {}).get('up_name')}"

        print(f"[PASS] Intent Agent test passed: {result}")
        return result


def test_schema_agent():
    """Test Schema Retrieval Agent"""
    print("\n=== Test Schema Agent ===")

    from src.agents.schema_agent import SchemaAgent

    agent = SchemaAgent.__new__(SchemaAgent)
    agent.llm = MockLLMClient(SCHEMA_MOCK_RESPONSE)

    intent = INTENT_MOCK_RESPONSE
    result = agent.run(intent)

    assert "error" not in result, f"Schema agent returned error: {result.get('error')}"
    assert "video_meta" in result["tables"], f"Expected video_meta in tables, got {result.get('tables')}"

    print(f"[PASS] Schema Agent test passed")
    return result


def test_sql_gen_agent():
    """Test SQL Generation Agent"""
    print("\n=== Test SQL Generation Agent ===")

    from src.agents.sql_gen_agent import SQLGenAgent

    agent = SQLGenAgent.__new__(SQLGenAgent)
    agent.llm = MockLLMClient(SQL_MOCK_RESPONSE)

    intent = INTENT_MOCK_RESPONSE
    schema = SCHEMA_MOCK_RESPONSE
    result = agent.run(intent, schema)

    assert "error" not in result, f"SQL gen agent returned error: {result.get('error')}"
    assert "sql" in result, f"No SQL in result: {result}"
    assert "SELECT" in result["sql"].upper(), f"Invalid SQL: {result.get('sql')}"

    print(f"[PASS] SQL Generation Agent test passed: {result['sql']}")
    return result["sql"]


def test_review_agent():
    """Test SQL Review Agent"""
    print("\n=== Test SQL Review Agent ===")

    from src.agents.review_agent import ReviewAgent

    agent = ReviewAgent.__new__(ReviewAgent)
    agent.llm = MockLLMClient(REVIEW_MOCK_RESPONSE)

    sql = SQL_MOCK_RESPONSE["sql"]
    intent = INTENT_MOCK_RESPONSE
    schema = SCHEMA_MOCK_RESPONSE

    result = agent.run(sql, intent, schema)

    assert "passed" in result, f"No passed field in result: {result}"
    assert result["passed"] == True, f"SQL review failed: {result.get('issues')}"

    print(f"[PASS] SQL Review Agent test passed")
    return result


def test_database_execution():
    """Test Database Execution"""
    print("\n=== Test Database Execution ===")

    from src.database.duckdb_utils import execute_sql

    # Test simple query
    result = execute_sql("SELECT COUNT(*) FROM video_meta")
    assert result[0][0] > 0, "Video_meta table should have data"

    # Test aggregation query
    result = execute_sql("SELECT up_name, COUNT(*) as cnt FROM video_meta GROUP BY up_name LIMIT 1")
    assert len(result) > 0, "Should have at least one UP主"

    print(f"[PASS] Database execution test passed")
    print(f"  Video_meta table: {execute_sql('SELECT COUNT(*) FROM video_meta')[0][0]} rows")
    print(f"  UP主数量: {execute_sql('SELECT COUNT(DISTINCT up_name) FROM video_meta')[0][0]}")


def test_pipeline_integration():
    """Test Full Pipeline Integration"""
    print("\n=== Test Full Pipeline Integration ===")

    from src.orchestrator.pipeline import TextToSQLPipeline
    from src.agents.intent_agent import IntentAgent
    from src.agents.schema_agent import SchemaAgent
    from src.agents.sql_gen_agent import SQLGenAgent
    from src.agents.review_agent import ReviewAgent

    # Create Pipeline
    pipeline = TextToSQLPipeline()

    # Mock each Agent's LLM
    pipeline.intent_agent.llm = MockLLMClient(INTENT_MOCK_RESPONSE)
    pipeline.schema_agent.llm = MockLLMClient(SCHEMA_MOCK_RESPONSE)
    pipeline.sql_gen_agent.llm = MockLLMClient(SQL_MOCK_RESPONSE)
    pipeline.review_agent.llm = MockLLMClient(REVIEW_MOCK_RESPONSE)

    # Run Pipeline
    result = pipeline.run("桃姐这个月发了几个视频？")

    # Verify result
    assert result["success"] == True, f"Pipeline failed: {result.get('error')}"
    assert "sql" in result, "Pipeline should return SQL"
    assert "SELECT" in result["sql"].upper(), f"Invalid SQL: {result.get('sql')}"

    print(f"[PASS] Full pipeline integration test passed")
    print(f"  Generated SQL: {result['sql']}")
    print(f"  Query Result: {result.get('result')}")
    print(f"  Natural Language Answer: {result.get('answer')}")

    return result


def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("Text-to-SQL Multi-Agent System Test")
    print("=" * 60)

    tests = [
        ("Intent Agent", test_intent_agent),
        ("Schema Agent", test_schema_agent),
        ("SQL Generation Agent", test_sql_gen_agent),
        ("SQL Review Agent", test_review_agent),
        ("Database Execution", test_database_execution),
        ("Full Pipeline Integration", test_pipeline_integration),
    ]

    results = []
    for name, test_func in tests:
        try:
            test_func()
            results.append((name, True, None))
        except AssertionError as e:
            results.append((name, False, str(e)))
            print(f"[FAIL] {name} test failed: {e}")
        except Exception as e:
            results.append((name, False, str(e)))
            print(f"[ERROR] {name} exception: {e}")

    # Print summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for _, success, _ in results if success)
    total = len(results)

    for name, success, error in results:
        status = "[PASS]" if success else "[FAIL]"
        print(f"  {status} {name}")

    print(f"\nPassed: {passed}/{total}")

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
