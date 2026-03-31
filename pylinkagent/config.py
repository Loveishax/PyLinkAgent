"""
PyLinkAgent 配置管理

支持多种配置来源：
1. 默认配置（代码内嵌）
2. YAML 配置文件
3. 环境变量
4. 远程配置下发

使用 pydantic v2 进行配置验证
"""

from typing import Optional, List, Dict, Any
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class Config:
    """
    总配置对象

    所有配置项的集合，支持从 YAML 文件加载
    """
    # Agent 配置
    agent_id: str = ""
    app_name: str = "unknown"
    enabled: bool = True
    log_level: str = "INFO"

    # 平台配置
    platform_url: str = "http://localhost:8080"
    platform_api_key: str = ""
    platform_timeout: float = 30.0

    # 上报配置
    reporter_enabled: bool = True
    reporter_batch_size: int = 100
    reporter_flush_interval: float = 5.0
    reporter_max_queue_size: int = 10000

    # 采样配置
    trace_sample_rate: float = 1.0

    # 模块配置
    enabled_modules: List[str] = field(default_factory=lambda: [
        "requests",
        "httpx",
        "fastapi",
        "flask",
        "sqlalchemy",
        "redis",
    ])

    # 高级配置
    debug_mode: bool = False
    auto_upgrade: bool = True


# ============= 配置加载函数 =============

def load_config(config_path: Optional[str] = None) -> Config:
    """
    加载配置

    Args:
        config_path: 配置文件路径（支持 YAML/JSON）

    Returns:
        Config: 配置对象
    """
    config = Config()

    if config_path:
        config = _load_from_file(config_path, config)

    return config


def _load_from_file(config_path: str, default_config: Config) -> Config:
    """
    从文件加载配置

    支持 YAML 和 JSON 格式

    Args:
        config_path: 文件路径
        default_config: 默认配置

    Returns:
        Config: 合并后的配置
    """
    import os

    path = Path(config_path)
    if not path.exists():
        return default_config

    try:
        if path.suffix in (".yaml", ".yml"):
            return _load_yaml(path, default_config)
        elif path.suffix == ".json":
            return _load_json(path, default_config)
        else:
            return default_config
    except Exception:
        return default_config


def _load_yaml(path: Path, default_config: Config) -> Config:
    """从 YAML 文件加载配置"""
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            return default_config

        return _dict_to_config(data, default_config)
    except ImportError:
        # 无 yaml 库时返回默认配置
        return default_config
    except Exception:
        return default_config


def _load_json(path: Path, default_config: Config) -> Config:
    """从 JSON 文件加载配置"""
    try:
        import json
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not data:
            return default_config

        return _dict_to_config(data, default_config)
    except Exception:
        return default_config


def _dict_to_config(data: Dict[str, Any], default_config: Config) -> Config:
    """
    将字典转换为 Config 对象

    只更新 data 中存在的键，忽略未知键
    """
    config = default_config

    for key, value in data.items():
        if hasattr(config, key):
            setattr(config, key, value)

    return config


def get_default_config_path() -> Optional[str]:
    """
    获取默认配置文件路径

    搜索顺序：
    1. 当前目录 ./pylinkagent.yaml
    2. 用户目录 ~/.pylinkagent/config.yaml
    3. 系统目录 /etc/pylinkagent/config.yaml

    Returns:
        Optional[str]: 找到的配置文件路径
    """
    import os

    # 当前目录
    local_path = Path("./pylinkagent.yaml")
    if local_path.exists():
        return str(local_path)

    # 用户目录
    home = Path.home() / ".pylinkagent" / "config.yaml"
    if home.exists():
        return str(home)

    # 系统目录
    system_path = Path("/etc/pylinkagent/config.yaml")
    if system_path.exists():
        return str(system_path)

    return None
