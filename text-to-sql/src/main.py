"""CLI interface for Text-to-SQL Multi-Agent System."""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.orchestrator.pipeline import TextToSQLPipeline
from src.database.duckdb_utils import init_database


def print_result(result: dict):
    """Print query result in a formatted way."""
    print("\n" + "=" * 60)

    if result["success"]:
        print("[OK] Query Success")
        print("-" * 60)
        print(f"Generated SQL:\n  {result['sql']}")
        print("-" * 60)
        print(f"Answer:\n  {result['answer']}")
    else:
        print("[FAIL] Query Failed")
        print("-" * 60)
        print(f"Error: {result['error']}")
        if result.get("sql"):
            print(f"Generated SQL: {result['sql']}")

    print("=" * 60)
    print(f"Iterations: {result.get('iterations', 1)}")


def interactive_mode():
    """Run in interactive mode."""
    print("\n" + "=" * 60)
    print("  Text-to-SQL Multi-Agent System")
    print("  Enter your question, or 'quit' to exit")
    print("=" * 60)

    pipeline = TextToSQLPipeline()

    while True:
        try:
            question = input("\n> ").strip()
            if not question:
                continue
            if question.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break

            result = pipeline.run(question)
            print_result(result)

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")


def single_query_mode(question: str):
    """Run a single query and exit."""
    pipeline = TextToSQLPipeline()
    result = pipeline.run(question)
    print_result(result)
    return 0 if result["success"] else 1


def init_mode():
    """Initialize the database with schema and test data."""
    print("Initializing database...")
    init_database()
    print("Done!")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Text-to-SQL Multi-Agent System")
    parser.add_argument("question", nargs="?", help="The question to ask")
    parser.add_argument("--init", action="store_true", help="Initialize the database")
    parser.add_argument("-i", "--interactive", action="store_true", help="Run in interactive mode")

    args = parser.parse_args()

    if args.init:
        return init_mode()

    if args.interactive or not args.question:
        interactive_mode()
        return 0

    return single_query_mode(args.question)


if __name__ == "__main__":
    sys.exit(main())
