"""
PyLinkAgent 影子库配置中心

支持多种配置方式：
1. YAML 配置文件
2. 环境变量
3. API 动态注册
4. 远程配置中心
5. 用户自定义配置
"""

from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
from pathlib import Path
import os
import json
import logging

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

from .config import ShadowDatabaseConfig, ShadowConfigManager

logger = logging.getLogger(__name__)


@dataclass
class ShadowConfigSource:
    """配置来源配置"""
    # 文件配置
    config_file: Optional[str] = None  # YAML/JSON 配置文件路径

    # 环境变量配置
    env_enabled: bool = True
    env_prefix: str = "PYLINKAGENT_SHADOW_"

    # 远程配置中心
    remote_enabled: bool = False
    remote_url: str = ""
    remote_api_key: str = ""
    remote_poll_interval: int = 60  # 秒

    # API 服务器 (用于接收配置)
    api_enabled: bool = True
    api_host: str = "0.0.0.0"
    api_port: int = 8081


class ShadowConfigCenter:
    """
    影子库配置中心

    统一管理所有配置来源，支持：
    - 配置文件加载
    - 环境变量覆盖
    - 远程配置同步
    - API 动态注册
    - 配置热更新
    """

    def __init__(self, source: Optional[ShadowConfigSource] = None):
        self.source = source or ShadowConfigSource()
        self.config_manager = ShadowConfigManager()
        self._remote_task = None
        self._api_server = None

    def load_all(self) -> int:
        """
        加载所有配置来源

        加载顺序（优先级从低到高）：
        1. YAML 配置文件
        2. 环境变量
        3. 远程配置中心
        4. API 动态注册（运行时）

        Returns:
            加载的配置数量
        """
        count = 0

        # 1. 加载配置文件
        if self.source.config_file:
            count += self._load_from_file(self.source.config_file)

        # 2. 环境变量覆盖
        if self.source.env_enabled:
            count += self._load_from_env()

        # 3. 远程配置中心
        if self.source.remote_enabled:
            self._start_remote_sync()

        # 4. 启动 API 服务器
        if self.source.api_enabled:
            self._start_api_server()

        logger.info(f"ShadowConfigCenter 加载完成，共 {count} 个配置")
        return count

    def _load_from_file(self, config_file: str) -> int:
        """
        从配置文件加载

        支持 YAML 和 JSON 格式

        配置文件示例:
        ```yaml
        shadow_databases:
          - ds_type: 0
            url: jdbc:mysql://localhost:3306/test
            username: root
            password: password
            shadow_url: jdbc:mysql://localhost:3306/shadow_test
            shadow_username: PT_root
            shadow_password: PT_password
            shadow_account_prefix: PT_
            business_shadow_tables:
              users: shadow_users
              orders: shadow_orders
        ```
        """
        path = Path(config_file)
        if not path.exists():
            logger.warning(f"配置文件不存在：{config_file}")
            return 0

        try:
            if path.suffix in (".yaml", ".yml"):
                import yaml
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
            elif path.suffix == ".json":
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                return 0

            if not data or "shadow_databases" not in data:
                return 0

            configs = data.get("shadow_databases", [])
            return self.config_manager.load_from_dict(configs)

        except Exception as e:
            logger.error(f"加载配置文件失败：{e}")
            return 0

    def _load_from_env(self) -> int:
        """
        从环境变量加载配置

        环境变量格式:
        PYLINKAGENT_SHADOW_CONFIGS=[{"url":"...", "shadow_url":"...", ...}]

        或单个配置:
        PYLINKAGENT_SHADOW_URL=jdbc:mysql://localhost:3306/test
        PYLINKAGENT_SHADOW_SHADOW_URL=jdbc:mysql://localhost:3306/shadow_test
        """
        count = 0

        # 方式 1: JSON 数组格式
        configs_json = os.getenv(f"{self.source.env_prefix}CONFIGS")
        if configs_json:
            try:
                configs = json.loads(configs_json)
                if isinstance(configs, list):
                    count += self.config_manager.load_from_dict(configs)
            except json.JSONDecodeError as e:
                logger.error(f"解析环境变量 CONFIGS 失败：{e}")

        # 方式 2: 单个配置（多个环境变量）
        shadow_url = os.getenv(f"{self.source.env_prefix}SHADOW_URL")
        biz_url = os.getenv(f"{self.source.env_prefix}URL")

        if shadow_url and biz_url:
            config = ShadowDatabaseConfig(
                url=biz_url,
                shadow_url=shadow_url,
                username=os.getenv(f"{self.source.env_prefix}USERNAME", ""),
                shadow_username=os.getenv(f"{self.source.env_prefix}SHADOW_USERNAME"),
                password=os.getenv(f"{self.source.env_prefix}PASSWORD", ""),
                shadow_password=os.getenv(f"{self.source.env_prefix}SHADOW_PASSWORD"),
                shadow_account_prefix=os.getenv(f"{self.source.env_prefix}ACCOUNT_PREFIX", "PT_"),
                shadow_account_suffix=os.getenv(f"{self.source.env_prefix}ACCOUNT_SUFFIX", ""),
                business_shadow_tables=self._parse_table_mapping(
                    os.getenv(f"{self.source.env_prefix}TABLE_MAPPING", "")
                ),
            )
            self.config_manager.register_config(config)
            count += 1

        return count

    def _parse_table_mapping(self, value: str) -> Dict[str, str]:
        """
        解析表名映射字符串

        格式：users:shadow_users,orders:shadow_orders
        """
        if not value:
            return {}

        result = {}
        for item in value.split(","):
            if ":" in item:
                key, val = item.split(":", 1)
                result[key.strip()] = val.strip()

        return result

    def _start_remote_sync(self) -> None:
        """启动远程配置同步"""
        if not self.source.remote_url:
            logger.error("远程配置 URL 未设置")
            return

        logger.info(f"启动远程配置同步：{self.source.remote_url}")
        # TODO: 实现定时同步任务
        # 可以使用 asyncio.create_task 或 threading.Timer

    def _start_api_server(self) -> None:
        """
        启动配置 API 服务器

        提供 REST API 用于动态注册/更新/删除配置
        """
        import threading
        from http.server import HTTPServer, BaseHTTPRequestHandler

        class ConfigAPIHandler(BaseHTTPRequestHandler):
            def __init__(self, *args, center=None, **kwargs):
                self.center = center
                super().__init__(*args, **kwargs)

            def do_GET(self, *args, **kwargs):
                if self.path == "/health":
                    self._send_json({"status": "ok"})
                elif self.path == "/configs":
                    configs = self.center.config_manager.get_all_configs()
                    self._send_json({
                        "count": len(configs),
                        "configs": [self._config_to_dict(c) for c in configs]
                    })
                else:
                    self.send_error(404)

            def do_POST(self, *args, **kwargs):
                if self.path == "/configs/register":
                    content_length = int(self.headers.get("Content-Length", 0))
                    body = self.rfile.read(content_length)
                    try:
                        data = json.loads(body)
                        config = self._dict_to_config(data)
                        self.center.config_manager.register_config(config)
                        self._send_json({"status": "success", "message": "配置已注册"})
                    except Exception as e:
                        self._send_json({"status": "error", "message": str(e)}, status=400)
                elif self.path == "/configs/unregister":
                    content_length = int(self.headers.get("Content-Length", 0))
                    body = self.rfile.read(content_length)
                    try:
                        data = json.loads(body)
                        url = data.get("url")
                        username = data.get("username")
                        if self.center.config_manager.unregister_config(url, username):
                            self._send_json({"status": "success", "message": "配置已删除"})
                        else:
                            self._send_json({"status": "error", "message": "配置不存在"}, status=404)
                    except Exception as e:
                        self._send_json({"status": "error", "message": str(e)}, status=400)
                else:
                    self.send_error(404)

            def _send_json(self, data: dict, status=200):
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())

            def _config_to_dict(self, config: ShadowDatabaseConfig) -> dict:
                return {
                    "ds_type": config.ds_type,
                    "url": config.url,
                    "username": config.username,
                    "shadow_url": config.shadow_url,
                    "shadow_username": config.shadow_username,
                    "shadow_account_prefix": config.shadow_account_prefix,
                    "business_shadow_tables": config.business_shadow_tables,
                }

            def _dict_to_config(self, data: dict) -> ShadowDatabaseConfig:
                return ShadowDatabaseConfig(
                    ds_type=data.get("ds_type", 0),
                    url=data.get("url", ""),
                    username=data.get("username", ""),
                    password=data.get("password", ""),
                    shadow_url=data.get("shadow_url", ""),
                    shadow_username=data.get("shadow_username"),
                    shadow_password=data.get("shadow_password"),
                    shadow_account_prefix=data.get("shadow_account_prefix", "PT_"),
                    shadow_account_suffix=data.get("shadow_account_suffix", ""),
                    business_shadow_tables=data.get("business_shadow_tables", {}),
                )

        def run_server():
            handler = lambda *args, **kwargs: ConfigAPIHandler(*args, center=self, **kwargs)
            server = HTTPServer((self.source.api_host, self.source.api_port), handler)
            logger.info(f"配置 API 服务器启动：http://{self.source.api_host}:{self.source.api_port}")
            server.serve_forever()

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        self._api_server = thread

    def get_config(self, url: str, username: Optional[str] = None) -> Optional[ShadowDatabaseConfig]:
        """获取影子库配置"""
        return self.config_manager.get_shadow_config(url, username)

    def register_config(self, config: ShadowDatabaseConfig) -> bool:
        """注册影子库配置"""
        return self.config_manager.register_config(config)

    def unregister_config(self, url: str, username: Optional[str] = None) -> bool:
        """注销影子库配置"""
        return self.config_manager.unregister_config(url, username)

    def get_all_configs(self) -> List[ShadowDatabaseConfig]:
        """获取所有配置"""
        return self.config_manager.get_all_configs()


# ============= 全局配置中心实例 =============

_global_config_center: Optional[ShadowConfigCenter] = None


def get_config_center() -> ShadowConfigCenter:
    """获取全局配置中心"""
    global _global_config_center
    if _global_config_center is None:
        _global_config_center = ShadowConfigCenter()
    return _global_config_center


def init_config_center(source: Optional[ShadowConfigSource] = None) -> ShadowConfigCenter:
    """初始化配置中心"""
    global _global_config_center
    _global_config_center = ShadowConfigCenter(source)
    _global_config_center.load_all()
    return _global_config_center


# ============= 便捷函数 =============

def load_from_file(config_file: str) -> int:
    """从配置文件加载影子库配置"""
    return get_config_center()._load_from_file(config_file)


def load_from_env() -> int:
    """从环境变量加载影子库配置"""
    return get_config_center()._load_from_env()


def register_config(config: ShadowDatabaseConfig) -> bool:
    """注册影子库配置"""
    return get_config_center().register_config(config)


def get_config(url: str, username: Optional[str] = None) -> Optional[ShadowDatabaseConfig]:
    """获取影子库配置"""
    return get_config_center().get_config(url, username)
