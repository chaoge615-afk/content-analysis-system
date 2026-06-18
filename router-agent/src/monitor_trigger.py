"""
bilibili-monitor 采集触发模块
通过 Docker SDK 启动 bilibili-monitor 容器，追踪运行状态和日志
"""

import os
import threading
import time
from datetime import datetime
from typing import Optional


# 监控的服务名列表（用于 system_metrics）
MONITORED_CONTAINERS = [
    "chromadb", "text-to-sql", "rag", "router-agent", "frontend"
]


class MonitorTrigger:
    """管理 bilibili-monitor 的触发和状态追踪"""

    def __init__(self):
        self._lock = threading.Lock()
        self._task: Optional[dict] = None
        self._docker_client = None
        self._start_time = datetime.now()

    def _get_client(self):
        """延迟初始化 Docker 客户端"""
        if self._docker_client is None:
            try:
                import docker
                self._docker_client = docker.from_env()
                self._docker_client.ping()
            except Exception as e:
                self._docker_client = None
                raise RuntimeError(f"Docker 连接失败: {e}")
        return self._docker_client

    @property
    def is_available(self) -> bool:
        """检查 Docker 是否可用"""
        try:
            self._get_client()
            return True
        except Exception:
            return False

    def _cleanup_old_containers(self):
        """清理旧的触发容器（exit code 137 SIGKILL 后残留）"""
        try:
            client = self._get_client()
            containers = client.containers.list(all=True)
            for c in containers:
                if c.name.startswith("bilibili-monitor-") and c.status == "exited":
                    c.remove(force=True)
        except Exception:
            pass

    def check_cookie(self) -> dict:
        """
        预检 Cookie 配置是否可用
        优先级：持久化文件 > 环境变量
        返回 { ok: bool, message: str }
        """
        # 1. 检查持久化文件（前端保存的 Cookie）
        cookie_file = os.path.join(
            os.path.dirname(os.getenv("DUCKDB_PATH", "data/content.db")),
            "bilibili_cookie.txt",
        )
        if os.path.exists(cookie_file):
            try:
                with open(cookie_file, encoding="utf-8") as f:
                    content = f.read().strip()
                if "SESSDATA" in content or "DedeUserID" in content:
                    return {
                        "ok": True,
                        "message": "Cookie 已配置（前端保存），文件: bilibili_cookie.txt",
                        "source": "file",
                    }
            except Exception:
                pass
            return {
                "ok": False,
                "message": "Cookie 文件存在但内容无效，请重新配置",
                "source": "file",
            }

        # 2. 检查环境变量
        cookie_val = os.getenv("BILIBILI_COOKIE", "")
        if not cookie_val:
            return {
                "ok": False,
                "message": "Cookie 未配置。请通过上方输入框粘贴 Cookie，或在 .env 中设置 BILIBILI_COOKIE",
                "source": "none",
            }

        # 环境变量是文件路径
        cookie_path = os.path.expanduser(cookie_val)
        if os.path.exists(cookie_path):
            return {
                "ok": True,
                "message": f"Cookie 已配置（环境变量文件）: {os.path.basename(cookie_path)}",
                "source": "env_file",
            }

        # 环境变量是 cookie 内容
        if "SESSDATA" in cookie_val or "DedeUserID" in cookie_val:
            return {
                "ok": True,
                "message": "Cookie 已配置（环境变量内容），启动时将自动写入容器",
                "source": "env_content",
            }

        return {
            "ok": False,
            "message": "BILIBILI_COOKIE 已设置但内容无效（不是文件路径，也不包含 SESSDATA/DedeUserID）",
            "source": "env",
        }

    def trigger(self, params: Optional[dict] = None) -> dict:
        """
        触发采集任务（非阻塞）

        Args:
            params: 可选参数 { max_videos, up_names }

        Returns:
            任务信息 { status, started_at, error? }
        """
        params = params or {}

        with self._lock:
            # 清理旧的触发容器（避免残留）
            self._cleanup_old_containers()

            # 预检：Cookie 配置
            cookie_check = self.check_cookie()
            if not cookie_check["ok"]:
                return {
                    "success": False,
                    "error": f"Cookie 预检失败: {cookie_check['message']}",
                }

            # 检查是否已有运行中的任务
            if self._task and self._task.get("status") == "running":
                return {
                    "success": False,
                    "error": "已有采集任务正在运行",
                    "task": self._task,
                }

            try:
                client = self._get_client()
            except RuntimeError as e:
                return {"success": False, "error": str(e)}

            # 构建容器启动参数（镜像 docker-compose.yml 中 bilibili-monitor 的配置）
            image = self._find_monitor_image(client)
            if not image:
                return {"success": False, "error": "未找到 bilibili-monitor 镜像，请先构建: docker compose build bilibili-monitor"}

            env = self._build_env(params)
            command = self._build_command(params)

            try:
                # 构建 volume 映射（卷名前缀需与 docker-compose 项目名一致）
                vol_prefix = self._get_volume_prefix()
                volumes = [
                    f"{vol_prefix}bilibili-data:/app/downloads:rw",
                    f"{vol_prefix}bilibili-data:/root/B站监控:rw",  # 实际下载目录（YAML 配置的 download_root）
                    f"{vol_prefix}bilibili-data:/app/bilibili-data:rw",  # ASR 用量存储（与 router-agent 共享）
                    f"{vol_prefix}duckdb-data:/app/data:rw",
                ]

                # 挂载本地目录（需要知道 host 路径）
                project_dir = self._detect_project_dir(client)
                if project_dir:
                    volumes.append(f"{project_dir}/bilibili-monitor/transcripts:/app/transcripts:rw")
                    volumes.append(f"{project_dir}/bilibili-monitor/chromadb:/app/chromadb:rw")
                    # 挂载 UP主 配置目录（实时读取，避免使用镜像内烘焙的旧配置）
                    volumes.append(f"{project_dir}/bilibili-monitor/config:/app/bilibili-config:rw")

                container = client.containers.run(
                    image=image,
                    name=f"bilibili-monitor-{int(time.time())}",
                    command=command,
                    environment=env,
                    volumes=volumes,
                    mem_limit="4g",
                    detach=True,
                    remove=False,  # 保留容器以便获取日志
                    network_mode=self._get_network(),
                )

                self._task = {
                    "status": "running",
                    "container_id": container.short_id,
                    "container_name": container.name,
                    "started_at": datetime.now().isoformat(),
                    "finished_at": None,
                    "error": None,
                    "logs": [],
                    "params": params,
                }

                # 启动后台线程监控容器状态
                thread = threading.Thread(
                    target=self._monitor_container,
                    args=(container.id,),
                    daemon=True,
                )
                thread.start()

                return {"success": True, "task": self._task}

            except Exception as e:
                return {"success": False, "error": f"启动容器失败: {e}"}

    def get_status(self) -> dict:
        """获取当前任务状态"""
        cookie_check = self.check_cookie()

        if self._task is None:
            return {
                "status": "idle",
                "task": None,
                "docker_available": self.is_available,
                "cookie_ok": cookie_check["ok"],
                "cookie_message": cookie_check["message"],
                "cookie_source": cookie_check.get("source", "none"),
            }

        # 如果运行中，尝试更新日志
        if self._task.get("status") == "running" and self._task.get("container_id"):
            self._update_logs()

        return {
            "status": self._task.get("status", "unknown"),
            "task": self._task,
            "docker_available": self.is_available,
            "cookie_ok": cookie_check["ok"],
            "cookie_message": cookie_check["message"],
            "cookie_source": cookie_check.get("source", "none"),
        }

    def _find_monitor_image(self, client) -> Optional[str]:
        """查找 bilibili-monitor 镜像"""
        # Docker compose 构建的镜像通常命名为 <project>_<service>
        project_name = os.getenv("COMPOSE_PROJECT_NAME", "")
        possible_names = []

        if project_name:
            possible_names.append(f"{project_name}-bilibili-monitor:latest")
            possible_names.append(f"{project_name}_bilibili-monitor:latest")
        possible_names.extend([
            "ai项目-bilibili-monitor:latest",
            "ai项目_bilibili-monitor:latest",
        ])

        images = client.images.list()
        for img in images:
            for tag in (img.tags or []):
                for name in possible_names:
                    if tag == name or tag.startswith(name.split(":")[0]):
                        return tag
                # 宽泛匹配：任何包含 bilibili-monitor 的标签
                if "bilibili-monitor" in tag:
                    return tag

        return None

    def _build_env(self, params: dict) -> dict:
        """构建容器环境变量（从 router-agent 自身环境变量透传）"""
        env_keys = [
            "QQ_BOT_URL", "QQ_USER_ID",
            "SILICONFLOW_API_KEY", "EMBEDDING_API_KEY",
            "REFINE_API_URL", "REFINE_API_KEY", "REFINE_MODEL",
            "WHISPER_DEVICE", "WHISPER_MODEL", "COMPUTE_TYPE",
            "GPU_SERVICE_URL",  # 开发机 GPU 转写服务地址
        ]
        env = {}
        for key in env_keys:
            val = os.getenv(key)
            if val:
                env[key] = val

        # 强制 Python 实时输出日志（不缓冲）
        env["PYTHONUNBUFFERED"] = "1"

        # Cookie：优先读取文件内容直接注入（避免 volume 名称不匹配导致容器找不到文件）
        cookie_file = os.path.join(
            os.path.dirname(os.getenv("DUCKDB_PATH", "data/content.db")),
            "bilibili_cookie.txt",
        )
        if os.path.exists(cookie_file):
            try:
                with open(cookie_file, encoding="utf-8") as f:
                    cookie_content = f.read().strip()
                if cookie_content:
                    # 直接传内容，cookie_utils 会写入容器文件再解析
                    env["BILIBILI_COOKIE"] = cookie_content
            except Exception:
                pass

        if "BILIBILI_COOKIE" not in env:
            # 透传环境变量
            cookie_env = os.getenv("BILIBILI_COOKIE", "")
            if cookie_env:
                env["BILIBILI_COOKIE"] = cookie_env

        # 固定配置
        env["DATABASE_PATH"] = "/app/data/content.db"
        env["CHROMA_HOST"] = "chromadb"
        env["CHROMA_PORT"] = "8000"
        env["BILIBILI_CONFIG_DIR"] = "/app/bilibili-config"
        env["BILIBILI_DATA_DIR"] = "/app/bilibili-data"

        return env

    def _build_command(self, params: dict) -> list:
        """构建容器启动命令"""
        cmd = ["python", "src/monitor_all.py"]
        if params.get("max_videos"):
            cmd.extend(["--max-videos", str(params["max_videos"])])
        if params.get("batch_size"):
            cmd.extend(["--batch-size", str(params["batch_size"])])
        if params.get("asr"):
            cmd.append("--asr")
        if params.get("full_scan"):
            cmd.append("--full-scan")
        # 支持多选 UP主（up_names 列表）
        up_names = params.get("up_names")
        if up_names:
            cmd.append("--up")
            cmd.extend(up_names)
        elif params.get("up_name"):
            # 向后兼容旧的单值参数
            cmd.extend(["--up", params["up_name"]])
        return cmd

    def _get_network(self) -> str:
        """获取 Docker 网络名称（容器需要访问 chromadb 等服务）"""
        project_name = os.getenv("COMPOSE_PROJECT_NAME", "")
        if project_name:
            return f"{project_name}_default"
        # 尝试常见的网络名
        for name in ["ai项目_default", "ai-project_default"]:
            try:
                self._get_client().networks.get(name)
                return name
            except Exception:
                continue
        return "bridge"

    def _get_volume_prefix(self) -> str:
        """
        获取 Docker Compose 命名卷的前缀

        Docker Compose 创建的卷命名为 {project_name}_{volume_name}
        例如：content-analysis-system_duckdb-data
        """
        project_name = os.getenv("COMPOSE_PROJECT_NAME", "")
        if project_name:
            return f"{project_name}_"

        # 从 router-agent 容器自身的挂载信息推断卷前缀
        try:
            hostname = os.getenv("HOSTNAME", "")
            if hostname:
                client = self._get_client()
                container = client.containers.get(hostname)
                mounts = container.attrs.get("Mounts", [])
                for mount in mounts:
                    if mount.get("Destination") == "/app/data" and mount.get("Type") == "volume":
                        vol_name = mount.get("Name", "")
                        # 卷名格式: {prefix}_duckdb-data → 提取 prefix_
                        if vol_name.endswith("_duckdb-data"):
                            return vol_name[:-len("duckdb-data")]
        except Exception:
            pass

        # 回退：尝试查找已有的 duckdb-data 卷
        try:
            client = self._get_client()
            for vol in client.volumes.list():
                name = vol.name
                if name.endswith("duckdb-data") or name.endswith("_duckdb-data"):
                    return name[:-len("duckdb-data")]
        except Exception:
            pass

        return ""  # 无前缀（使用裸卷名）

    def _detect_project_dir(self, client) -> str:
        """
        自动检测项目根目录的宿主机路径

        优先使用 PROJECT_DIR 环境变量，否则从 router-agent 容器自身的挂载信息推断
        """
        # 1. 优先使用环境变量
        project_dir = os.getenv("PROJECT_DIR", "").replace("\\", "/")
        if project_dir:
            return project_dir

        # 2. 从 router-agent 容器自身的挂载推断宿主机路径
        #    router-agent 的 /app/bilibili-config 挂载自宿主机的 bilibili-monitor/config
        try:
            hostname = os.getenv("HOSTNAME", "")
            if hostname:
                container = client.containers.get(hostname)
                mounts = container.attrs.get("Mounts", [])
                for mount in mounts:
                    if mount.get("Destination") == "/app/bilibili-config":
                        host_path = mount.get("Source", "")
                        if host_path:
                            # Source 是宿主机上的绝对路径，去掉 /bilibili-monitor/config 后缀
                            host_path = host_path.replace("\\", "/")
                            suffix = "/bilibili-monitor/config"
                            if host_path.endswith(suffix):
                                return host_path[:-len(suffix)]
        except Exception:
            pass

        return ""

    def _monitor_container(self, container_id: str):
        """后台线程：监控容器状态直到完成"""
        try:
            client = self._get_client()
            container = client.containers.get(container_id)

            # 轮询等待容器退出
            while True:
                container.reload()
                status = container.status
                if status in ("exited", "dead"):
                    break
                time.sleep(3)

            # 获取退出码和最终日志
            exit_code = container.attrs.get("State", {}).get("ExitCode", -1)
            final_logs = self._get_container_logs(container, tail=200)

            with self._lock:
                if exit_code == 0:
                    self._task["status"] = "completed"
                else:
                    self._task["status"] = "failed"
                    self._task["error"] = f"容器退出码: {exit_code}"

                self._task["finished_at"] = datetime.now().isoformat()
                self._task["logs"] = final_logs
                self._task["exit_code"] = exit_code

            # 延迟清理容器（30 秒后自动删除）
            time.sleep(30)
            try:
                container.remove(force=True)
            except Exception:
                pass

        except Exception as e:
            with self._lock:
                if self._task:
                    self._task["status"] = "failed"
                    self._task["error"] = str(e)
                    self._task["finished_at"] = datetime.now().isoformat()

    def _update_logs(self):
        """更新运行中容器的日志"""
        try:
            client = self._get_client()
            container_id = self._task.get("container_id")
            if not container_id:
                return

            # 通过短 ID 查找容器
            containers = client.containers.list(all=True)
            for c in containers:
                if c.short_id == container_id or c.id.startswith(container_id):
                    logs = self._get_container_logs(c, tail=100)
                    self._task["logs"] = logs
                    break
        except Exception:
            pass

    def _get_container_logs(self, container, tail: int = 100) -> list:
        """获取容器日志（最后 N 行）"""
        try:
            log_bytes = container.logs(tail=tail, timestamps=False)
            text = log_bytes.decode("utf-8", errors="replace")
            lines = text.strip().split("\n")
            return lines[-tail:] if len(lines) > tail else lines
        except Exception:
            return []

    def get_uptime(self) -> str:
        """获取 router-agent 运行时间"""
        delta = datetime.now() - self._start_time
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        parts = []
        if days > 0:
            parts.append(f"{days}天")
        if hours > 0:
            parts.append(f"{hours}小时")
        parts.append(f"{minutes}分钟")
        return " ".join(parts)

    def get_container_metrics(self) -> dict:
        """获取所有监控容器的资源使用指标（并行采集 stats 加速）"""
        import concurrent.futures

        metrics = {}
        try:
            client = self._get_client()
            containers = client.containers.list()
            targets = [c for c in containers if c.name in MONITORED_CONTAINERS]

            def _collect_one(c):
                """采集单个容器的指标（阻塞在 stats() 调用）"""
                info = {
                    "name": c.name,
                    "status": c.status,
                    "image": c.image.tags[0] if c.image.tags else "unknown",
                }
                if c.status == "running":
                    try:
                        stats = c.stats(stream=False)
                        mem_usage = stats.get("memory_stats", {}).get("usage", 0)
                        mem_limit = stats.get("memory_stats", {}).get("limit", 0)
                        info["memory_usage"] = mem_usage
                        info["memory_limit"] = mem_limit
                        info["memory_percent"] = round(
                            (mem_usage / mem_limit * 100) if mem_limit else 0, 1
                        )
                        cpu_stats = stats.get("cpu_stats", {})
                        precpu_stats = stats.get("precpu_stats", {})
                        cpu_delta = (
                            cpu_stats.get("cpu_usage", {}).get("total_usage", 0)
                            - precpu_stats.get("cpu_usage", {}).get("total_usage", 0)
                        )
                        system_delta = (
                            cpu_stats.get("system_cpu_usage", 0)
                            - precpu_stats.get("system_cpu_usage", 0)
                        )
                        num_cpus = cpu_stats.get("online_cpus", 1)
                        if system_delta > 0:
                            info["cpu_percent"] = round(
                                (cpu_delta / system_delta) * num_cpus * 100, 1
                            )
                        else:
                            info["cpu_percent"] = 0
                    except Exception:
                        info["memory_usage"] = 0
                        info["memory_limit"] = 0
                        info["memory_percent"] = 0
                        info["cpu_percent"] = 0
                else:
                    info["memory_usage"] = 0
                    info["memory_limit"] = 0
                    info["memory_percent"] = 0
                    info["cpu_percent"] = 0

                ports = c.attrs.get("NetworkSettings", {}).get("Ports", {})
                port_list = []
                for container_port, host_bindings in (ports or {}).items():
                    if host_bindings:
                        for binding in host_bindings:
                            port_list.append(f"{binding.get('HostPort', '?')}→{container_port}")
                info["ports"] = port_list
                return c.name, info

            # 并行采集所有容器的 stats（每个 stats() 调用阻塞 ~1.5s）
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(targets) or 1) as ex:
                futures = {ex.submit(_collect_one, c): c for c in targets}
                for fut in concurrent.futures.as_completed(futures):
                    try:
                        name, info = fut.result()
                        metrics[name] = info
                    except Exception as e:
                        c = futures[fut]
                        metrics[c.name] = {"name": c.name, "status": "error", "error": str(e)}

        except Exception as e:
            metrics["_error"] = str(e)

        return metrics
