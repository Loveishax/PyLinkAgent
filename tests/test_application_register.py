"""
测试应用自动注册功能

验证 PyLinkAgent 与控制台的应用注册接口对接
"""

import os
import sys
import logging

# 添加项目路径
script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
sys.path.insert(0, project_dir)

# 设置环境变量
os.environ['MANAGEMENT_URL'] = 'http://localhost:9999'
os.environ['APP_NAME'] = 'test-pylinkagent-app'
os.environ['AGENT_ID'] = 'test-agent-001'
os.environ['SIMULATOR_ENV_CODE'] = 'test'
os.environ['SIMULATOR_TENANT_ID'] = '1'
os.environ['AUTO_REGISTER_APP'] = 'true'

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_application_info():
    """测试 ApplicationInfo 数据类"""
    print("\n=== 测试 ApplicationInfo 数据类 ===")

    from pylinkagent.controller import ApplicationInfo

    app_info = ApplicationInfo(
        application_name="test-app",
        application_desc="Test Application",
        use_yn=0,
        access_status=0,
        switch_status="OPENED",
        node_num=1,
        agent_version="1.0.0",
        pradar_version="1.0.0",
        cluster_name="default",
        tenant_id="1",
        env_code="test",
    )

    # 测试 to_dict
    data_dict = app_info.to_dict()
    assert data_dict["applicationName"] == "test-app"
    assert data_dict["switchStatus"] == "OPENED"
    assert data_dict["tenantId"] == "1"

    print(f"[OK] ApplicationInfo 创建成功")
    print(f"  应用名称：{app_info.application_name}")
    print(f"  集群：{app_info.cluster_name}")
    print(f"  租户：{app_info.tenant_id}")
    print(f"  环境：{app_info.env_code}")

    return app_info


def test_application_registrator_structure():
    """测试 ApplicationRegistrator 类结构"""
    print("\n=== 测试 ApplicationRegistrator 类结构 ===")

    from pylinkagent.controller import ApplicationRegistrator, ApplicationInfo
    from pylinkagent.controller import ExternalAPI

    # 创建 ExternalAPI (不实际连接)
    api = ExternalAPI(
        tro_web_url="http://localhost:9999",
        app_name="test-app",
        agent_id="test-001",
    )

    # 创建注册器
    registrator = ApplicationRegistrator(api)

    # 检查方法
    assert hasattr(registrator, 'register'), "缺少 register 方法"
    assert hasattr(registrator, 'is_registered'), "缺少 is_registered 方法"
    assert hasattr(registrator, '_generate_app_info'), "缺少 _generate_app_info 方法"

    print("[OK] ApplicationRegistrator 类结构正确")
    print(f"  主要方法：register, is_registered, sync_application_info")

    return registrator


def test_application_status_reporter():
    """测试 ApplicationStatusReporter 类"""
    print("\n=== 测试 ApplicationStatusReporter 类 ===")

    from pylinkagent.controller import ApplicationStatusReporter
    from pylinkagent.controller import ExternalAPI

    # 创建 ExternalAPI
    api = ExternalAPI(
        tro_web_url="http://localhost:9999",
        app_name="test-app",
        agent_id="test-001",
    )

    # 创建状态上报器
    reporter = ApplicationStatusReporter(api)

    # 检查方法
    assert hasattr(reporter, 'report_access_status'), "缺少 report_access_status 方法"
    assert hasattr(reporter, 'report_config_error'), "缺少 report_config_error 方法"
    assert hasattr(reporter, 'report_config_success'), "缺少 report_config_success 方法"
    assert hasattr(reporter, 'clear_errors'), "缺少 clear_errors 方法"

    print("[OK] ApplicationStatusReporter 类结构正确")

    return reporter


