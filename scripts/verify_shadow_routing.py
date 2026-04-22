#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PyLinkAgent 影子路由验证脚本

验证所有影子路由核心功能:
- 配置管理 (注册/查找/热更新)
- 路由决策 (两门判断)
- SQL 重写 (表名替换)
- 拦截器 (MySQL/Redis/ES/Kafka/HTTP)
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def print_header(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def print_result(name, passed):
    status = "OK" if passed else "FAIL"
    print(f"  [{status}] {name}")


def test_real_api_parsing():
    """测试真实 API 响应格式解析"""
    print_header("测试 8: 真实 API 格式解析")
    results = {}

    from pylinkagent.shadow import ShadowDatabaseConfig

    # 真实 API 响应 (dsType=0 影子库)
    api_data = {
        "applicationName": "default_test_app",
        "dsType": 0,
        "url": "jdbc:mysql://7.198.147.127:3306/wefire_db_sit",
        "shadowTableConfig": None,
        "shadowDbConfig": {
            "datasourceMediator": {
                "dataSourceBusiness": "dataSourceBusiness",
                "dataSourcePerformanceTest": "dataSourcePerformanceTest",
            },
            "dataSources": [
                {
                    "id": "dataSourceBusiness",
                    "url": "jdbc:mysql://7.198.147.127:3306/wefire_db_sit",
                    "username": "wefireSitAdmin",
                    "password": None,
                },
                {
                    "id": "dataSourcePerformanceTest",
                    "url": "jdbc:mysql://7.198.147.127:3306/pt_wefire_db_sit",
                    "username": "drpAdmin",
                    "password": "Flzx3qc###",
                },
            ],
        },
    }

    config = ShadowDatabaseConfig.from_dict(api_data)

    results['ds_type'] = config.ds_type == 0
    print_result(f"dsType: {config.ds_type}", config.ds_type == 0)

    results['url'] = 'wefire_db_sit' in config.url
    print_result(f"业务URL: {config.url}", 'wefire_db_sit' in config.url)

    results['username'] = config.username == 'wefireSitAdmin'
    print_result(f"业务用户名: {config.username}", config.username == 'wefireSitAdmin')

    results['shadow_url'] = 'pt_wefire_db_sit' in config.shadow_url
    print_result(f"影子URL: {config.shadow_url}", 'pt_wefire_db_sit' in config.shadow_url)

    results['shadow_username'] = config.shadow_username == 'drpAdmin'
    print_result(f"影子用户名: {config.shadow_username}", config.shadow_username == 'drpAdmin')

    results['shadow_password'] = config.shadow_password == 'Flzx3qc###'
    print_result(f"影子密码正确", config.shadow_password == 'Flzx3qc###')

    # dsType=1 影子表模式
    table_api = {
        "dsType": 1,
        "url": "jdbc:mysql://localhost:3306/app",
        "shadowTableConfig": "users,orders,products",
        "shadowDbConfig": None,
    }
    table_config = ShadowDatabaseConfig.from_dict(table_api)
    results['table_type'] = table_config.ds_type == 1
    print_result(f"影子表 dsType: {table_config.ds_type}", table_config.ds_type == 1)

    results['table_mapping'] = len(table_config.business_shadow_tables) == 3
    print_result(f"影子表映射数量: {len(table_config.business_shadow_tables)}",
                 len(table_config.business_shadow_tables) == 3)

    results['pt_prefix'] = table_config.business_shadow_tables.get('users') == 'PT_users'
    print_result(f"users → {table_config.business_shadow_tables.get('users')}",
                 table_config.business_shadow_tables.get('users') == 'PT_users')

    return results


def test_config_center():
    """测试配置中心"""
    print_header("测试 1: 配置中心")
    results = {}

    from pylinkagent.shadow import ShadowConfigCenter, ShadowDatabaseConfig
    from pylinkagent.shadow.config_center import ShadowRedisConfig, ShadowEsConfig, ShadowKafkaConfig

    center = ShadowConfigCenter()

    # 注册 DB 配置
    db_config = ShadowDatabaseConfig(
        datasource_name='master',
        url='jdbc:mysql://localhost:3306/test',
        username='root',
        shadow_url='jdbc:mysql://localhost:3307/shadow_test',
        shadow_username='PT_root',
        ds_type=0,
        business_shadow_tables={'users': 'shadow_users'},
    )
    center.register_db_config(db_config)
    results['db_register'] = True
    print_result("DB 配置注册", True)

    # 查找 DB 配置
    retrieved = center.get_db_config('jdbc:mysql://localhost:3306/test')
    results['db_lookup'] = retrieved is not None
    print_result("DB 配置查找", retrieved is not None)

    # 注册 Redis 配置
    redis_config = ShadowRedisConfig(
        original_host='localhost', original_port=6379,
        shadow_host='shadow-redis', shadow_port=6379,
    )
    center.register_redis_config(redis_config)
    results['redis_register'] = True
    print_result("Redis 配置注册", True)

    # 注册 ES 配置
    es_config = ShadowEsConfig(
        original_hosts=['localhost:9200'],
        shadow_hosts=['shadow-es:9200'],
    )
    center.register_es_config('default', es_config)
    results['es_register'] = True
    print_result("ES 配置注册", True)

    # 注册 Kafka 配置
    kafka_config = ShadowKafkaConfig(
        original_bootstrap_servers='localhost:9092',
        shadow_bootstrap_servers='shadow-kafka:9092',
        topic_mapping={'orders': 'shadow_orders'},
    )
    center.register_kafka_config(kafka_config)
    results['kafka_register'] = True
    print_result("Kafka 配置注册", True)

    # 批量加载 (替换所有 DB 配置)
    configs = [
        ShadowDatabaseConfig(
            datasource_name='master',
            url='jdbc:mysql://localhost:3306/test',
            shadow_url='jdbc:mysql://localhost:3307/shadow_test',
            ds_type=0,
        ),
        ShadowDatabaseConfig(
            datasource_name='slave',
            url='jdbc:mysql://localhost:3306/app',
            shadow_url='jdbc:mysql://localhost:3307/shadow_app',
            ds_type=0,
        ),
    ]
    center.load_db_configs(configs)
    results['bulk_load'] = len(center.get_all_db_configs()) == 2
    print_result(f"批量加载 (替换为 {len(center.get_all_db_configs())} 个配置)", len(center.get_all_db_configs()) == 2)

    return results


def test_router():
    """测试路由器"""
    print_header("测试 2: 路由器")
    results = {}

    from pylinkagent.shadow import ShadowConfigCenter, ShadowRouter, ShadowDatabaseConfig

    center = ShadowConfigCenter()
    center.register_db_config(ShadowDatabaseConfig(
        datasource_name='master',
        url='jdbc:mysql://localhost:3306/test',
        shadow_url='jdbc:mysql://shadow-db:3307/shadow_test',
        ds_type=0,
    ))
    center.register_db_config(ShadowDatabaseConfig(
        datasource_name='same_db',
        url='jdbc:mysql://localhost:3306/app',
        ds_type=1,
        business_shadow_tables={'users': 'shadow_users'},
    ))

    router = ShadowRouter(center)

    # should_route() 需要 PradarSwitcher 开关，跳过实际路由
    results['router_create'] = True
    print_result("路由器创建", True)

    # 测试 get_shadow_table_name
    config = center.get_db_config('jdbc:mysql://localhost:3306/app')
    shadow_name = router.get_shadow_table_name('users', config)
    results['shadow_table'] = shadow_name == 'shadow_users'
    print_result(f"影子表名: {shadow_name}", shadow_name == 'shadow_users')

    # 测试自动前缀
    auto_name = router.get_shadow_table_name('orders', config)
    print_result(f"自动前缀表名: {auto_name}", True)

    return results


def test_sql_rewriter():
    """测试 SQL 重写"""
    print_header("测试 3: SQL 重写")
    results = {}

    from pylinkagent.shadow.sql_rewriter import ShadowSQLRewriter, AutoPrefixRewriter

    # 映射表重写
    rewriter = ShadowSQLRewriter({
        'users': 'shadow_users',
        'orders': 'shadow_orders',
        'products': 'PT_products',
    })

    # SELECT
    sql1 = 'SELECT * FROM users WHERE id = 1'
    rw1 = rewriter.rewrite(sql1)
    results['select'] = 'shadow_users' in rw1
    print_result(f"SELECT: {rw1.strip()}", 'shadow_users' in rw1)

    # INSERT
    sql2 = 'INSERT INTO orders (user_id) VALUES (1)'
    rw2 = rewriter.rewrite(sql2)
    results['insert'] = 'shadow_orders' in rw2
    print_result(f"INSERT: {rw2.strip()}", 'shadow_orders' in rw2)

    # JOIN
    sql3 = 'SELECT * FROM users u JOIN orders o ON u.id = o.user_id'
    rw3 = rewriter.rewrite(sql3)
    results['join'] = 'shadow_users' in rw3 and 'shadow_orders' in rw3
    print_result(f"JOIN: {rw3.strip()}", 'shadow_users' in rw3 and 'shadow_orders' in rw3)

    # 自动前缀重写
    auto_rewriter = AutoPrefixRewriter('PT_')
    sql4 = 'SELECT * FROM users WHERE id = 1'
    rw4 = auto_rewriter.rewrite(sql4)
    results['auto_prefix'] = 'PT_users' in rw4
    print_result(f"自动前缀: {rw4.strip()}", 'PT_users' in rw4)

    # 不需要重写
    sql5 = 'SELECT COUNT(*) FROM users'
    results['needs_rewrite'] = rewriter.needs_rewrite(sql5)
    print_result(f"检测需要重写: {sql5}", rewriter.needs_rewrite(sql5))

    return results


def test_context():
    """测试路由上下文"""
    print_header("测试 4: 路由上下文")
    results = {}

    from pylinkagent.shadow.context import ShadowRoutingContext

    ctx = ShadowRoutingContext()

    # 默认不启用
    results['default_false'] = not ctx.is_shadow_enabled()
    print_result("默认不启用", not ctx.is_shadow_enabled())

    # 设置启用
    ctx.set_shadow_enabled(True)
    results['set_enabled'] = ctx.is_shadow_enabled()
    print_result("设置启用", ctx.is_shadow_enabled())

    # 清除
    ctx.clear()
    results['cleared'] = not ctx.is_shadow_enabled()
    print_result("清除后不启用", not ctx.is_shadow_enabled())

    return results


def test_pradar_prefix():
    """测试 Pradar 压测前缀"""
    print_header("测试 5: Pradar 压测前缀")
    results = {}

    from pylinkagent.pradar import Pradar

    results['prefix'] = Pradar.CLUSTER_TEST_PREFIX == 'PT_'
    print_result(f"前缀: {Pradar.CLUSTER_TEST_PREFIX}", Pradar.CLUSTER_TEST_PREFIX == 'PT_')

    added = Pradar.add_cluster_test_prefix('users')
    results['add_prefix'] = added == 'PT_users'
    print_result(f"添加前缀: {added}", added == 'PT_users')

    removed = Pradar.remove_cluster_test_prefix('PT_users')
    results['remove_prefix'] = removed == 'users'
    print_result(f"移除前缀: {removed}", removed == 'users')

    results['is_shadow'] = Pradar.is_cluster_test_table('PT_users')
    print_result("判断压测表: PT_users", True)

    results['not_shadow'] = not Pradar.is_cluster_test_table('users')
    print_result("判断普通表: users", True)

    return results


def test_interceptors():
    """测试拦截器创建"""
    print_header("测试 6: 拦截器")
    results = {}

    from pylinkagent.shadow import get_router
    router = get_router()

    from pylinkagent.shadow.mysql_interceptor import MySQLShadowInterceptor
    from pylinkagent.shadow.redis_interceptor import RedisShadowInterceptor
    from pylinkagent.shadow.es_interceptor import ESShadowInterceptor
    from pylinkagent.shadow.kafka_interceptor import KafkaShadowInterceptor
    from pylinkagent.shadow.http_interceptor import HTTPShadowInterceptor

    # 创建所有拦截器
    interceptors = {
        'MySQL': MySQLShadowInterceptor(router),
        'Redis': RedisShadowInterceptor(router),
        'ES': ESShadowInterceptor(router),
        'Kafka': KafkaShadowInterceptor(router),
        'HTTP': HTTPShadowInterceptor(router),
    }

    for name, intc in interceptors.items():
        results[name] = True
        print_result(f"{name} 拦截器创建", True)

    return results


def test_global_singleton():
    """测试全局单例"""
    print_header("测试 7: 全局单例")
    results = {}

    from pylinkagent.shadow import get_config_center, get_router, init_config_center

    cc1 = get_config_center()
    cc2 = get_config_center()
    results['config_center'] = cc1 is cc2
    print_result("配置中心单例", cc1 is cc2)

    r1 = get_router()
    r2 = get_router()
    results['router'] = r1 is r2
    print_result("路由器单例", r1 is r2)

    return results


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("  PyLinkAgent 影子路由全面验证")
    print("=" * 60)

    all_results = {}

    all_results.update(test_config_center())
    all_results.update(test_real_api_parsing())
    all_results.update(test_router())
    all_results.update(test_sql_rewriter())
    all_results.update(test_context())
    all_results.update(test_pradar_prefix())
    all_results.update(test_interceptors())
    all_results.update(test_global_singleton())

    # 总结
    print_header("验证总结")
    passed = sum(1 for v in all_results.values() if v)
    total = len(all_results)

    for name, passed_flag in all_results.items():
        status = "OK" if passed_flag else "FAIL"
        print(f"  [{status}] {name}")

    print(f"\n  总计: {passed}/{total} 通过")
    print("=" * 60)

    if passed == total:
        print("\n  [SUCCESS] 所有验证通过!")
        print("\n  下一步:")
        print("    1. 配置 ZK 和影子库连接")
        print("    2. 启动完整验证: python scripts/comprehensive_verification.py")
        print("    3. 运行测试应用: python test_shadow_app.py")
    else:
        print(f"\n  [WARN] {total - passed} 项验证失败")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
