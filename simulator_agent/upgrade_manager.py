"""
UpgradeManager - 模块升级管理

负责：
- 下载新版本模块
- 验证模块完整性
- 协调热更新流程
"""

from typing import Optional, Dict, Any
import os
import hashlib
import tempfile
import shutil
import logging
from pathlib import Path

from pylinkagent.config import Config


logger = logging.getLogger(__name__)


class UpgradeManager:
    """
    升级管理器

    处理模块下载、验证和升级流程
    """

    def __init__(self, config: Config):
        """
        初始化升级管理器

        Args:
            config: 配置对象
        """
        self.config = config
        self._download_dir = tempfile.mkdtemp(prefix="pylinkagent_upgrade_")
        logger.info(f"升级下载目录：{self._download_dir}")

    def upgrade_module(
        self,
        module_name: str,
        version: str,
        download_url: str,
        instrument_simulator: Any
    ) -> Dict[str, Any]:
        """
        升级模块

        Args:
            module_name: 模块名称
            version: 目标版本
            download_url: 下载地址
            instrument_simulator: instrument-simulator 实例

        Returns:
            升级结果
        """
        try:
            logger.info(f"开始升级模块 {module_name} 到版本 {version}")

            # 1. 下载模块
            local_path = self._download_module(module_name, download_url)
            if not local_path:
                return {"success": False, "error": "下载失败"}

            # 2. 验证模块
            if not self._verify_module(local_path):
                return {"success": False, "error": "模块验证失败"}

            # 3. 执行热更新
            if instrument_simulator:
                result = instrument_simulator.reload_module(module_name, local_path)
                if result.get("success"):
                    logger.info(f"模块 {module_name} 升级成功")
                return result

            return {"success": False, "error": "instrument_simulator 不可用"}

        except Exception as e:
            logger.exception(f"升级模块失败：{e}")
            return {"success": False, "error": str(e)}

    def _download_module(self, module_name: str, url: str) -> Optional[str]:
        """
        下载模块文件

        Args:
            module_name: 模块名称
            url: 下载地址

        Returns:
            本地文件路径，失败返回 None
        """
        try:
            import httpx

            local_path = os.path.join(self._download_dir, f"{module_name}.tar.gz")

            with httpx.stream("GET", url, follow_redirects=True) as response:
                response.raise_for_status()
                with open(local_path, "wb") as f:
                    for chunk in response.iter_bytes():
                        f.write(chunk)

            logger.info(f"模块下载到：{local_path}")
            return local_path

        except Exception as e:
            logger.error(f"下载失败：{e}")
            return None

    def _verify_module(self, local_path: str) -> bool:
        """
        验证模块文件

        Args:
            local_path: 模块文件路径

        Returns:
            验证是否通过
        """
        # 1. 检查文件是否存在
        if not os.path.exists(local_path):
            return False

        # 2. 检查文件大小
        if os.path.getsize(local_path) == 0:
            return False

        # 3. 验证哈希（可选，如果有提供哈希值）
        # 这里简化处理，实际应该对比平台下发的哈希值

        # 4. 验证文件格式（应该是 tar.gz 或 wheel）
        if not local_path.endswith((".tar.gz", ".whl")):
            return False

        return True

    def cleanup(self) -> None:
        """清理临时下载目录"""
        try:
            shutil.rmtree(self._download_dir)
            logger.info("清理临时下载目录完成")
        except Exception as e:
            logger.error(f"清理失败：{e}")
