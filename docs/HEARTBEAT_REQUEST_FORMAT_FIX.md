# PyLinkAgent 心跳请求格式修正说明

> **版本**: v2.0.0  
> **更新日期**: 2026-04-16  
> **主题**: 与控制台心跳上报格式对齐 Java Agent

---

## 一、问题背景

在对比 PyLinkAgent 与 Java Agent 的心跳上报请求时，发现存在以下格式差异，可能导致与控制台 (Takin-web) 的兼容性问题。

---

## 二、Java Agent 抓包数据

```
projectName=@String[default_demo-test-am_test]
agentId=@String[12.11.0.110-1]
ipAddress=@String[12.11.0.110]
progressId=@String[1]
curUpgradeBatch=@String[-1]
agentStatus=@String[INSTALLED]
agentErrorInfo=@String[]
simulatorStatus=@String[INSTALLED]
simulatorErrorInfo=null
uninstallStatus=@Integer[0]
dormantStatus=@Integer[0]
agentVersion=@String[1.0.0]
simulatorVersion=@String[1.0.0]
dependencyInfo=null
flag=@String[shulieEnterprise]
commandResult=@ArrayList[isEmpty=true;size=0]
```

---

## 三、发现的差异

| 字段 | Java Agent | PyLinkAgent (修正前) | 问题 |
|------|-----------|---------------------|------|
| `agentStatus` | `INSTALLED` | `running` | 状态值不匹配 |
| `simulatorStatus` | `INSTALLED` | `running` | 状态值不匹配 |
| `agentErrorInfo` | `@String[]` (数组) | `""` (字符串) | 类型不匹配 |
| `simulatorErrorInfo` | `null` | `""` (空字符串) | null vs 空字符串 |
| `dependencyInfo` | `null` | `""` (空字符串) | null vs 空字符串 |
| `commandResult` | `@ArrayList` | `[]` (列表) | 类型正确，但默认值应为空列表 |
| `curUpgradeBatch` | `-1` | 未设置 | 字段缺失 |
| `flag` | `shulieEnterprise` | 未设置 | 字段缺失 |

---

## 四、修正内容

### 4.1 external_api.py - HeartRequest 数据类

**文件**: `pylinkagent/controller/external_api.py`

```python
@dataclass
class HeartRequest:
    project_name: str = ""
    agent_id: str = ""
    ip_address: str = ""
    progress_id: str = ""
    cur_upgrade_batch: str = "-1"  # 修正：添加默认值
    agent_status: str = "INSTALLED"  # 修正：从 "running" 改为 "INSTALLED"
    agent_error_info: list = field(default_factory=list)  # 修正：从 str 改为 list
    simulator_status: str = "INSTALLED"  # 修正：从 "running" 改为 "INSTALLED"
    simulator_error_info: Optional[str] = None  # 修正：从 str 改为 Optional，默认 null
    uninstall_status: int = 0
    dormant_status: int = 0
    agent_version: str = "1.0.0"
    simulator_version: str = "1.0.0"
    dependency_info: Optional[str] = None  # 修正：从 str 改为 Optional，默认 null
    flag: str = "shulieEnterprise"  # 修正：添加默认值
    task_exceed: bool = False
    command_result: List[Any] = field(default_factory=list)  # 修正：从 Dict 改为 List
```

### 4.2 heartbeat.py - AgentStatus 数据类

**文件**: `pylinkagent/controller/heartbeat.py`

```python
@dataclass
class AgentStatus:
    agent_status: str = "INSTALLED"  # 修正：从 "running" 改为 "INSTALLED"
    agent_error_info: list = field(default_factory=list)  # 修正：从 str 改为 list
    simulator_status: str = "INSTALLED"  # 修正：从 "running" 改为 "INSTALLED"
    simulator_error_info: Optional[str] = None  # 修正：从 str 改为 Optional
    uninstall_status: int = 0
    dormant_status: int = 0
    agent_version: str = "1.0.0"
    simulator_version: str = "1.0.0"
    dependency_info: Optional[str] = None  # 修正：从 str 改为 Optional
    task_exceed: bool = False
```

