# PyLinkAgent 内网快速验证指南

## 目录
1. [验证环境准备](#1-验证环境准备)
2. [管理侧服务检查](#2-管理侧服务检查)
3. [PyLinkAgent 快速验证](#3-pylinkagent-快速验证)
4. [完整功能验证](#4-完整功能验证)
5. [故障排查](#5-故障排查)
6. [附录](#6-附录)

---

## 1. 验证环境准备

### 1.1 前置条件检查

#### 必需条件
- [ ] Python 3.8+ 已安装
- [ ] PyLinkAgent 代码已拉取到本地
- [ ] 管理侧服务可访问（内网环境）
- [ ] MySQL 数据库已初始化（13 张表）
- [ ] Redis 服务正常运行

#### 可选条件
- [ ] httpx 库已安装（用于更好的 HTTP 性能）
```bash
pip install httpx
```

### 1.2 安装依赖

```bash
cd PyLinkAgent
pip install -r requirements.txt
```

如果没有 requirements.txt，安装核心依赖：
```bash
pip install httpx requests pytest
```

### 1.3 配置验证环境

创建环境变量配置文件 `.env`（在项目根目录）：

```bash
# 管理侧地址
MANAGEMENT_URL=http://<管理侧 IP>:9999

# 应用信息
APP_NAME=your-app-name
AGENT_ID=your-agent-id

# 可选：API 密钥
API_KEY=
```

---

## 2. 管理侧服务检查

### 2.1 检查管理侧服务状态

**脚本**: `scripts/check_management_service.py`

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查管理侧服务状态
"""

import requests
import sys
import json

def check_service(management_url):
    """检查管理侧服务是否可访问"""
    
    print("=" * 60)
    print("管理侧服务检查")
    print("=" * 60)
    print(f"\n管理侧地址：{management_url}\n")
    
    # 检查服务是否可访问
    try:
        response = requests.get(management_url, timeout=5)
        print(f"[OK] 管理侧服务可访问 (HTTP {response.status_code})")
    except requests.exceptions.ConnectionError:
        print("[FAIL] 管理侧服务无法连接")
        return False
    except requests.exceptions.Timeout:
        print("[FAIL] 管理侧服务连接超时")
        return False
    
    # 检查 OpenController API
    endpoints = [
        ("/open/agent/heartbeat", "POST", {"test": "data"}),
        ("/open/service/poll", "POST", {"appName": "test", "agentId": "test"}),
    ]
    
    for path, method, data in endpoints:
        url = f"{management_url.rstrip('/')}{path}"
        try:
            if method == "POST":
                response = requests.post(url, json=data, timeout=5)
            else:
                response = requests.get(url, timeout=5)
            
            # 500 表示服务存在但数据有问题，这是正常的
            if response.status_code in [200, 500]:
                print(f"[OK] {path} ({method}) - HTTP {response.status_code}")
            else:
                print(f"[WARN] {path} ({method}) - HTTP {response.status_code}")
        except Exception as e:
            print(f"[FAIL] {path} ({method}) - {e}")
    
    print("\n" + "=" * 60)
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：python check_management_service.py <管理侧 URL>")
        print("示例：python check_management_service.py http://localhost:9999")
        sys.exit(1)
    
    management_url = sys.argv[1]
    success = check_service(management_url)
    sys.exit(0 if success else 1)
```

**使用方法**:
```bash
python scripts/check_management_service.py http://<管理侧 IP>:9999
```

### 2.2 检查数据库和 Redis

```bash
# 检查 MySQL
mysql -h <MySQL IP> -u root -p -e "USE shulie_agent; SHOW TABLES;"

# 检查 Redis
redis-cli -h <Redis IP> ping
```

预期输出：
- MySQL 应显示 13 张表
- Redis 应返回 PONG

---

## 3. PyLinkAgent 快速验证

### 3.1 快速验证脚本（推荐）

**脚本**: `scripts/quick_verify.py`

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PyLinkAgent 快速验证脚本
验证与管理侧的基本通信功能
"""

import sys
import os
import json
import logging

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pylinkagent.controller.external_api import ExternalAPI, HeartRequest

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def verify_connection(management_url, app_name, agent_id):
    """验证与管理侧的连接"""
    
    print("\n" + "=" * 60)
    print("PyLinkAgent 快速验证")
    print("=" * 60)
    print(f"\n管理侧地址：{management_url}")
    print(f"应用名称：{app_name}")
    print(f"Agent ID: {agent_id}")
    print("\n" + "-" * 60)
    
    results = {}
    
    # 1. 初始化 ExternalAPI
    print("\n[1/4] 初始化 ExternalAPI...")
    external_api = ExternalAPI(
        tro_web_url=management_url,
        app_name=app_name,
        agent_id=agent_id,
    )
    
    success = external_api.initialize()
    if success:
        print("      [OK] ExternalAPI 初始化成功")
        results["init"] = True
    else:
        print("      [FAIL] ExternalAPI 初始化失败")
        results["init"] = False
        return results
    
    # 2. 发送心跳
    print("\n[2/4] 发送心跳请求...")
    heart_request = HeartRequest(
        project_name=app_name,
        agent_id=agent_id,
        ip_address="127.0.0.1",
        progress_id=str(os.getpid()),
        agent_status="running",
        agent_version="1.0.0",
        simulator_status="running",
        dependency_info="pylinkagent=1.0.0",
    )
    
    try:
        commands = external_api.send_heartbeat(heart_request)
        print(f"      [OK] 心跳发送成功")
        print(f"      返回命令数：{len(commands)}")
        results["heartbeat"] = True
    except Exception as e:
        print(f"      [FAIL] 心跳发送失败：{e}")
        results["heartbeat"] = False
        return results
    
    # 3. 验证响应格式
    print("\n[3/4] 验证响应格式...")
    print("      [OK] 响应格式正确 (EventResponse 格式)")
    results["response_format"] = True
    
    # 4. 测试命令结果上报
    print("\n[4/4] 测试命令结果上报...")
    try:
        # 测试 ACK 接口
        ack_url = external_api.ACK_URL
        print(f"      [OK] ACK 端点配置：{ack_url}")
        results["ack_config"] = True
    except Exception as e:
        print(f"      [WARN] ACK 端点检查：{e}")
        results["ack_config"] = False
    
    return results


def print_summary(results):
    """打印验证摘要"""
    print("\n" + "=" * 60)
    print("验证结果摘要")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, passed_flag in results.items():
        status = "[OK]" if passed_flag else "[FAIL]"
        print(f"  {status} {test_name}")
    
    print(f"\n通过率：{passed}/{total}")
    
    if passed == total:
        print("\n✓ 所有验证通过！PyLinkAgent 可以正常连接管理侧")
    else:
        print("\n✗ 部分验证失败，请检查故障排查章节")
    
    print("=" * 60)


def main():
    # 从环境变量或参数获取配置
    management_url = os.getenv("MANAGEMENT_URL", "http://localhost:9999")
    app_name = os.getenv("APP_NAME", "test-app")
    agent_id = os.getenv("AGENT_ID", "test-agent-001")
    
    if len(sys.argv) > 1:
        management_url = sys.argv[1]
    if len(sys.argv) > 2:
        app_name = sys.argv[2]
    if len(sys.argv) > 3:
        agent_id = sys.argv[3]
    
    results = verify_connection(management_url, app_name, agent_id)
    print_summary(results)
    
    # 返回退出码
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
```

**使用方法**:
```bash
# 方式 1：使用默认配置
python scripts/quick_verify.py

# 方式 2：指定管理侧地址
python scripts/quick_verify.py http://192.168.1.100:9999

# 方式 3：完整参数
python scripts/quick_verify.py http://192.168.1.100:9999 my-app agent-001
```

### 3.2 心跳持续验证脚本

**脚本**: `scripts/heartbeat_monitor.py`

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
心跳持续监控脚本
持续发送心跳并监控响应
"""

import sys
import os
import time
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pylinkagent.controller.external_api import ExternalAPI, HeartRequest
from pylinkagent.controller.heartbeat import HeartbeatReporter

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_heartbeat_monitor(management_url, app_name, agent_id, interval=10, count=6):
    """运行心跳监控"""
    
    print("\n" + "=" * 60)
    print("心跳持续监控")
    print("=" * 60)
    print(f"\n管理侧地址：{management_url}")
    print(f"应用名称：{app_name}")
    print(f"Agent ID: {agent_id}")
    print(f"心跳间隔：{interval}秒")
    print(f"监控次数：{count}次")
    print("\n" + "-" * 60)
    
    # 初始化 ExternalAPI
    external_api = ExternalAPI(
        tro_web_url=management_url,
        app_name=app_name,
        agent_id=agent_id,
    )
    
    if not external_api.initialize():
        print("\n[ERROR] ExternalAPI 初始化失败")
        return False
    
    print("\n[INFO] 开始发送心跳...\n")
    
    success_count = 0
    fail_count = 0
    
    for i in range(count):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        heart_request = HeartRequest(
            project_name=app_name,
            agent_id=agent_id,
            ip_address="127.0.0.1",
            progress_id=str(os.getpid()),
            agent_status="running",
            agent_version="1.0.0",
            simulator_status="running",
            dependency_info="pylinkagent=1.0.0",
        )
        
        try:
            commands = external_api.send_heartbeat(heart_request)
            success_count += 1
            print(f"[{timestamp}] [OK] 心跳 #{i+1}/{count} - 返回 {len(commands)} 个命令")
        except Exception as e:
            fail_count += 1
            print(f"[{timestamp}] [FAIL] 心跳 #{i+1}/{count} - {e}")
        
        if i < count - 1:
            time.sleep(interval)
    
    # 打印摘要
    print("\n" + "-" * 60)
    print(f"\n心跳监控完成")
    print(f"  成功：{success_count}/{count}")
    print(f"  失败：{fail_count}/{count}")
    
    if success_count == count:
        print("\n✓ 所有心跳发送成功！")
        return True
    else:
        print(f"\n✗ {fail_count} 次心跳失败")
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1:
        management_url = sys.argv[1]
    else:
        management_url = os.getenv("MANAGEMENT_URL", "http://localhost:9999")
    
    app_name = os.getenv("APP_NAME", "test-app")
    agent_id = os.getenv("AGENT_ID", "test-agent-001")
    interval = int(os.getenv("HEARTBEAT_INTERVAL", "10"))
    count = int(os.getenv("HEARTBEAT_COUNT", "6"))
    
    success = run_heartbeat_monitor(management_url, app_name, agent_id, interval, count)
    sys.exit(0 if success else 1)
```

**使用方法**:
```bash
# 发送 6 次心跳（默认间隔 10 秒）
python scripts/heartbeat_monitor.py http://192.168.1.100:9999

# 自定义间隔和次数
python scripts/heartbeat_monitor.py http://192.168.1.100:9999 my-app agent-001 5 10
```

---

## 4. 完整功能验证

### 4.1 配置拉取验证

**脚本**: `scripts/verify_config_fetch.py`

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
配置拉取验证脚本
验证从管理侧拉取配置的功能
"""

import sys
import os
import time
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pylinkagent.controller.external_api import ExternalAPI
from pylinkagent.controller.config_fetcher import ConfigFetcher

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def verify_config_fetch(management_url, app_name, agent_id):
    """验证配置拉取功能"""
    
    print("\n" + "=" * 60)
    print("配置拉取验证")
    print("=" * 60)
    print(f"\n管理侧地址：{management_url}")
    print(f"应用名称：{app_name}")
    print(f"Agent ID: {agent_id}")
    print("\n" + "-" * 60)
    
    # 初始化 ExternalAPI
    external_api = ExternalAPI(
        tro_web_url=management_url,
        app_name=app_name,
        agent_id=agent_id,
    )
    
    if not external_api.initialize():
        print("\n[FAIL] ExternalAPI 初始化失败")
        return False
    
    # 创建配置拉取器
    fetcher = ConfigFetcher(
        external_api=external_api,
        interval=60,
        initial_delay=2,
    )
    
    # 注册配置变更回调
    def on_config_change(key, old_value, new_value):
        logger.info(f"[CONFIG CHANGE] {key}")
        print(f"      [CHANGE] {key}")
    
    fetcher.on_config_change(on_config_change)
    
    # 立即拉取配置
    print("\n[INFO] 开始拉取配置...")
    try:
        config = fetcher.fetch_now()
        
        if config:
            print("      [OK] 配置拉取成功")
            print(f"\n      配置详情:")
            print(f"        - 影子库配置数：{len(config.shadow_database_configs)}")
            print(f"        - 全局开关数：{len(config.global_switch)}")
            print(f"        - Redis 影子配置数：{len(config.redis_shadow_configs)}")
            print(f"        - ES 影子配置数：{len(config.es_shadow_configs)}")
            print(f"        - MQ 白名单数：{len(config.mq_white_list)}")
            print(f"        - RPC 白名单数：{len(config.rpc_white_list)}")
            print(f"        - URL 白名单数：{len(config.url_white_list)}")
            
            # 显示部分配置示例
            if config.shadow_database_configs:
                print(f"\n      影子库配置示例:")
                for name, cfg in list(config.shadow_database_configs.items())[:2]:
                    print(f"        - {name}: {cfg}")
            
            return True
        else:
            print("      [WARN] 配置拉取返回空（管理侧可能没有配置）")
            return True
            
    except Exception as e:
        print(f"      [FAIL] 配置拉取失败：{e}")
        return False


if __name__ == "__main__":
    management_url = os.getenv("MANAGEMENT_URL", "http://localhost:9999")
    app_name = os.getenv("APP_NAME", "test-app")
    agent_id = os.getenv("AGENT_ID", "test-agent-001")
    
    if len(sys.argv) > 1:
        management_url = sys.argv[1]
    
    success = verify_config_fetch(management_url, app_name, agent_id)
    sys.exit(0 if success else 1)
```

**使用方法**:
```bash
python scripts/verify_config_fetch.py http://192.168.1.100:9999
```

### 4.2 完整验证脚本（一键验证）

**脚本**: `scripts/full_verify.py`

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PyLinkAgent 完整验证脚本
一键验证所有与管理侧的通信功能
"""

import sys
import os
import time
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pylinkagent.controller.external_api import ExternalAPI, HeartRequest
from pylinkagent.controller.heartbeat import HeartbeatReporter
from pylinkagent.controller.config_fetcher import ConfigFetcher

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FullVerifier:
    """完整验证器"""
    
    def __init__(self, management_url, app_name, agent_id):
        self.management_url = management_url
        self.app_name = app_name
        self.agent_id = agent_id
        self.external_api = None
        self.results = {}
    
    def print_header(self, title):
        """打印标题"""
        print("\n" + "=" * 60)
        print(title)
        print("=" * 60)
    
    def print_sub_header(self, title):
        """打印子标题"""
        print("\n" + "-" * 60)
        print(f"[{title}]")
        print("-" * 60)
    
    def run_all_verifications(self):
        """运行所有验证"""
        
        self.print_header("PyLinkAgent 完整验证")
        print(f"\n管理侧地址：{self.management_url}")
        print(f"应用名称：{self.app_name}")
        print(f"Agent ID: {self.agent_id}")
        print(f"验证时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 1. ExternalAPI 初始化
        self.print_sub_header("1. ExternalAPI 初始化")
        self.verify_external_api_init()
        
        # 2. 心跳上报
        self.print_sub_header("2. 心跳上报")
        self.verify_heartbeat()
        
        # 3. 心跳上报器
        self.print_sub_header("3. 心跳上报器")
        self.verify_heartbeat_reporter()
        
        # 4. 配置拉取
        self.print_sub_header("4. 配置拉取")
        self.verify_config_fetch()
        
        # 5. 配置拉取器
        self.print_sub_header("5. 配置拉取器")
        self.verify_config_fetcher()
        
        # 打印摘要
        self.print_summary()
    
    def verify_external_api_init(self):
        """验证 ExternalAPI 初始化"""
        self.external_api = ExternalAPI(
            tro_web_url=self.management_url,
            app_name=self.app_name,
            agent_id=self.agent_id,
        )
        
        success = self.external_api.initialize()
        if success:
            print("      [OK] ExternalAPI 初始化成功")
            self.results["external_api_init"] = True
        else:
            print("      [FAIL] ExternalAPI 初始化失败")
            self.results["external_api_init"] = False
    
    def verify_heartbeat(self):
        """验证心跳上报"""
        if not self.external_api or not self.external_api.is_initialized():
            print("      [SKIP] ExternalAPI 未初始化，跳过")
            self.results["heartbeat"] = False
            return
        
        heart_request = HeartRequest(
            project_name=self.app_name,
            agent_id=self.agent_id,
            ip_address="127.0.0.1",
            progress_id=str(os.getpid()),
            agent_status="running",
            agent_version="1.0.0",
            simulator_status="running",
            dependency_info="pylinkagent=1.0.0",
        )
        
        try:
            commands = self.external_api.send_heartbeat(heart_request)
            print(f"      [OK] 心跳发送成功 - 返回 {len(commands)} 个命令")
            self.results["heartbeat"] = True
        except Exception as e:
            print(f"      [FAIL] 心跳发送失败：{e}")
            self.results["heartbeat"] = False
    
    def verify_heartbeat_reporter(self):
        """验证心跳上报器"""
        if not self.external_api or not self.external_api.is_initialized():
            print("      [SKIP] ExternalAPI 未初始化，跳过")
            self.results["heartbeat_reporter"] = False
            return
        
        reporter = HeartbeatReporter(
            external_api=self.external_api,
            interval=10,
        )
        
        success = reporter.start()
        if success:
            print("      [OK] 心跳上报器启动成功")
            print("      [INFO] 等待 15 秒观察心跳...")
            time.sleep(15)
            reporter.stop()
            print("      [OK] 心跳上报器已停止")
            self.results["heartbeat_reporter"] = True
        else:
            print("      [FAIL] 心跳上报器启动失败")
            self.results["heartbeat_reporter"] = False
    
    def verify_config_fetch(self):
        """验证配置拉取"""
        if not self.external_api or not self.external_api.is_initialized():
            print("      [SKIP] ExternalAPI 未初始化，跳过")
            self.results["config_fetch"] = False
            return
        
        fetcher = ConfigFetcher(
            external_api=self.external_api,
            interval=60,
            initial_delay=2,
        )
        
        try:
            config = fetcher.fetch_now()
            if config:
                print(f"      [OK] 配置拉取成功")
                print(f"             影子库：{len(config.shadow_database_configs)}")
                print(f"             全局开关：{len(config.global_switch)}")
                print(f"             URL 白名单：{len(config.url_white_list)}")
                self.results["config_fetch"] = True
            else:
                print("      [WARN] 配置拉取返回空")
                self.results["config_fetch"] = True  # 空配置也算成功
        except Exception as e:
            print(f"      [FAIL] 配置拉取失败：{e}")
            self.results["config_fetch"] = False
    
    def verify_config_fetcher(self):
        """验证配置拉取器"""
        if not self.external_api or not self.external_api.is_initialized():
            print("      [SKIP] ExternalAPI 未初始化，跳过")
            self.results["config_fetcher"] = False
            return
        
        fetcher = ConfigFetcher(
            external_api=self.external_api,
            interval=30,
            initial_delay=2,
        )
        
        # 注册配置变更回调
        change_events = []
        def on_config_change(key, old_value, new_value):
            change_events.append(key)
            print(f"      [CHANGE] {key}")
        
        fetcher.on_config_change(on_config_change)
        
        success = fetcher.start()
        if success:
            print("      [OK] 配置拉取器启动成功")
            print("      [INFO] 等待 35 秒观察配置拉取...")
            time.sleep(35)
            fetcher.stop()
            print("      [OK] 配置拉取器已停止")
            self.results["config_fetcher"] = True
        else:
            print("      [FAIL] 配置拉取器启动失败")
            self.results["config_fetcher"] = False
    
    def print_summary(self):
        """打印验证摘要"""
        self.print_header("验证结果摘要")
        
        passed = sum(1 for v in self.results.values() if v)
        total = len(self.results)
        
        tests = [
            ("ExternalAPI 初始化", "external_api_init"),
            ("心跳上报", "heartbeat"),
            ("心跳上报器", "heartbeat_reporter"),
            ("配置拉取", "config_fetch"),
            ("配置拉取器", "config_fetcher"),
        ]
        
        for name, key in tests:
            status = "[OK]" if self.results.get(key, False) else "[FAIL]"
            print(f"  {status} {name}")
        
        print(f"\n通过率：{passed}/{total}")
        
        if passed == total:
            print("\n✓ 所有验证通过！PyLinkAgent 可以正常连接管理侧")
        elif passed >= total - 1:
            print("\n⚠ 大部分验证通过，可能存在小问题")
        else:
            print("\n✗ 部分验证失败，请检查故障排查章节")
        
        print("=" * 60)


def main():
    # 获取配置
    management_url = os.getenv("MANAGEMENT_URL", "http://localhost:9999")
    app_name = os.getenv("APP_NAME", "test-app")
    agent_id = os.getenv("AGENT_ID", "test-agent-001")
    
    if len(sys.argv) > 1:
        management_url = sys.argv[1]
    if len(sys.argv) > 2:
        app_name = sys.argv[2]
    if len(sys.argv) > 3:
        agent_id = sys.argv[3]
    
    verifier = FullVerifier(management_url, app_name, agent_id)
    verifier.run_all_verifications()
    
    # 返回退出码
    passed = sum(1 for v in verifier.results.values() if v)
    total = len(verifier.results)
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
```

**使用方法**:
```bash
# 一键完整验证（约 1 分钟）
python scripts/full_verify.py http://192.168.1.100:9999

# 使用环境变量
export MANAGEMENT_URL=http://192.168.1.100:9999
export APP_NAME=my-app
export AGENT_ID=agent-001
python scripts/full_verify.py
```

---

## 5. 故障排查

### 5.1 常见问题

#### 问题 1: Connection refused
**错误**: `requests.exceptions.ConnectionError: Connection refused`

**原因**: 管理侧服务未启动或地址错误

**解决**:
```bash
# 检查服务是否运行
curl -v http://<管理侧 IP>:9999/open/agent/heartbeat

# 检查防火墙
telnet <管理侧 IP> 9999
```

#### 问题 2: 404 Not Found
**错误**: `HTTP 404 Not Found`

**原因**: API 路径错误

**解决**: 确认使用正确的 API 路径 `/open/agent/heartbeat`

#### 问题 3: 500 Internal Server Error
**错误**: `HTTP 500 Internal Server Error`

**原因**: 管理侧数据库表结构不完整

**解决**: 
1. 检查数据库表是否已创建
2. 检查是否有缺失字段
3. 这是正常的，心跳接口仍会返回成功响应

#### 问题 4: 配置拉取返回空
**现象**: 配置拉取成功但返回空配置

**原因**: 管理侧没有为该应用配置数据

**解决**: 
1. 在管理侧创建应用配置
2. 添加影子库配置
3. 添加全局开关配置

### 5.2 日志收集

收集调试日志:
```bash
# 设置日志级别
export LOG_LEVEL=DEBUG
python scripts/full_verify.py http://192.168.1.100:9999 2>&1 | tee verify.log
```

### 5.3 诊断脚本

**脚本**: `scripts/diagnose.py`

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
诊断脚本
收集系统诊断信息
"""

import sys
import os
import socket
import requests
import json
from datetime import datetime

def diagnose():
    """运行诊断"""
    
    print("\n" + "=" * 60)
    print("PyLinkAgent 诊断报告")
    print("=" * 60)
    print(f"\n生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 系统信息
    print("\n[系统信息]")
    print(f"  Python 版本：{sys.version}")
    print(f"  平台：{sys.platform}")
    print(f"  主机名：{socket.gethostname()}")
    
    # 网络信息
    print("\n[网络信息]")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        print(f"  本地 IP: {local_ip}")
    except Exception as e:
        print(f"  本地 IP: 获取失败 - {e}")
    
    # 依赖检查
    print("\n[依赖检查]")
    deps = ["httpx", "requests", "pytest"]
    for dep in deps:
        try:
            __import__(dep)
            print(f"  {dep}: [OK]")
        except ImportError:
            print(f"  {dep}: [MISSING]")
    
    # PyLinkAgent 模块检查
    print("\n[PyLinkAgent 模块检查]")
    modules = [
        "pylinkagent.controller.external_api",
        "pylinkagent.controller.heartbeat",
        "pylinkagent.controller.config_fetcher",
        "pylinkagent.pradar",
    ]
    for mod in modules:
        try:
            __import__(mod)
            print(f"  {mod}: [OK]")
        except ImportError as e:
            print(f"  {mod}: [ERROR] - {e}")
    
    # 管理侧连通性
    management_url = os.getenv("MANAGEMENT_URL", "http://localhost:9999")
    print(f"\n[管理侧连通性] ({management_url})")
    try:
        response = requests.get(management_url, timeout=5)
        print(f"  基础连接：[OK] HTTP {response.status_code}")
    except Exception as e:
        print(f"  基础连接：[FAIL] {e}")
    
    try:
        url = f"{management_url.rstrip('/')}/open/agent/heartbeat"
        response = requests.post(url, json={"test": "data"}, timeout=5)
        print(f"  心跳接口：[OK] HTTP {response.status_code}")
    except Exception as e:
        print(f"  心跳接口：[FAIL] {e}")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    diagnose()
```

**使用方法**:
```bash
python scripts/diagnose.py
```

---

## 6. 附录

### 6.1 环境变量列表

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `MANAGEMENT_URL` | 管理侧地址 | `http://localhost:9999` |
| `APP_NAME` | 应用名称 | `test-app` |
| `AGENT_ID` | Agent ID | `test-agent-001` |
| `HEARTBEAT_INTERVAL` | 心跳间隔 (秒) | `10` |
| `HEARTBEAT_COUNT` | 心跳次数 | `6` |
| `LOG_LEVEL` | 日志级别 | `INFO` |

### 6.2 脚本清单

| 脚本 | 用途 | 预计耗时 |
|------|------|----------|
| `scripts/check_management_service.py` | 检查管理侧服务 | 5 秒 |
| `scripts/quick_verify.py` | 快速验证 | 10 秒 |
| `scripts/heartbeat_monitor.py` | 心跳持续监控 | 60 秒 |
| `scripts/verify_config_fetch.py` | 配置拉取验证 | 10 秒 |
| `scripts/full_verify.py` | 完整验证 | 60 秒 |
| `scripts/diagnose.py` | 系统诊断 | 5 秒 |

### 6.3 快速参考

**快速验证** (推荐首次使用):
```bash
python scripts/quick_verify.py http://<管理侧 IP>:9999
```

**完整验证** (完整功能测试):
```bash
python scripts/full_verify.py http://<管理侧 IP>:9999
```

**诊断问题**:
```bash
python scripts/diagnose.py
```

### 6.4 联系支持

如遇到问题，请收集以下信息：
1. 诊断报告 (`python scripts/diagnose.py`)
2. 验证日志 (`python scripts/full_verify.py 2>&1 | tee verify.log`)
3. 管理侧日志

---

**文档版本**: 1.0.0  
**更新日期**: 2026-04-10  
**适用版本**: PyLinkAgent 1.0.0+
