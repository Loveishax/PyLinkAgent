#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试心跳请求格式是否与 Java Agent 一致
"""

import sys
import os
import json

# 添加项目路径
script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
sys.path.insert(0, project_dir)

from pylinkagent.controller import HeartRequest, ExternalAPI


def test_heart_request_format():
    """测试 HeartRequest 格式"""
    print("=" * 70)
    print("测试 HeartRequest 格式".center(70))
    print("=" * 70)

    # 创建一个示例请求
    request = HeartRequest(
        project_name="default_demo-test-am_test",
        agent_id="12.11.0.110-1",
        ip_address="12.11.0.110",
        progress_id="1",
        cur_upgrade_batch="-1",
        agent_status="INSTALLED",
        agent_error_info=[],
        simulator_status="INSTALLED",
        simulator_error_info=None,
        uninstall_status=0,
        dormant_status=0,
        agent_version="1.0.0",
        simulator_version="1.0.0",
        dependency_info=None,
        flag="shulieEnterprise",
        task_exceed=False,
        command_result=[],
    )

    # 转换为字典
    data = request.to_dict()

    print("\n生成的 JSON 请求:")
    print(json.dumps(data, indent=2, ensure_ascii=False))

    # 验证关键字段
    print("\n字段验证:")
    checks = {
        'projectName': data['projectName'] == "default_demo-test-am_test",
        'agentId': data['agentId'] == "12.11.0.110-1",
        'ipAddress': data['ipAddress'] == "12.11.0.110",
        'progressId': data['progressId'] == "1",
        'curUpgradeBatch': data['curUpgradeBatch'] == "-1",
        'agentStatus': data['agentStatus'] == "INSTALLED",
        'agentErrorInfo is list': isinstance(data['agentErrorInfo'], list),
        'simulatorStatus': data['simulatorStatus'] == "INSTALLED",
        'simulatorErrorInfo is null': data['simulatorErrorInfo'] is None,
        'uninstallStatus': data['uninstallStatus'] == 0,
        'dormantStatus': data['dormantStatus'] == 0,
        'agentVersion': data['agentVersion'] == "1.0.0",
        'simulatorVersion': data['simulatorVersion'] == "1.0.0",
        'dependencyInfo is null': data['dependencyInfo'] is None,
        'flag': data['flag'] == "shulieEnterprise",
        'taskExceed': data['taskExceed'] == False,
        'commandResult is list': isinstance(data['commandResult'], list),
    }

    all_passed = True
    for field, passed in checks.items():
        status = "OK" if passed else "FAIL"
        print(f"  [{status}] {field}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 70)
    if all_passed:
        print("所有字段验证通过!")
    else:
        print("部分字段验证失败!")
    print("=" * 70)

    return all_passed


def test_empty_request():
    """测试空请求（默认值）"""
    print("\n" + "=" * 70)
    print("测试默认值".center(70))
    print("=" * 70)

    request = HeartRequest()
    data = request.to_dict()

    print("\n默认值请求:")
    print(json.dumps(data, indent=2, ensure_ascii=False))

    print("\n默认值验证:")
    checks = {
        'agentStatus default': data['agentStatus'] == "INSTALLED",
        'simulatorStatus default': data['simulatorStatus'] == "INSTALLED",
        'agentErrorInfo default is list': isinstance(data['agentErrorInfo'], list) and len(data['agentErrorInfo']) == 0,
        'simulatorErrorInfo default is null': data['simulatorErrorInfo'] is None,
        'dependencyInfo default is null': data['dependencyInfo'] is None,
        'curUpgradeBatch default': data['curUpgradeBatch'] == "-1",
        'flag default': data['flag'] == "shulieEnterprise",
        'commandResult default is list': isinstance(data['commandResult'], list) and len(data['commandResult']) == 0,
    }

    all_passed = True
    for field, passed in checks.items():
        status = "OK" if passed else "FAIL"
        print(f"  [{status}] {field}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 70)
    if all_passed:
        print("所有默认值验证通过!")
    else:
        print("部分默认值验证失败!")
    print("=" * 70)

    return all_passed


if __name__ == "__main__":
    result1 = test_heart_request_format()
    result2 = test_empty_request()

    print("\n" + "=" * 70)
    print("测试总结".center(70))
    print("=" * 70)

    if result1 and result2:
        print("所有测试通过!")
        sys.exit(0)
    else:
        print("部分测试失败!")
        sys.exit(1)
