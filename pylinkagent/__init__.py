"""
PyLinkAgent - Python 运行时探针

零代码侵入的 Python 应用监控与函数控制探针。
通过运行时插桩技术实现对 Python 应用的数据采集和函数控制。

Usage:
    # 方式 1: 环境变量注入
    export PYLINKAGENT_ENABLED=true
    python app.py

    # 方式 2: 包装器启动
    pylinkagent-run python app.py

    # 方式 3: 代码中导入（需最早导入）
    import pylinkagent
    pylinkagent.bootstrap()

Author: PyLinkAgent Team
License: Apache 2.0
"""

from typing import Optional, Dict, Any
import os
import sys
import logging

from .version import __version__
from .logger import setup_logger
from .config import Config, load_config
from .core.agent import Agent
from .lifecycle.manager import LifecycleManager

# 模块级别的全局状态
_initialized: bool = False
_agent: Optional[Agent] = None
_lifecycle_manager: Optional[LifecycleManager] = None
_config: Optional[Config] = None
_logger: Optional[logging.Logger] = None

# 环境变量常量
ENV_ENABLED = "PYLINKAGENT_ENABLED"
ENV_CONFIG_PATH = "PYLINKAGENT_CONFIG_PATH"
ENV_LOG_LEVEL = "PYLINKAGENT_LOG_LEVEL"
ENV_AGENT_ID = "PYLINKAGENT_AGENT_ID"
ENV_PLATFORM_URL = "PYLINKAGENT_PLATFORM_URL"


def bootstrap(config_path: Optional[str] = None, **kwargs: Any) -> bool:
    """
    引导并启动 PyLinkAgent 探针

    这是探针的主入口函数，负责：
    1. 检查并加载配置
    2. 初始化日志系统
    3. 创建并启动 Agent
    4. 注册生命周期钩子

    Args:
        config_path: 配置文件路径（可选，优先使用环境变量）
        **kwargs: 覆盖配置的键值对

    Returns:
        bool: 启动成功返回 True，失败返回 False

    Example:
        >>> import pylinkagent
        >>> pylinkagent.bootstrap()  # 使用默认配置
        True

        >>> pylinkagent.bootstrap(config_path="/etc/pylinkagent/config.yaml")
        True
    """
    global _initialized, _agent, _lifecycle_manager, _config, _logger

    # 防止重复初始化
    if _initialized:
        return True

    # 检查是否启用
    if not _should_enable():
        return False

    try:
        # 1. 加载配置
        _config = _load_config(config_path, **kwargs)
        if _config is None:
            return False

        # 2. 初始化日志系统
        _logger = setup_logger(_config.log_level)
        _logger.info(f"PyLinkAgent v{__version__} 正在启动...")

        # 3. 创建 Agent 实例
        _agent = Agent(_config)

        # 4. 创建生命周期管理器
        _lifecycle_manager = LifecycleManager(_agent, _config)

        # 5. 启动 Agent
        if not _agent.start():
            _logger.error("Agent 启动失败")
            return False

        # 6. 注册关闭钩子
        _register_shutdown_hooks()

        _initialized = True
        _logger.info("PyLinkAgent 启动成功")
        return True

    except Exception as e:
        # 启动失败时记录错误，但不影响主应用运行
        if _logger:
            _logger.exception(f"PyLinkAgent 启动异常：{e}")
        else:
            print(f"[PyLinkAgent] 启动异常：{e}", file=sys.stderr)
        return False


def shutdown() -> bool:
    """
    优雅关闭 PyLinkAgent

    负责：
    1. 停止数据采集
    2. 卸载所有插桩模块
    3. 上报最终状态
    4. 清理资源

    Returns:
        bool: 关闭成功返回 True
    """
    global _initialized, _agent, _lifecycle_manager

    if not _initialized:
        return True

    try:
        if _logger:
            _logger.info("PyLinkAgent 正在关闭...")

        # 1. 停止生命周期管理器
        if _lifecycle_manager:
            _lifecycle_manager.stop()

        # 2. 停止 Agent
        if _agent:
            _agent.stop()

        _initialized = False

        if _logger:
            _logger.info("PyLinkAgent 已关闭")

        return True

    except Exception as e:
        if _logger:
            _logger.exception(f"PyLinkAgent 关闭异常：{e}")
        return False


def get_agent() -> Optional[Agent]:
    """获取当前 Agent 实例"""
    return _agent


def get_config() -> Optional[Config]:
    """获取当前配置"""
    return _config


def is_initialized() -> bool:
    """检查探针是否已初始化"""
    return _initialized


def _should_enable() -> bool:
    """
    判断是否应该启用探针

    检查顺序：
    1. 环境变量 PYLINKAGENT_ENABLED
    2. 配置文件中的 enabled 字段
    3. 默认为 False（安全默认值）

    Returns:
        bool: 是否启用
    """
    env_val = os.getenv(ENV_ENABLED, "").lower()
    if env_val in ("true", "1", "yes", "on"):
        return True
    if env_val in ("false", "0", "no", "off"):
        return False
    # 未设置时默认不启用
    return False


def _load_config(config_path: Optional[str] = None, **kwargs: Any) -> Optional[Config]:
    """
    加载配置

    优先级：
    1. kwargs 传入的参数（最高优先级）
    2. 环境变量
    3. 配置文件
    4. 默认值

    Args:
        config_path: 配置文件路径
        **kwargs: 覆盖配置

    Returns:
        Config: 配置对象，加载失败返回 None
    """
    # 从环境变量获取配置路径
    if config_path is None:
        config_path = os.getenv(ENV_CONFIG_PATH)

    # 加载配置文件
    config = load_config(config_path)

    # 从环境变量覆盖配置
    if os.getenv(ENV_AGENT_ID):
        config.agent_id = os.getenv(ENV_AGENT_ID)
    if os.getenv(ENV_PLATFORM_URL):
        config.platform_url = os.getenv(ENV_PLATFORM_URL)
    if os.getenv(ENV_LOG_LEVEL):
        config.log_level = os.getenv(ENV_LOG_LEVEL)

    # kwargs 覆盖（最高优先级）
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)

    return config


def _register_shutdown_hooks() -> None:
    """
    注册关闭钩子

    确保在进程退出时优雅关闭探针
    """
    import atexit

    # 注册 atexit 钩子
    atexit.register(shutdown)

    # 注册信号处理（Unix only）
    try:
        import signal

        def signal_handler(signum, frame):
            shutdown()

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
    except (ImportError, AttributeError):
        # Windows 下某些信号不存在
        pass


# 自动引导：当通过环境变量启用时自动调用 bootstrap()
def _auto_bootstrap() -> None:
    """
    自动引导函数

    当模块被导入时，如果环境变量 PYLINKAGENT_ENABLED=true，
    自动调用 bootstrap()
    """
    if _should_enable():
        bootstrap()


# 模块导入时自动执行
_auto_bootstrap()


__all__ = [
    "__version__",
    "bootstrap",
    "shutdown",
    "get_agent",
    "get_config",
    "is_initialized",
    "Agent",
    "Config",
]
