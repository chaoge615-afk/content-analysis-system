-- Text-to-SQL 数据库 Schema（与 bilibili-monitor/src/db_writer.py _init_tables 对齐）
-- CS-09 修复：补齐 text-to-sql 容器的自动建表入口，避免全新 volume 首启时 video_meta 整表缺失触发 DuckDB Catalog Error。
-- 全部 CREATE TABLE IF NOT EXISTS，旧 volume 安全，新 volume 自建。
-- 列定义与 db_writer._init_tables + _migrate 一致（含 domain/play_count）。

CREATE TABLE IF NOT EXISTS video_meta (
    bvid        TEXT PRIMARY KEY,
    up_name     TEXT NOT NULL,
    up_uid      TEXT NOT NULL,
    title       TEXT NOT NULL,
    publish_date DATE,
    category    TEXT,
    duration    INT,
    play_count  INT DEFAULT 0,
    summary     TEXT,
    tags        TEXT,
    domain      TEXT DEFAULT '',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS up_info (
    uid          TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    total_videos INT DEFAULT 0,
    last_update  DATE,
    config_file  TEXT,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- query_log 由 router-agent QueryLogger 建，这里 IF NOT EXISTS 兜底，列定义与之对齐：
CREATE TABLE IF NOT EXISTS query_log (
    question    TEXT,
    sql_text    TEXT,
    success     BOOLEAN,
    duration_ms DOUBLE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
