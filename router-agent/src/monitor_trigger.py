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

    def check_cookie(self) -> dict:
        """
        预检 Cookie 配置是否可用
        返回 { ok: bool, message: str }
        """
        cookie_val = os.getenv("BILIBILI_COOKIE", "")
        if not cookie_val:
            return {
                "ok": False,
                "message": "环境变量 BILIBILI_COOKIE 未设置。请在 .env 中配置 BILIBILI_COOKIE（Cookie 文件路径或内容）",
            }

        # 如果是文件路径，检查文件是否存在
        cookie_path = os.path.expanduser(cookie_val)
        if os.path.exists(cookie_path):
            return {
                "ok": True,
                "message": f"Cookie 文件就绪: {os.path.basename(cookie_path)}",
            }

        # 不是路径，检查是否像 Netscape cookie 内容（至少包含 SESSDATA 或 DedeUserID）
        if "SESSDATA" in cookie_val or "DedeUserID" in cookie_val:
            return {
                "ok": True,
                "message": "Cookie 内容已配置（环境变量），启动时将自动写入容器",
            }

        return {
            "ok": False,
            "message": "BILIBILI_COOKIE 已设置但内容无效（不是文件路径，也不包含 SESSDATA/DedeUserID）",
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
                # 构建 volume 映射
                # 注意：Docker SDK 需要 host 路径，不能用 named volumes
                # 但 named volumes 在 Docker daemon 层面是可以的
                volumes = {
                    "bilibili-data": {"bind": "/app/downloads", "mode": "rw"},
                    "duckdb-data": {"bind": "/app/data", "mode": "rw"},
                }

                # 挂载本地目录（需要知道 host 路径）
                project_dir = os.getenv("PROJECT_DIR", "")
                if project_dir:
                    volumes[f"{project_dir}/bilibili-monitor/transcripts"] = {
                        "bind": "/app/transcripts", "mode": "rw"
                    }
                    volumes[f"{project_dir}/bilibili-monitor/chromadb"] = {
                        "bind": "/app/chromadb", "mode": "rw"
                    }

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
            "BILIBILI_COOKIE", "QQ_BOT_URL", "QQ_USER_ID",
            "SILICONFLOW_API_KEY", "EMBEDDING_API_KEY",
            "REFINE_API_URL", "REFINE_API_KEY",
            "WHISPER_DEVICE", "WHISPER_MODEL", "COMPUTE_TYPE",
        ]
        env = {}
        for key in env_keys:
            val = os.getenv(key)
            if val:
                env[key] = val

        # 固定配置
        env["DATABASE_PATH"] = "/app/data/content.db"
        env["CHROMA_HOST"] = "chromadb"
        env["CHROMA_PORT"] = "8000"

        return env

    def _build_command(self, params: dict) -> list:
        """构建容器启动命令"""
        cmd = ["python", "scripts/monitor_all.py"]
        if params.get("max_videos"):
            cmd.extend(["--max-videos", str(params["max_videos"])])
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
        """获取所有监控容器的资源使用指标"""
        metrics = {}
        try:
            client = self._get_client()
            containers = client.containers.list()

            for c in containers:
                name = c.name
                if name not in MONITORED_CONTAINERS:
                    continue

                info = {
                    "name": name,
                    "status": c.status,
                    "image": c.image.tags[0] if c.image.tags else "unknown",
                }

                # 获取内存使用
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

                        # CPU 使用率
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

                # 端口映射
                ports = c.attrs.get("NetworkSettings", {}).get("Ports", {})
                port_list = []
                for container_port, host_bindings in (ports or {}).items():
                    if host_bindings:
                        for binding in host_bindings:
                            port_list.append(f"{binding.get('HostPort', '?')}→{container_port}")
                info["ports"] = port_list

                metrics[name] = info

        except Exception as e:
            metrics["_error"] = str(e)

        return metrics
