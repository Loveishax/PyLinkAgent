"""
影子数据库配置类

参考 Java ShadowDatabaseConfig 实现，支持:
- 影子库/影子表配置
- 表名映射
- 账号前缀/后缀转换
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Any, List
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class ShadowDatabaseConfig:
    """
    影子数据库配置

    Attributes:
        ds_type: 数据源类型 0=影子库，1=影子表，2=影子库 + 影子表
        url: 业务库 URL
        username: 业务库用户名
        schema: 业务库 schema
        shadow_url: 影子库 URL
        shadow_driver_class: 影子库驱动类名
        shadow_username: 影子库用户名 (可选，优先级高于前缀/后缀)
        shadow_password: 影子库密码 (可选，优先级高于前缀/后缀)
        shadow_schema: 影子库 schema
        shadow_account_prefix: 影子库账号前缀 (如 "PT_")
        shadow_account_suffix: 影子库账号后缀 (如 "_PRESSURE")
        business_shadow_tables: 业务表→影子表映射 {"users": "shadow_users"}
        properties: 其他配置属性
    """
    # 数据源类型
    ds_type: int = 0  # 0=影子库，1=影子表，2=库 + 表

    # 业务库配置
    url: str = ""
    username: str = ""
    password: str = ""
    schema: Optional[str] = None

    # 影子库配置
    shadow_url: str = ""
    shadow_driver_class: Optional[str] = None
    shadow_username: Optional[str] = None
    shadow_password: Optional[str] = None
    shadow_schema: Optional[str] = None

    # 账号转换配置
    shadow_account_prefix: str = "PT_"
    shadow_account_suffix: str = ""

    # 表映射配置
    business_shadow_tables: Dict[str, str] = field(default_factory=dict)

    # 其他配置
    properties: Dict[str, Any] = field(default_factory=dict)

    # 连接池配置 (可选)
    min_idle: Optional[int] = None
    max_active: Optional[int] = None
    max_wait: Optional[int] = None
    validation_query: Optional[str] = None
    test_while_idle: Optional[bool] = None
    test_on_borrow: Optional[bool] = None
    test_on_return: Optional[bool] = None

    def is_shadow_database(self) -> bool:
        """是否是影子库模式"""
        return self.ds_type in (0, 2)

    def is_shadow_table(self) -> bool:
        """是否是影子表模式"""
        return self.ds_type == 1

    def is_shadow_database_with_table(self) -> bool:
        """是否是影子库 + 影子表模式"""
        return self.ds_type == 2

    def get_shadow_username(self, biz_username: Optional[str] = None) -> str:
        """
        获取影子库用户名

        支持在业务用户名上添加前缀/后缀
        Oracle 用户名特殊处理 (必须以 C## 开头)
        """
        if self.shadow_username:
            return self.shadow_username

        if not biz_username:
            return self.username

        # Oracle 特殊处理
        if self._is_oracle() and biz_username.upper().startswith("C##"):
            return f"C##{self.shadow_account_prefix}{biz_username[3:]}{self.shadow_account_suffix}"

        return f"{self.shadow_account_prefix}{biz_username}{self.shadow_account_suffix}"

    def get_shadow_password(self, biz_password: Optional[str] = None) -> str:
        """获取影子库密码"""
        if self.shadow_password:
            return self.shadow_password

        if not biz_password:
            return self.password or ""

        return f"{self.shadow_account_prefix}{biz_password}{self.shadow_account_suffix}"

    def get_shadow_table(self, table_name: str) -> str:
        """获取影子表名"""
        return self.business_shadow_tables.get(table_name, f"{self.shadow_account_prefix}{table_name}")

    def rewrite_table_name(self, sql: str) -> str:
        """
        重写 SQL 中的表名

        支持简单的表名替换，复杂 SQL 需要更高级的解析
        """
        result = sql
        for biz_table, shadow_table in self.business_shadow_tables.items():
            # 简单的表名替换，考虑大小写
            patterns = [
                rf'\b{re.escape(biz_table)}\b',
                rf'"{re.escape(biz_table)}"',
                rf'`{re.escape(biz_table)}`',
            ]
            for pattern in patterns:
                result = re.sub(pattern, shadow_table, result, flags=re.IGNORECASE)
        return result

    def _is_oracle(self) -> bool:
        """是否是 Oracle 数据库"""
        return self.url.startswith("jdbc:oracle:") if self.url else False

    def match(self, url: str, username: Optional[str] = None) -> bool:
        """
        判断当前配置是否匹配给定的数据库连接

        支持按 URL+ 用户名或仅 URL 匹配
        """
        if self.url != url:
            return False

        if username and self.username:
            return self.username == username

        return True

    def __repr__(self) -> str:
        return (
            f"ShadowDatabaseConfig(ds_type={self.ds_type}, "
            f"url='{self.url}', shadow_url='{self.shadow_url}', "
            f"tables={list(self.business_shadow_tables.keys())})"
        )


class ShadowConfigManager:
    """
    影子配置管理器

    管理多个影子数据库配置，支持动态添加/删除配置
    """

    def __init__(self):
        # 使用 URL+Username 作为 key
        self._configs: Dict[str, ShadowDatabaseConfig] = {}
        self._lock = None  # 线程锁，可选

    def _make_key(self, url: str, username: Optional[str] = None) -> str:
        """生成配置 key"""
        if username:
            return f"{url}|{username}"
        return f"{url}|"

    def register_config(self, config: ShadowDatabaseConfig) -> bool:
        """
        注册影子库配置

        Args:
            config: 影子库配置对象

        Returns:
            是否注册成功
        """
        key = self._make_key(config.url, config.username)
        self._configs[key] = config
        logger.info(f"Registered shadow config: {config}")
        return True

    def unregister_config(self, url: str, username: Optional[str] = None) -> bool:
        """注销影子库配置"""
        key = self._make_key(url, username)
        if key in self._configs:
            del self._configs[key]
            logger.info(f"Unregistered shadow config: url={url}, username={username}")
            return True

        # 尝试只匹配 URL
        if username:
            key_no_user = self._make_key(url, None)
            if key_no_user in self._configs:
                del self._configs[key_no_user]
                logger.info(f"Unregistered shadow config (no username): url={url}")
                return True

        return False

    def get_shadow_config(self, url: str, username: Optional[str] = None) -> Optional[ShadowDatabaseConfig]:
        """
        获取影子库配置

        优先匹配 URL+Username，其次只匹配 URL
        """
        key = self._make_key(url, username)
        if key in self._configs:
            return self._configs[key]

        # 尝试只匹配 URL
        key_no_user = self._make_key(url, None)
        if key_no_user in self._configs:
            return self._configs[key_no_user]

        return None

    def contains_config(self, url: str, username: Optional[str] = None) -> bool:
        """是否包含某个配置"""
        return self.get_shadow_config(url, username) is not None

    def get_all_configs(self) -> List[ShadowDatabaseConfig]:
        """获取所有配置"""
        return list(self._configs.values())

    def clear_configs(self) -> None:
        """清空所有配置"""
        self._configs.clear()
        logger.info("Cleared all shadow configs")

    def load_from_dict(self, configs_data: List[Dict[str, Any]]) -> int:
        """
        从字典列表加载配置

        支持 camelCase 和 snake_case 两种命名风格:
        - camelCase: dsType, shadowUrl, shadowUsername, businessShadowTables
        - snake_case: ds_type, shadow_url, shadow_username, business_shadow_tables

        Args:
            configs_data: 配置数据列表

        Returns:
            成功加载的配置数量
        """
        count = 0
        for data in configs_data:
            try:
                # 支持 camelCase 和 snake_case 两种风格
                config = ShadowDatabaseConfig(
                    ds_type=data.get("ds_type") or data.get("dsType", 0),
                    url=data.get("url", ""),
                    username=data.get("username", ""),
                    password=data.get("password", ""),
                    shadow_url=data.get("shadow_url") or data.get("shadowUrl", ""),
                    shadow_username=data.get("shadow_username") or data.get("shadowUsername"),
                    shadow_password=data.get("shadow_password") or data.get("shadowPassword"),
                    shadow_account_prefix=data.get("shadow_account_prefix") or data.get("shadowAccountPrefix", "PT_"),
                    shadow_account_suffix=data.get("shadow_account_suffix") or data.get("shadowAccountSuffix", ""),
                    business_shadow_tables=data.get("business_shadow_tables") or data.get("businessShadowTables", {}),
                    properties=data.get("properties", {}),
                )
                self.register_config(config)
                count += 1
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
        return count

    def __len__(self) -> int:
        return len(self._configs)

    def __repr__(self) -> str:
        return f"ShadowConfigManager(configs={len(self._configs)})"
