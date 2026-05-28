"""
UP主数据导入导出模块
支持将 UP主 的完整数据（配置、视频元数据、向量嵌入、转写文本、检查点）
打包为 ZIP 文件，用于跨环境迁移（开发机 → NAS）
"""

import io
import os
import json
import zipfile
import tempfile
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Dict, Any, List

import duckdb
import yaml


def _json_serializer(obj):
    """JSON 序列化器，处理 date/datetime/numpy 类型"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    # numpy array → list
    if hasattr(obj, 'tolist'):
        return obj.tolist()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class UpExporter:
    """UP主数据导入导出器"""

    def __init__(
        self,
        config_dir: Optional[str] = None,
        db_path: Optional[str] = None,
        chroma_host: Optional[str] = None,
        chroma_port: int = 8000,
    ):
        """
        初始化导入导出器

        Args:
            config_dir: UP主配置文件目录
            db_path: DuckDB 数据库路径
            chroma_host: ChromaDB 主机地址
            chroma_port: ChromaDB 端口
        """
        self.config_dir = Path(
            config_dir
            or os.getenv(
                "BILIBILI_CONFIG_DIR",
                str(Path(__file__).parent.parent.parent / "bilibili-monitor" / "config"),
            )
        )
        self.db_path = db_path or os.getenv("DUCKDB_PATH", "data/content.db")
        self.chroma_host = chroma_host or os.getenv("CHROMA_HOST", "chromadb")
        self.chroma_port = int(os.getenv("CHROMA_PORT", str(chroma_port)))

    def _get_chroma_client(self):
        """获取 ChromaDB 客户端"""
        import chromadb
        from chromadb.config import Settings

        return chromadb.HttpClient(
            host=self.chroma_host,
            port=self.chroma_port,
            settings=Settings(anonymized_telemetry=False),
        )

    def _find_config(self, uid: str) -> Optional[Path]:
        """查找 UP主 配置文件"""
        # 优先按 UID 查找
        config_path = self.config_dir / f"{uid}.yaml"
        if config_path.exists():
            return config_path

        # 遍历所有 YAML 查找匹配的 UID
        for yaml_file in self.config_dir.glob("*.yaml"):
            try:
                with open(yaml_file, encoding="utf-8") as f:
                    cfg = yaml.safe_load(f)
                if str(cfg.get("uid", "")) == uid:
                    return yaml_file
            except Exception:
                continue

        return None

    def _read_config(self, config_path: Path) -> Dict[str, Any]:
        """读取 YAML 配置"""
        with open(config_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _query_duckdb(self, uid: str, name: str) -> Dict[str, Any]:
        """查询 DuckDB 中的 UP主 数据"""
        conn = duckdb.connect(self.db_path, read_only=True)
        try:
            # 查询 up_info
            up_info_rows = conn.execute(
                "SELECT * FROM up_info WHERE uid = ?", [uid]
            ).fetchall()
            up_info_columns = [desc[0] for desc in conn.description]

            # 查询 video_meta
            video_rows = conn.execute(
                "SELECT * FROM video_meta WHERE up_uid = ?", [uid]
            ).fetchall()
            video_columns = [desc[0] for desc in conn.description]

            # 转换为字典列表
            up_info = [dict(zip(up_info_columns, row)) for row in up_info_rows]
            videos = [dict(zip(video_columns, row)) for row in video_rows]

            return {
                "up_info": up_info,
                "videos": videos,
            }
        finally:
            conn.close()

    def _query_chromadb(self, name: str) -> Dict[str, Any]:
        """查询 ChromaDB 中的 UP主 数据"""
        client = self._get_chroma_client()
        collection = client.get_or_create_collection(
            name="video_knowledge",
            metadata={"description": "B站视频转写和精炼知识库"},
        )

        # 按 up_name 查询所有文档
        results = collection.get(
            where={"up_name": name},
            include=["documents", "metadatas", "embeddings"],
        )

        return {
            "ids": results.get("ids", []),
            "documents": results.get("documents", []),
            "metadatas": results.get("metadatas", []),
            "embeddings": results.get("embeddings", []),
        }

    def _scan_transcripts(self, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """扫描转写文本文件"""
        transcribe_dir = config.get("transcribe_output_dir", "")
        if not transcribe_dir:
            return []

        up_name = config.get("name", "")
        if not up_name:
            return []

        # UP主 子目录（替换不安全字符）
        up_safe = up_name.replace("/", "_").replace("\\", "_")
        up_dir = Path(transcribe_dir) / up_safe

        if not up_dir.exists():
            return []

        transcripts = []
        for txt_file in up_dir.glob("*.txt"):
            try:
                with open(txt_file, encoding="utf-8") as f:
                    content = f.read()
                transcripts.append({
                    "filename": txt_file.name,
                    "content": content,
                })
            except Exception:
                continue

        return transcripts

    def _read_checkpoints(self, uid: str) -> Dict[str, str]:
        """读取检查点文件"""
        # 检查点文件在 bilibili-monitor/data/ 目录
        data_dir = Path(__file__).parent.parent.parent / "bilibili-monitor" / "data"

        checkpoints = {}

        # done_bvid.txt
        done_file = data_dir / f"{uid}_done_bvid.txt"
        if done_file.exists():
            try:
                with open(done_file, encoding="utf-8") as f:
                    checkpoints["done_bvid"] = f.read()
            except Exception:
                pass

        # downloaded.txt
        downloaded_file = data_dir / f"{uid}_downloaded.txt"
        if downloaded_file.exists():
            try:
                with open(downloaded_file, encoding="utf-8") as f:
                    checkpoints["downloaded"] = f.read()
            except Exception:
                pass

        return checkpoints

    def export_up(self, uid: str) -> bytes:
        """
        导出 UP主 完整数据为 ZIP 字节

        Args:
            uid: UP主 UID

        Returns:
            ZIP 文件的字节数据

        Raises:
            ValueError: UP主 不存在
        """
        # 1. 查找配置
        config_path = self._find_config(uid)
        if not config_path:
            raise ValueError(f"未找到 UID {uid} 的配置文件")

        config = self._read_config(config_path)
        name = config.get("name", "unknown")

        # 2. 查询 DuckDB
        db_data = self._query_duckdb(uid, name)

        # 3. 查询 ChromaDB
        chroma_data = self._query_chromadb(name)

        # 4. 扫描转写文件
        transcripts = self._scan_transcripts(config)

        # 5. 读取检查点
        checkpoints = self._read_checkpoints(uid)

        # 6. 打包 ZIP
        date_str = datetime.now().strftime("%Y%m%d")
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # manifest.json
            manifest = {
                "version": "1.0",
                "uid": uid,
                "name": name,
                "video_count": len(db_data["videos"]),
                "transcript_count": len(transcripts),
                "chromadb_doc_count": len(chroma_data["ids"]),
                "transcribe_output_dir": config.get("transcribe_output_dir", ""),
                "exported_at": datetime.now().isoformat(),
            }
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2, default=_json_serializer))

            # config.yaml
            with open(config_path, encoding="utf-8") as f:
                zf.writestr("config.yaml", f.read())

            # up_info.json
            zf.writestr("up_info.json", json.dumps(db_data["up_info"], ensure_ascii=False, indent=2, default=_json_serializer))

            # videos.json
            zf.writestr("videos.json", json.dumps(db_data["videos"], ensure_ascii=False, indent=2, default=_json_serializer))

            # chromadb.json
            zf.writestr("chromadb.json", json.dumps(chroma_data, ensure_ascii=False, indent=2, default=_json_serializer))

            # transcripts/
            for transcript in transcripts:
                zf.writestr(f"transcripts/{transcript['filename']}", transcript["content"])

            # checkpoints/
            for cp_name, cp_content in checkpoints.items():
                zf.writestr(f"checkpoints/{uid}_{cp_name}.txt", cp_content)

        return zip_buffer.getvalue()

    def import_up(self, zip_bytes: bytes, overwrite: bool = False) -> Dict[str, Any]:
        """
        从 ZIP 字节导入 UP主 数据

        Args:
            zip_bytes: ZIP 文件的字节数据
            overwrite: 是否覆盖已有数据

        Returns:
            导入结果统计
        """
        # 1. 解压并读取 manifest
        zip_buffer = io.BytesIO(zip_bytes)
        with zipfile.ZipFile(zip_buffer, "r") as zf:
            # 读取 manifest
            manifest = json.loads(zf.read("manifest.json"))
            uid = manifest["uid"]
            name = manifest["name"]

            # 读取各部分数据
            config_yaml = zf.read("config.yaml").decode("utf-8")
            up_info_data = json.loads(zf.read("up_info.json"))
            videos_data = json.loads(zf.read("videos.json"))
            chroma_data = json.loads(zf.read("chromadb.json"))

            # 读取转写文件
            transcripts = []
            for filename in zf.namelist():
                if filename.startswith("transcripts/") and filename.endswith(".txt"):
                    content = zf.read(filename).decode("utf-8")
                    transcripts.append({
                        "filename": filename.split("/")[-1],
                        "content": content,
                    })

            # 读取检查点
            checkpoints = {}
            for filename in zf.namelist():
                if filename.startswith("checkpoints/"):
                    content = zf.read(filename).decode("utf-8")
                    cp_name = filename.split("/")[-1].replace(f"{uid}_", "").replace(".txt", "")
                    checkpoints[cp_name] = content

        # 2. 写入配置文件
        config = yaml.safe_load(config_yaml)

        # 先检查是否已有同 UID 的配置文件（可能文件名不是 {uid}.yaml）
        existing_config = self._find_config(uid)
        if existing_config:
            config_path = existing_config
        else:
            # 新 UP主，使用名称作为文件名
            safe_name = name.replace("/", "_").replace("\\", "_").replace(":", "_")
            config_path = self.config_dir / f"{safe_name}.yaml"

        config_written = False
        if config_path.exists():
            if overwrite:
                with open(config_path, "w", encoding="utf-8") as f:
                    f.write(config_yaml)
                config_written = True
        else:
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(config_yaml)
            config_written = True

        # 3. 写入 DuckDB
        conn = duckdb.connect(self.db_path, read_only=False)
        try:
            videos_written = 0
            up_info_written = 0

            # up_info
            for row in up_info_data:
                if overwrite:
                    conn.execute(
                        """INSERT OR REPLACE INTO up_info
                           (uid, name, total_videos, last_update, config_file, created_at)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        [
                            row["uid"],
                            row["name"],
                            row["total_videos"],
                            row.get("last_update"),
                            row.get("config_file"),
                            row.get("created_at"),
                        ],
                    )
                    up_info_written += 1
                else:
                    # 检查是否存在
                    existing = conn.execute(
                        "SELECT uid FROM up_info WHERE uid = ?", [row["uid"]]
                    ).fetchone()
                    if not existing:
                        conn.execute(
                            """INSERT INTO up_info
                               (uid, name, total_videos, last_update, config_file, created_at)
                               VALUES (?, ?, ?, ?, ?, ?)""",
                            [
                                row["uid"],
                                row["name"],
                                row["total_videos"],
                                row.get("last_update"),
                                row.get("config_file"),
                                row.get("created_at"),
                            ],
                        )
                        up_info_written += 1

            # video_meta
            for row in videos_data:
                if overwrite:
                    conn.execute(
                        """INSERT OR REPLACE INTO video_meta
                           (bvid, up_name, up_uid, title, publish_date, category, duration, summary, tags, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        [
                            row["bvid"],
                            row["up_name"],
                            row["up_uid"],
                            row["title"],
                            row.get("publish_date"),
                            row.get("category"),
                            row.get("duration"),
                            row.get("summary"),
                            row.get("tags"),
                            row.get("created_at"),
                        ],
                    )
                    videos_written += 1
                else:
                    existing = conn.execute(
                        "SELECT bvid FROM video_meta WHERE bvid = ?", [row["bvid"]]
                    ).fetchone()
                    if not existing:
                        conn.execute(
                            """INSERT INTO video_meta
                               (bvid, up_name, up_uid, title, publish_date, category, duration, summary, tags, created_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            [
                                row["bvid"],
                                row["up_name"],
                                row["up_uid"],
                                row["title"],
                                row.get("publish_date"),
                                row.get("category"),
                                row.get("duration"),
                                row.get("summary"),
                                row.get("tags"),
                                row.get("created_at"),
                            ],
                        )
                        videos_written += 1

            conn.commit()
        finally:
            conn.close()

        # 4. 写入 ChromaDB
        chroma_written = 0
        if chroma_data["ids"]:
            client = self._get_chroma_client()
            collection = client.get_or_create_collection(
                name="video_knowledge",
                metadata={"description": "B站视频转写和精炼知识库"},
            )

            # 收集所有 bvid，先删除旧数据
            bvids = set()
            for meta in chroma_data["metadatas"]:
                if "bvid" in meta:
                    bvids.add(meta["bvid"])

            for bvid in bvids:
                existing = collection.get(where={"bvid": bvid})
                if existing["ids"]:
                    collection.delete(ids=existing["ids"])

            # 添加新数据
            collection.add(
                ids=chroma_data["ids"],
                documents=chroma_data["documents"],
                metadatas=chroma_data["metadatas"],
                embeddings=chroma_data["embeddings"],
            )
            chroma_written = len(chroma_data["ids"])

        # 5. 写入转写文件
        transcripts_written = 0
        transcribe_dir = config.get("transcribe_output_dir", "")
        if transcribe_dir and transcripts:
            up_safe = name.replace("/", "_").replace("\\", "_")
            up_dir = Path(transcribe_dir) / up_safe
            up_dir.mkdir(parents=True, exist_ok=True)

            for transcript in transcripts:
                txt_path = up_dir / transcript["filename"]
                if txt_path.exists() and not overwrite:
                    continue
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(transcript["content"])
                transcripts_written += 1

        # 6. 写入检查点
        checkpoints_written = 0
        data_dir = Path(__file__).parent.parent.parent / "bilibili-monitor" / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        for cp_name, cp_content in checkpoints.items():
            cp_path = data_dir / f"{uid}_{cp_name}.txt"
            if cp_path.exists() and not overwrite:
                continue
            with open(cp_path, "w", encoding="utf-8") as f:
                f.write(cp_content)
            checkpoints_written += 1

        return {
            "success": True,
            "imported": {
                "uid": uid,
                "name": name,
                "config_written": config_written,
                "up_info_written": up_info_written,
                "videos_written": videos_written,
                "chromadb_written": chroma_written,
                "transcripts_written": transcripts_written,
                "checkpoints_written": checkpoints_written,
            },
        }
