"""
P1 优先级插桩模块功能验证

验证 Kafka 和 Elasticsearch 插桩模块的基本功能
"""

import sys
sys.path.insert(0, '.')

print("=" * 60)
print("P1 优先级插桩模块功能验证")
print("=" * 60)
print()

# ============================================
# 1. Kafka 模块验证
# ============================================
print("[1] Kafka 插桩模块验证")
print("-" * 40)

try:
    from instrument_modules.kafka_module import KafkaModule, KafkaPatcher

    # 创建模块实例
    module = KafkaModule()
    print(f"    模块名称：{module.name}")
    print(f"    模块版本：{module.version}")
    print(f"    依赖配置：{module.dependencies}")
    print(f"    默认配置：{module.default_config}")

    # 验证 Patcher
    patcher = KafkaPatcher(
        module_name="kafka",
        config={"ignored_topics": ["_internal"]},
        on_produce=lambda **kw: None,
        on_consume=lambda **kw: None,
        on_error=lambda **kw: None,
    )
    print(f"    Patcher 状态：{'已创建' if patcher else '创建失败'}")

    # 验证 Trace 上下文注入
    trace_context = {'trace_id': 'test123456789012345678901234567890ab', 'span_id': '1234567890abcdef'}
    headers = patcher._inject_trace_context(None, trace_context)
    print(f"    Trace 注入：{'成功' if headers else '失败'}")

    # 验证 Trace 上下文提取
    extracted = patcher._extract_trace_context_from_headers(headers)
    print(f"    Trace 提取：{'成功' if extracted else '失败'}")

    # 检查依赖
    deps_ok = module.check_dependencies()
    print(f"    依赖检查：{'通过' if deps_ok else '未安装 confluent-kafka'}")

    print("[OK] Kafka 模块验证通过")

except Exception as e:
    print(f"[FAIL] Kafka 模块验证失败：{e}")

print()

# ============================================
# 2. Elasticsearch 模块验证
# ============================================
print("[2] Elasticsearch 插桩模块验证")
print("-" * 40)

try:
    from instrument_modules.elasticsearch_module import ElasticsearchModule, ElasticsearchPatcher

    # 创建模块实例
    module = ElasticsearchModule()
    print(f"    模块名称：{module.name}")
    print(f"    模块版本：{module.version}")
    print(f"    依赖配置：{module.dependencies}")
    print(f"    默认配置：{module.default_config}")

    # 验证 Patcher
    patcher = ElasticsearchPatcher(
        module_name="elasticsearch",
        config={"ignored_indices": [".monitoring"]},
        on_request=lambda **kw: None,
        on_response=lambda **kw: None,
        on_error=lambda **kw: None,
    )
    print(f"    Patcher 状态：{'已创建' if patcher else '创建失败'}")

    # 验证辅助方法
    result = {'hits': {'total': 100, 'hits': []}}
    size = patcher._calculate_result_size(result)
    print(f"    结果大小计算：{size} bytes")

    bulk_body = [{'index': {}}, {'doc': 1}, {'index': {}}, {'doc': 2}]
    count = patcher._calculate_bulk_count(bulk_body)
    print(f"    Bulk 数量计算：{count} 操作")

    # 检查依赖
    deps_ok = module.check_dependencies()
    print(f"    依赖检查：{'通过' if deps_ok else '未安装 elasticsearch7'}")

    print("[OK] Elasticsearch 模块验证通过")

except Exception as e:
    print(f"[FAIL] Elasticsearch 模块验证失败：{e}")

print()

# ============================================
# 3. 模块注册验证
# ============================================
print("[3] 模块注册验证")
print("-" * 40)

try:
    from instrument_simulator.module_registry import ModuleRegistry

    registry = ModuleRegistry()

    # 注册 Kafka 模块
    from instrument_modules.kafka_module import KafkaModule
    kafka_module = KafkaModule()
    registry.register_module(kafka_module)

    # 注册 Elasticsearch 模块
    from instrument_modules.elasticsearch_module import ElasticsearchModule
    es_module = ElasticsearchModule()
    registry.register_module(es_module)

    # 验证注册
    modules = registry.get_all_modules()
    print(f"    已注册模块数：{len(modules)}")

    kafka_mod = registry.get_module("kafka")
    print(f"    Kafka 模块：{'已注册' if kafka_mod else '未注册'}")

    es_mod = registry.get_module("elasticsearch")
    print(f"    Elasticsearch 模块：{'已注册' if es_mod else '未注册'}")

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
    ["python", "-m", "pytest", "tests/test_p1_instrumentation.py", "-v", "--tb=no"],
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