### 4.3 heartbeat.py - _build_heart_request() 方法

```python
def _build_heart_request(self) -> HeartRequest:
    return HeartRequest(
        project_name=self.external_api.app_name,
        agent_id=self.external_api.agent_id,
        ip_address=ip_address,
        progress_id=progress_id,
        cur_upgrade_batch="-1",  # 修正：显式设置
        agent_status=self._status.agent_status,
        agent_error_info=self._status.agent_error_info,
        simulator_status=self._status.simulator_status,
        simulator_error_info=self._status.simulator_error_info,
        uninstall_status=self._status.uninstall_status,
        dormant_status=self._status.dormant_status,
        agent_version=self._status.agent_version,
        simulator_version=self._status.simulator_version,
        dependency_info=dependency_info if dependency_info else None,  # 修正：空值转 null
        flag="shulieEnterprise",  # 修正：显式设置
        task_exceed=self._status.task_exceed,
        command_result=self._command_results.copy(),
    )
```

---

## 五、修正后的请求格式

```json
{
  "projectName": "default_demo-test-am_test",
  "agentId": "12.11.0.110-1",
  "ipAddress": "12.11.0.110",
  "progressId": "1",
  "curUpgradeBatch": "-1",
  "agentStatus": "INSTALLED",
  "agentErrorInfo": [],
  "simulatorStatus": "INSTALLED",
  "simulatorErrorInfo": null,
  "uninstallStatus": 0,
  "dormantStatus": 0,
  "agentVersion": "1.0.0",
  "simulatorVersion": "1.0.0",
  "dependencyInfo": null,
  "flag": "shulieEnterprise",
  "taskExceed": false,
  "commandResult": []
}
```

---

## 六、验证方法

### 6.1 运行测试脚本

```bash
cd PyLinkAgent
python scripts/test_heartbeat_format.py
```

### 6.2 预期输出

```
[OK] projectName
[OK] agentId
[OK] ipAddress
[OK] progressId
[OK] curUpgradeBatch
[OK] agentStatus
[OK] agentErrorInfo is list
[OK] simulatorStatus
[OK] simulatorErrorInfo is null
[OK] uninstallStatus
[OK] dormantStatus
[OK] agentVersion
[OK] simulatorVersion
[OK] dependencyInfo is null
[OK] flag
[OK] taskExceed
[OK] commandResult is list
```

---

## 七、与控制台兼容性

修正后的心跳请求格式与 Java Agent 完全一致，确保以下功能正常：

1. **应用状态识别**: 控制台正确识别 `INSTALLED`、`RUNNING`、`ERROR` 等状态
2. **错误信息解析**: `agentErrorInfo` 作为数组被正确解析
3. **null 值处理**: `simulatorErrorInfo` 和 `dependencyInfo` 的 null 值被正确处理
4. **命令结果上报**: `commandResult` 作为数组，支持多命令结果聚合
5. **企业标识**: `flag` 字段标识企业版 Agent

---

## 八、相关文件

| 文件 | 修改内容 |
|------|---------|
| `pylinkagent/controller/external_api.py` | HeartRequest 数据类定义 |
| `pylinkagent/controller/heartbeat.py` | AgentStatus 数据类、_build_heart_request() 方法 |
| `scripts/test_heartbeat_format.py` | 新增测试脚本 |

---

## 九、后续工作

1. **实际环境测试**: 在真实环境中运行 PyLinkAgent，验证与控制台的交互
2. **命令处理**: 完善心跳返回命令的执行逻辑
3. **状态流转**: 实现 `INSTALLED` → `RUNNING` 的状态流转逻辑

---

**文档完成日期**: 2026-04-16  
**版本**: v1.0
