"""DuckDB utilities for database operations."""

import re
import duckdb
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.config import DATABASE_PATH, PROJECT_ROOT

# CS-07：只读 SQL 白名单。仅允许 SELECT/WITH 起首的查询，
# 阻止 DROP/DELETE/UPDATE/INSERT/ALTER/TRUNCATE/CREATE 等以该关键字起首的 DDL/DML。
# 注意：不扫全文黑名单，避免误伤 `WHERE title LIKE '%DROP%'` 这类合法 SELECT。
_READONLY_FIRST_KW = {"SELECT", "WITH"}


def _assert_readonly_sql(sql: str) -> None:
    """确定性护栏：仅允许 SELECT/WITH 只读查询。

    判据（对抗审查修正后）：
    1) 剥离块注释 /* */ 与行注释 --，取首个关键字，必须为 SELECT/WITH；
    2) 拒绝多语句（剥离注释后含独立分号 `;` 且其后还有 token），比关键字黑名单更精准、零字面量误伤。

    已知边界（side_effects）：
    - 字符串字面量内的 `--` 或 `/*` 会被当注释剥离，偏保守，可能改变 SQL 语义；
    - SHOW/PRAGMA/EXPLAIN/DESCRIBE 走 conn.execute 直连已豁免（get_table_info/get_all_schemas/init_database），不受本护栏约束。
    """
    if not sql or not sql.strip():
        raise ValueError("execute_sql: 空 SQL")

    s = sql.strip()
    # 剥离注释（块注释 + 行注释）。注意：不区分字符串字面量，保守剥离。
    s = re.sub(r"/\*.*?\*/", " ", s, flags=re.DOTALL)
    s = re.sub(r"--.*?$", " ", s, flags=re.MULTILINE)
    s = s.strip()
    if not s:
        raise ValueError("execute_sql: 剥离注释后为空 SQL")

    # 首关键字白名单
    m = re.match(r"([A-Za-z]+)", s)
    kw = m.group(1).upper() if m else ""
    if kw not in _READONLY_FIRST_KW:
        raise ValueError(
            f"execute_sql: 仅允许 SELECT/WITH 只读查询，已拦截语句类型={kw} (sql: {s[:80]!r})"
        )

    # 多语句拒绝：DuckDB conn.execute 默认只执行单语句，但显式拦截更安全。
    # 合法单条 SELECT 末尾最多一个 `;`，其后无 token；若分号后还有内容则视为多语句。
    body = s.rstrip().rstrip(";").strip()
    if ";" in body:
        raise ValueError(f"execute_sql: 拒绝多语句执行 (sql: {s[:80]!r})")


def get_connection() -> duckdb.DuckDBPyConnection:
    """Get a connection to the DuckDB database."""
    db_path = Path(DATABASE_PATH)
    if not db_path.parent.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(database=str(db_path), read_only=False)


def execute_sql(sql: str, params: dict = None) -> list:
    """Execute a SQL query and return results.

    CS-07：入口加 SELECT-only 白名单，不依赖 review_agent 的 LLM 判断，
    即便 LLM 配合生成 DROP 也会被硬拦。
    """
    _assert_readonly_sql(sql)
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
    """Initialize the database with schema (CS-09 自举建表 + 迁移)。

    - schema.sql 存在则执行其 CREATE TABLE IF NOT EXISTS DDL；
    - 即便 schema.sql 缺失，也用内联 DDL 兜底建表（避免 FileNotFoundError 阻断）；
    - 对已存在旧 video_meta 表做列迁移（补 domain/play_count），修复旧 volume 列漂移。
    这样 text-to-sql 容器启动即自举 schema，不再依赖 bilibili-monitor 是否跑过。
    """
    conn = get_connection()
    schema_path = PROJECT_ROOT / "src" / "database" / "schema.sql"

    try:
        # 1) 优先用 schema.sql 建表
        if schema_path.exists():
            conn.execute(schema_path.read_text(encoding="utf-8"))
        else:
            print("[duckdb_utils] schema.sql 不存在，使用内联 DDL 兜底建表")

        # 2) 内联 DDL 兜底（schema.sql 缺失或部分表缺失时确保表存在）
        conn.execute(
            "CREATE TABLE IF NOT EXISTS video_meta ("
            "bvid TEXT PRIMARY KEY, up_name TEXT NOT NULL, up_uid TEXT NOT NULL, "
            "title TEXT NOT NULL, publish_date DATE, category TEXT, duration INT, "
            "play_count INT DEFAULT 0, summary TEXT, tags TEXT, "
            "domain TEXT DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS up_info ("
            "uid TEXT PRIMARY KEY, name TEXT NOT NULL, total_videos INT DEFAULT 0, "
            "last_update DATE, config_file TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS query_log ("
            "question TEXT, sql_text TEXT, success BOOLEAN, duration_ms DOUBLE, "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )

        # 3) 列迁移：旧 volume 可能缺 domain/play_count 列（与 db_writer._migrate 对齐）
        cols = [c[1] for c in conn.execute("PRAGMA table_info('video_meta')").fetchall()]
        if "domain" not in cols:
            conn.execute("ALTER TABLE video_meta ADD COLUMN domain TEXT DEFAULT ''")
            print("[duckdb_utils] 迁移：video_meta 补 domain 列")
        if "play_count" not in cols:
            conn.execute("ALTER TABLE video_meta ADD COLUMN play_count INT DEFAULT 0")
            print("[duckdb_utils] 迁移：video_meta 补 play_count 列")
        conn.commit()

        # 4) 状态日志
        result = conn.execute("SELECT COUNT(*) FROM video_meta").fetchone()
        if result[0] > 0:
            print(f"[duckdb_utils] 数据库已就绪，video_meta 含 {result[0]} 条视频。")
        else:
            print("[duckdb_utils] Schema 已就绪，video_meta 暂无数据（待 bilibili-monitor 采集）。")

    except Exception as e:
        # best-effort：建表/迁移失败不阻断 API 启动（否则 healthcheck 起不来）
        print(f"[duckdb_utils] init_database 警告: {e}")
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
