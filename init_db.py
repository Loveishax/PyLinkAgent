"""
数据库初始化脚本 - 直接用 Python 创建表
"""

import pymysql

MYSQL_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': '123456',
    'charset': 'utf8mb4'
}

def init_database():
    print("=" * 70)
    print(" 数据库初始化")
    print("=" * 70)

    # 连接 MySQL（不指定数据库）
    conn = pymysql.connect(
        host=MYSQL_CONFIG['host'],
        port=MYSQL_CONFIG['port'],
        user=MYSQL_CONFIG['user'],
        password=MYSQL_CONFIG['password'],
        charset=MYSQL_CONFIG['charset']
    )
    cursor = conn.cursor()

    # 创建数据库
    cursor.execute('DROP DATABASE IF EXISTS trodb')
    cursor.execute('CREATE DATABASE trodb DEFAULT CHARACTER SET utf8mb4')
    print("trodb 数据库创建成功")
    conn.commit()
    cursor.close()
    conn.close()

    # 连接到 trodb
    conn = pymysql.connect(
        host=MYSQL_CONFIG['host'],
        port=MYSQL_CONFIG['port'],
        user=MYSQL_CONFIG['user'],
        password=MYSQL_CONFIG['password'],
        database='trodb',
        charset=MYSQL_CONFIG['charset']
    )
    cursor = conn.cursor()

    # 1. 创建心跳表 t_agent_report
    cursor.execute('''
    CREATE TABLE `t_agent_report` (
      `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
      `application_id` bigint(20) DEFAULT '0',
      `application_name` varchar(64) DEFAULT '',
      `agent_id` varchar(600) NOT NULL,
      `ip_address` varchar(1024) DEFAULT '',
      `status` tinyint(2) DEFAULT '0',
      `agent_version` varchar(1024) DEFAULT '',
      `simulator_version` varchar(1024) DEFAULT NULL,
      `gmt_create` datetime DEFAULT CURRENT_TIMESTAMP,
      `gmt_update` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      `env_code` varchar(100) DEFAULT 'test',
      `tenant_id` bigint(20) DEFAULT '1',
      PRIMARY KEY (`id`),
      UNIQUE KEY `uni_app_agent` (`application_id`,`agent_id`,`env_code`,`tenant_id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ''')
    print("t_agent_report 表创建成功")

    # 2. 创建应用表 t_application_mnt
    cursor.execute('''
    CREATE TABLE `t_application_mnt` (
      `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
      `APPLICATION_ID` bigint(19) NOT NULL,
      `APPLICATION_NAME` varchar(50) NOT NULL,
      `APPLICATION_DESC` varchar(200) DEFAULT NULL,
      `USE_YN` int(1) DEFAULT '0',
      `ACCESS_STATUS` int(2) NOT NULL DEFAULT '0',
      `SWITCH_STATUS` varchar(255) NOT NULL DEFAULT 'OPENED',
      `CREATE_TIME` datetime DEFAULT CURRENT_TIMESTAMP,
      `UPDATE_TIME` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      `env_code` varchar(20) DEFAULT 'test',
      `tenant_id` bigint(20) DEFAULT '1',
      PRIMARY KEY (`id`),
      UNIQUE KEY `uk_app_name` (`APPLICATION_NAME`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ''')
    print("t_application_mnt 表创建成功")

    # 3. 创建影子库配置表 t_application_ds_manage
    cursor.execute('''
    CREATE TABLE `t_application_ds_manage` (
      `ID` bigint(20) NOT NULL AUTO_INCREMENT,
      `APPLICATION_ID` bigint(20) DEFAULT NULL,
      `APPLICATION_NAME` varchar(50) DEFAULT NULL,
      `DB_TYPE` tinyint(4) DEFAULT '0',
      `DS_TYPE` tinyint(4) DEFAULT '0',
      `CONFIG` longtext,
      `PARSE_CONFIG` longtext,
      `STATUS` tinyint(4) DEFAULT '0',
      `CREATE_TIME` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
      `UPDATE_TIME` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      `env_code` varchar(20) DEFAULT 'test',
      `tenant_id` bigint(20) DEFAULT '1',
      PRIMARY KEY (`ID`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ''')
    print("t_application_ds_manage 表创建成功")

    # 4. 创建命令结果表 t_application_node_probe
    cursor.execute('''
    CREATE TABLE `t_application_node_probe` (
      `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
      `application_name` varchar(100) NOT NULL,
      `agent_id` varchar(100) NOT NULL,
      `operate` tinyint(3) unsigned DEFAULT '0',
      `operate_result` tinyint(4) unsigned DEFAULT '99',
      `operate_id` bigint(20) unsigned DEFAULT '0',
      `probe_id` bigint(20) unsigned DEFAULT '0',
      `remark` varchar(500) DEFAULT '',
      `gmt_create` datetime DEFAULT CURRENT_TIMESTAMP,
      `gmt_update` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      `env_code` varchar(20) DEFAULT 'test',
      `tenant_id` bigint(20) DEFAULT '1',
      PRIMARY KEY (`id`),
      KEY `idx_an_ai` (`application_name`,`agent_id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ''')
    print("t_application_node_probe 表创建成功")

    # 插入测试应用
    cursor.execute('''
    INSERT INTO t_application_mnt
    (APPLICATION_ID, APPLICATION_NAME, APPLICATION_DESC, USE_YN, ACCESS_STATUS, SWITCH_STATUS, env_code, tenant_id)
    VALUES (1, 'demo-app', 'Demo Application', 0, 0, 'OPENED', 'test', 1)
    ''')
    print("测试应用 demo-app 插入成功")

    # 插入影子库配置
    shadow_config = json.dumps({
        "datasourceMediator": {
            "dataSourceBusiness": "dataSourceBusiness",
            "dataSourcePerformanceTest": "dataSourcePerformanceTest"
        },
        "dataSources": [
            {
                "id": "dataSourceBusiness",
                "url": "jdbc:mysql://master-db:3306/demo_db",
                "username": "root",
                "password": "root123"
            },
            {
                "id": "dataSourcePerformanceTest",
                "url": "jdbc:mysql://shadow-db:3306/demo_db_shadow",
                "username": "root",
                "password": "root123"
            }
        ]
    })

    cursor.execute('''
    INSERT INTO t_application_ds_manage
    (APPLICATION_ID, APPLICATION_NAME, DB_TYPE, DS_TYPE, CONFIG, PARSE_CONFIG, STATUS, env_code, tenant_id)
    VALUES (1, 'demo-app', 0, 0, %s, '{}', 0, 'test', 1)
    ''', (shadow_config,))
    print("影子库配置插入成功")

    conn.commit()
    cursor.close()
    conn.close()

    print("=" * 70)
    print(" 数据库初始化完成！")
    print("=" * 70)

if __name__ == "__main__":
    import json
    init_database()
