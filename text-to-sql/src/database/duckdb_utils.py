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
    """Initialize the database with schema and test data."""
    conn = get_connection()
    schema_path = PROJECT_ROOT / "src" / "database" / "schema.sql"

    try:
        # Read and execute schema
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        conn.execute(schema_sql)

        # Check if data already exists
        result = conn.execute("SELECT COUNT(*) FROM food").fetchone()
        if result[0] > 0:
            print("Database already initialized.")
            return

        # Insert test food data
        foods = [
            (1, "鸡蛋", 144.0, 13.3, 8.8, 1.1),
            (2, "鸡胸肉", 133.0, 31.0, 1.2, 0.0),
            (3, "米饭", 116.0, 2.6, 0.3, 25.9),
            (4, "面条", 284.0, 8.2, 0.6, 59.5),
            (5, "苹果", 52.0, 0.3, 0.2, 13.8),
            (6, "香蕉", 89.0, 1.1, 0.2, 22.8),
            (7, "牛奶", 54.0, 3.2, 3.3, 3.4),
            (8, "酸奶", 72.0, 2.9, 1.9, 10.3),
            (9, "牛肉", 250.0, 26.1, 15.0, 0.0),
            (10, "白菜", 17.0, 1.4, 0.1, 3.4),
        ]
        conn.executemany(
            "INSERT INTO food (id, name, calorie, protein, fat, carb) VALUES (?, ?, ?, ?, ?, ?)",
            foods
        )

        # Insert test daily records (last 7 days)
        from datetime import date, timedelta
        today = date.today()
        daily_records = []
        for i in range(7):
            d = today - timedelta(days=i)
            daily_records.append((
                i + 1,            # id
                d.isoformat(),
                1800.0 + i * 50,  # total_calorie
                65.0 + i * 2,    # total_protein
                2000.0,           # target_calorie
                70.0              # target_protein
            ))
        conn.executemany(
            "INSERT INTO daily_record (id, date, total_calorie, total_protein, target_calorie, target_protein) VALUES (?, ?, ?, ?, ?, ?)",
            daily_records
        )

        # Insert meal records
        meal_records = [
            (1, 1, "早餐", 1, 100),   # id, daily_id, meal_type, food_id, weight_g
            (2, 1, "午餐", 3, 200),   # day 1, rice
            (3, 1, "晚餐", 2, 150),   # day 1, chicken
            (4, 2, "早餐", 7, 200),   # day 2, milk
            (5, 2, "午餐", 9, 100),   # day 2, beef
            (6, 3, "早餐", 6, 150),   # day 3, banana
            (7, 3, "午餐", 4, 100),   # day 3, noodles
        ]
        conn.executemany(
            "INSERT INTO meal_record (id, daily_id, meal_type, food_id, weight_g) VALUES (?, ?, ?, ?, ?)",
            meal_records
        )

        print("Database initialized successfully.")

    finally:
        conn.close()


def get_table_info(table_name: str) -> dict:
    """Get table schema information."""
    conn = get_connection()
    try:
        # Get column info
        columns = conn.execute(f"DESCRIBE {table_name}").fetchall()
        return {
            "table": table_name,
            "columns": [{"name": col[0], "type": col[1], "comment": col[2]} for col in columns]
        }
    finally:
        conn.close()


def get_all_schemas() -> list:
    """Get schema information for all tables."""
    tables = ["food", "daily_record", "meal_record"]
    return [get_table_info(t) for t in tables]
