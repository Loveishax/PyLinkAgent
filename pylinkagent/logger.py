"""
PyLinkAgent 日志系统

使用 structlog 进行结构化日志输出，支持：
- 多种输出格式（JSON、Console）
- 动态日志级别
- 日志采样（避免日志爆炸）
"""

import logging
import sys
from typing import Optional

try:
    import structlog
    STRUCTLOG_AVAILABLE = True
except ImportError:
    STRUCTLOG_AVAILABLE = False

# 默认日志格式
DEFAULT_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"


def setup_logger(log_level: str = "INFO") -> logging.Logger:
    """
    设置并返回日志对象

    Args:
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        logging.Logger: 配置好的 logger 实例
    """
    logger = logging.getLogger("pylinkagent")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # 创建控制台 handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)

    # 设置格式
    if STRUCTLOG_AVAILABLE:
        _setup_structlog(logger, handler, log_level)
    else:
        _setup_basic_logging(logger, handler, log_level)

    return logger


def _setup_structlog(logger: logging.Logger, handler: logging.Handler, log_level: str) -> None:
    """使用 structlog 进行结构化日志"""
    import structlog

    # 配置 structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # 绑定到标准 logging
    handler.setFormatter(logging.Formatter(DEFAULT_LOG_FORMAT))
    logger.addHandler(handler)


def _setup_basic_logging(logger: logging.Logger, handler: logging.Handler, log_level: str) -> None:
    """使用标准 logging（无 structlog 依赖时）"""
    formatter = logging.Formatter(DEFAULT_LOG_FORMAT)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