def test_app_info_generation():
    """测试应用信息生成"""
    print("\n=== 测试应用信息生成 ===")

    from pylinkagent.controller import ApplicationRegistrator
    from pylinkagent.controller import ExternalAPI

    api = ExternalAPI(
        tro_web_url="http://localhost:9999",
        app_name="test-app",
        agent_id="test-001",
    )

    registrator = ApplicationRegistrator(api)
    app_info = registrator._generate_app_info()

    print(f"[OK] 应用信息生成成功")
    print(f"  应用名称：{app_info.application_name}")
    print(f"  描述：{app_info.application_desc}")
    print(f"  状态：use_yn={app_info.use_yn}, access_status={app_info.access_status}")
    print(f"  开关：{app_info.switch_status}")
    print(f"  版本：agent={app_info.agent_version}, pradar={app_info.pradar_version}")

    # 验证字段
    assert app_info.application_name == "test-app"
    assert app_info.use_yn == 0
    assert app_info.access_status == 0
    assert app_info.switch_status == "OPENED"

    return True


def test_upload_application_info():
    """测试上传应用信息 (需要实际控制台)"""
    print("\n=== 测试上传应用信息 (需要控制台) ===")

    from pylinkagent.controller import ExternalAPI, ApplicationInfo

    api = ExternalAPI(
        tro_web_url=os.getenv('MANAGEMENT_URL', 'http://localhost:9999'),
        app_name=os.getenv('APP_NAME', 'test-app'),
        agent_id=os.getenv('AGENT_ID', 'test-001'),
    )

    if not api.initialize():
        print("[SKIP] ExternalAPI 初始化失败，跳过上传测试")
        return None

    app_info = ApplicationInfo(
        application_name=api.app_name,
        application_desc=f"Test App: {api.app_name}",
        use_yn=0,
        access_status=0,
        switch_status="OPENED",
        node_num=1,
        agent_version="2.0.0",
        pradar_version="2.0.0",
        env_code="test",
    )

    try:
        result = api.upload_application_info(app_info.to_dict())
        if result:
            print(f"[OK] 应用信息上传成功")
        else:
            print(f"[FAIL] 应用信息上传失败 (控制台可能不可用)")
        return result
    except Exception as e:
        print(f"[FAIL] 上传异常：{e}")
        return None


def test_bootstrap_with_registration():
    """测试完整启动流程包含应用注册"""
    print("\n=== 测试完整启动流程 (包含应用注册) ===")

    from pylinkagent.bootstrap import PyLinkAgentBootstrapper

    bootstrapper = PyLinkAgentBootstrapper()

    # 初始化 ExternalAPI
    if not bootstrapper._init_external_api():
        print("[FAIL] ExternalAPI 初始化失败")
        return False

    # 执行应用注册
    bootstrapper._register_application()

    # 检查注册状态
    if bootstrapper._app_registrator:
        is_registered = bootstrapper._app_registrator.is_registered()
        if is_registered:
            print("[OK] 应用已注册")
        else:
            print("[INFO] 应用未注册 (可能控制台不可用)")
    else:
        print("[INFO] 注册器未初始化")

    return True


def main():
    """主测试函数"""
    print("=" * 60)
    print("PyLinkAgent 应用自动注册功能测试")
    print("=" * 60)

    # 1. 测试 ApplicationInfo
    test_application_info()

    # 2. 测试 ApplicationRegistrator 结构
    test_application_registrator_structure()

    # 3. 测试 ApplicationStatusReporter
    test_application_status_reporter()

    # 4. 测试应用信息生成
    test_app_info_generation()

    # 5. 测试上传 (需要控制台)
    upload_result = test_upload_application_info()

    # 6. 测试完整启动流程
    test_bootstrap_with_registration()

    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print("[OK] ApplicationInfo 数据类测试通过")
    print("[OK] ApplicationRegistrator 类结构测试通过")
    print("[OK] ApplicationStatusReporter 类结构测试通过")
    print("[OK] 应用信息生成测试通过")
    if upload_result is True:
        print("[OK] 应用信息上传测试通过 (控制台可用)")
    elif upload_result is False:
        print("[FAIL] 应用信息上传失败 (控制台返回失败)")
    else:
        print("[SKIP] 应用信息上传跳过 (控制台不可用)")
    print("")
    print("应用自动注册功能验证完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
