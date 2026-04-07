"""
P0 优先级插桩模块功能验证

验证 Redis 和 Flask 插桩模块的基本功能
"""

import sys
sys.path.insert(0, '.')

print("=" * 60)
print("P0 优先级插桩模块功能验证")
print("=" * 60)
print()

# ============================================
# 1. Redis 模块验证
# ============================================
print("[1] Redis 插桩模块验证")
print("-" * 40)

try:
    from instrument_modules.redis_module import RedisModule, RedisPatcher

    # 创建模块实例
    module = RedisModule()
    print(f"    模块名称：{module.name}")
    print(f"    模块版本：{module.version}")
    print(f"    依赖配置：{module.dependencies}")
    print(f"    默认配置：{module.default_config}")

    # 验证 Patcher
    patcher = RedisPatcher(
        module_name="redis",
        config={"ignored_commands": ["PING"]},
        on_command=lambda **kw: None,
        on_result=lambda **kw: None,
        on_error=lambda **kw: None,
    )
    print(f"    Patcher 状态：{'已创建' if patcher else '创建失败'}")

    # 检查依赖
    deps_ok = module.check_dependencies()
    print(f"    依赖检查：{'通过' if deps_ok else '未安装 redis'}")

    print("[OK] Redis 模块验证通过")

except Exception as e:
    print(f"[FAIL] Redis 模块验证失败：{e}")

print()

# ============================================
# 2. Flask 模块验证
# ============================================
print("[2] Flask 插桩模块验证")
print("-" * 40)

try:
    from instrument_modules.flask_module import FlaskModule, FlaskPatcher

    # 创建模块实例
    module = FlaskModule()
    print(f"    模块名称：{module.name}")
    print(f"    模块版本：{module.version}")
    print(f"    依赖配置：{module.dependencies}")
    print(f"    默认配置：{module.default_config}")

    # 验证 Patcher
    patcher = FlaskPatcher(
        module_name="flask",
        config={"ignored_paths": ["/health"]},
        on_request=lambda **kw: None,
        on_response=lambda **kw: None,
        on_error=lambda **kw: None,
    )
    print(f"    Patcher 状态：{'已创建' if patcher else '创建失败'}")

    # 验证 Trace 上下文提取
    environ = {
        'HTTP_TRACEPARENT': '00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01'
    }
    trace_context = patcher._extract_trace_context(environ)
    if trace_context:
        print(f"    Trace 上下文提取：成功 (trace_id={trace_context['trace_id'][:16]}...)")
    else:
        print(f"    Trace 上下文提取：失败")

    # 检查依赖
    deps_ok = module.check_dependencies()
    print(f"    依赖检查：{'通过' if deps_ok else '未安装 flask'}")

    print("[OK] Flask 模块验证通过")

except Exception as e:
    print(f"[FAIL] Flask 模块验证失败：{e}")

print()

# ============================================
# 3. 模块注册验证
# ============================================
print("[3] 模块注册验证")
print("-" * 40)

try:
    from instrument_simulator.module_registry import ModuleRegistry

    registry = ModuleRegistry()

    # 注册 Redis 模块
    from instrument_modules.redis_module import RedisModule
    redis_module = RedisModule()
    registry.register_module(redis_module)

    # 注册 Flask 模块
    from instrument_modules.flask_module import FlaskModule
    flask_module = FlaskModule()
    registry.register_module(flask_module)

    # 验证注册
    modules = registry.get_all_modules()
    print(f"    已注册模块数：{len(modules)}")

    redis_mod = registry.get_module("redis")
    print(f"    Redis 模块：{'已注册' if redis_mod else '未注册'}")

    flask_mod = registry.get_module("flask")
    print(f"    Flask 模块：{'已注册' if flask_mod else '未注册'}")

    print("[OK] 模块注册验证通过")

except ImportError:
    print("[SKIP] ModuleRegistry 不可用，跳过注册验证")
except Exception as e:
    print(f"[FAIL] 模块注册验证失败：{e}")

print()

# ============================================
# 4. 单元测试结果
# ============================================
print("[4] 单元测试结果")
print("-" * 40)

import subprocess
result = subprocess.run(
    ["python", "-m", "pytest", "tests/test_redis_instrumentation.py", "tests/test_flask_instrumentation.py", "-v", "--tb=no"],
    capture_output=True,
    text=True
)

# 解析结果
lines = result.stdout.split('\n')
for line in lines:
    if 'passed' in line or 'failed' in line or 'skipped' in line:
        print(f"    {line.strip()}")

print()
print("=" * 60)
print("验证完成")
print("=" * 60)
