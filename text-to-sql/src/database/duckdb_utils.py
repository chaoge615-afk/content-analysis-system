"""DuckDB utilities for database operations."""

import duckdb
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.config import DATABASE_PATH, PROJECT_ROOT


def get_connection() -> duckdb.DuckDBPyConnection:
    """Get a connection to the DuckDB database."""
    db_path = Path(DATABASE_PATH)
    if not db_path.parent.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(database=str(db_path), read_only=False)


def execute_sql(sql: str, params: dict = None) -> list:
    """Execute a SQL query and return results."""
    conn = get_connection()
    try:
        if params:
            result = conn.execute(sql, params).fetchall()
        else:
            result = conn.execute(sql).fetchall()
        return result
    finally:
        conn.close()


def init_database():
    """Initialize the database with schema."""
    conn = get_connection()
    schema_path = PROJECT_ROOT / "src" / "database" / "schema.sql"

    try:
        # Read and execute schema
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        conn.execute(schema_sql)

        # Check if video_meta table exists and has data
        result = conn.execute("SELECT COUNT(*) FROM video_meta").fetchone()
        if result[0] > 0:
            print(f"Database already initialized with {result[0]} videos.")
        else:
            print("Database schema created. Video data will be added by bilibili-monitor.")

    finally:
        conn.close()


def get_table_info(table_name: str) -> dict:
    """Get table schema information."""
    conn = get_connection()
    try:
        # DuckDB DESCRIBE 返回: (column_name, column_type, null, key, default, extra)
        columns = conn.execute(f"DESCRIBE {table_name}").fetchall()
        return {
            "table": table_name,
            "columns": [
                {
                    "name": col[0],
                    "type": col[1],
                    "nullable": col[2] == "YES",
                    "key": col[3],
                    "default": col[4],
                }
                for col in columns
            ]
        }
    finally:
        conn.close()


def get_all_schemas() -> list:
    """Get schema information for all tables in the database."""
    conn = get_connection()
    try:
        # 动态查询所有表名
        tables_result = conn.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'main'
            ORDER BY table_name
        """).fetchall()

        tables = [row[0] for row in tables_result]

        # 获取每个表的 schema
        schemas = []
        for table in tables:
            try:
                # DuckDB DESCRIBE 返回: (column_name, column_type, null, key, default, extra)
                columns = conn.execute(f"DESCRIBE {table}").fetchall()
                schemas.append({
                    "table": table,
                    "columns": [
                        {
                            "name": col[0],
                            "type": col[1],
                            "nullable": col[2] == "YES",
                            "key": col[3],
                            "default": col[4],
                        }
                        for col in columns
                    ]
                })
            except Exception as e:
                print(f"Warning: Failed to get schema for table {table}: {e}")

        return schemas
    finally:
        conn.close()
