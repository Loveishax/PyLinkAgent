-- ============================================================
-- PyLinkAgent 端到端验证 - 数据库初始化脚本
-- 适用于 Takin-web / takin-ee-web
-- ============================================================

-- 创建数据库
CREATE DATABASE IF NOT EXISTS trodb
DEFAULT CHARACTER SET utf8mb4
DEFAULT COLLATE utf8mb4_unicode_ci;

USE trodb;

-- ============================================================
-- 1. 探针心跳数据表 (t_agent_report)
-- ============================================================
DROP TABLE IF EXISTS `t_agent_report`;
CREATE TABLE `t_agent_report` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `application_id` bigint(20) DEFAULT '0' COMMENT '应用 id',
  `application_name` varchar(64) DEFAULT '' COMMENT '应用名',
  `agent_id` varchar(600) NOT NULL COMMENT 'Agent 唯一标识',
  `ip_address` varchar(1024) DEFAULT '' COMMENT '节点 IP 地址',
  `progress_id` varchar(20) DEFAULT '' COMMENT '进程号',
  `agent_version` varchar(1024) DEFAULT '' COMMENT 'agent 版本号',
  `simulator_version` varchar(1024) DEFAULT NULL COMMENT 'simulator 版本',
  `cur_upgrade_batch` varchar(64) DEFAULT '0' COMMENT '升级批次',
  `status` tinyint(2) DEFAULT '0' COMMENT '节点状态 0:未知，1:启动中，2:升级待重启，3:运行中，4:异常，5:休眠，6:卸载',
  `agent_error_info` varchar(1024) DEFAULT NULL,
  `simulator_error_info` varchar(1024) DEFAULT NULL,
  `gmt_create` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `gmt_update` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `env_code` varchar(100) DEFAULT 'test' COMMENT '环境标识',
  `tenant_id` bigint(20) DEFAULT '1' COMMENT '租户 id',
  `IS_DELETED` tinyint(4) NOT NULL DEFAULT '0' COMMENT '是否有效 0:有效;1:无效',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uni_app_agent_env_tenant` (`application_id`,`agent_id`,`env_code`,`tenant_id`),
  KEY `idx_tenant_env` (`tenant_id`,`env_code`),
  KEY `idx_application_id` (`application_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='探针心跳数据';

-- ============================================================
-- 2. 应用管理表 (t_application_mnt)
-- ============================================================
DROP TABLE IF EXISTS `t_application_mnt`;
CREATE TABLE `t_application_mnt` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `APPLICATION_ID` bigint(19) NOT NULL COMMENT '应用 id',
  `APPLICATION_NAME` varchar(50) NOT NULL COMMENT '应用名称',
  `APPLICATION_DESC` varchar(200) DEFAULT NULL COMMENT '应用说明',
  `USE_YN` int(1) DEFAULT NULL COMMENT '是否可用 (0 表示启用，1 表示未启用)',
  `ACCESS_STATUS` int(2) NOT NULL DEFAULT '1' COMMENT '接入状态；0：正常；1:待配置；2:待检测;3:异常',
  `SWITCH_STATUS` varchar(255) NOT NULL DEFAULT 'OPENED' COMMENT 'OPENED:已开启',
  `CREATE_TIME` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `UPDATE_TIME` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  `env_code` varchar(20) DEFAULT 'test' COMMENT '环境 code',
  `tenant_id` bigint(20) DEFAULT '1' COMMENT '租户 id',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_app_name` (`APPLICATION_NAME`),
  KEY `idx_tenant_env` (`tenant_id`,`env_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='应用管理表';

-- ============================================================
-- 3. 应用数据源配置表 (t_application_ds_manage)
-- ============================================================
DROP TABLE IF EXISTS `t_application_ds_manage`;
CREATE TABLE `t_application_ds_manage` (
  `ID` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '主键',
  `APPLICATION_ID` bigint(20) DEFAULT NULL COMMENT '应用主键',
  `APPLICATION_NAME` varchar(50) DEFAULT NULL COMMENT '应用名称',
  `DB_TYPE` tinyint(4) DEFAULT '0' COMMENT '存储类型 0:数据库 1:缓存',
  `DS_TYPE` tinyint(4) DEFAULT '0' COMMENT '方案类型 0:影子库 1:影子表',
  `CONFIG` longtext COMMENT '配置内容 (JSON 格式)',
  `PARSE_CONFIG` longtext COMMENT '解析后配置',
  `STATUS` tinyint(4) DEFAULT '0' COMMENT '状态 0:启用；1:禁用',
  `CREATE_TIME` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `UPDATE_TIME` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `env_code` varchar(20) DEFAULT 'test' COMMENT '环境 code',
  `tenant_id` bigint(20) DEFAULT '1' COMMENT '租户 id',
  PRIMARY KEY (`ID`),
  KEY `idx_application_id` (`APPLICATION_ID`),
  KEY `idx_tenant_env` (`tenant_id`,`env_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='应用数据源配置表';

-- ============================================================
-- 4. 影子表数据源表 (t_shadow_table_datasource)
-- ============================================================
DROP TABLE IF EXISTS `t_shadow_table_datasource`;
CREATE TABLE `t_shadow_table_datasource` (
  `SHADOW_DATASOURCE_ID` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '影子表数据源 id',
  `APPLICATION_ID` bigint(20) NOT NULL COMMENT '关联应用主键 id',
  `DATABASE_IPPORT` varchar(128) NOT NULL COMMENT '数据库 ip 端口',
  `DATABASE_NAME` varchar(128) NOT NULL COMMENT '数据库名称',
  `USE_SHADOW_TABLE` int(11) DEFAULT NULL COMMENT '是否使用影子表 1:使用 0:不使用',
  `CREATE_TIME` datetime DEFAULT NULL COMMENT '插入时间',
  `UPDATE_TIME` datetime DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `tenant_id` bigint(20) NOT NULL DEFAULT '1' COMMENT '租户 id',
  `env_code` varchar(20) NOT NULL DEFAULT 'test' COMMENT '环境变量',
  PRIMARY KEY (`SHADOW_DATASOURCE_ID`),
  KEY `idx_application_id` (`APPLICATION_ID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='影子表数据源';

-- ============================================================
-- 5. 影子 Job 配置表 (t_shadow_job_config)
-- ============================================================
DROP TABLE IF EXISTS `t_shadow_job_config`;
CREATE TABLE `t_shadow_job_config` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'id',
  `application_id` bigint(20) NOT NULL COMMENT '应用 ID',
  `name` varchar(256) DEFAULT NULL COMMENT 'Job 名称',
  `type` tinyint(4) NOT NULL COMMENT 'JOB 类型 0:quartz、1:elastic-job、2:xxl-job',
  `config_code` text COMMENT '配置代码 (JSON 格式)',
  `status` tinyint(3) DEFAULT '1' COMMENT '0:可用 1:不可用',
  `active` tinyint(3) DEFAULT '1' COMMENT '0:启用 1:禁用',
  `gmt_create` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `gmt_update` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `env_code` varchar(100) DEFAULT 'test' COMMENT '环境标识',
  `tenant_id` bigint(20) DEFAULT '1' COMMENT '租户 id',
  PRIMARY KEY (`id`),
  KEY `idx_application_id` (`application_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='影子 Job 配置';

-- ============================================================
-- 6. 应用节点探针操作表 (t_application_node_probe)
-- ============================================================
DROP TABLE IF EXISTS `t_application_node_probe`;
CREATE TABLE `t_application_node_probe` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `application_name` varchar(100) NOT NULL COMMENT '应用名称',
  `agent_id` varchar(100) NOT NULL COMMENT 'Agent ID',
  `operate` tinyint(3) unsigned DEFAULT '0' COMMENT '操作类型 1:安装，3:升级，2:卸载，0:无',
  `operate_result` tinyint(4) unsigned DEFAULT '99' COMMENT '操作结果 0:失败，1:成功，99:无',
  `operate_id` bigint(20) unsigned DEFAULT '0' COMMENT '操作 id',
  `probe_id` bigint(20) unsigned DEFAULT '0' COMMENT '对应的探针包记录 id',
  `remark` varchar(500) DEFAULT '' COMMENT '备注信息',
  `gmt_create` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `gmt_update` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `env_code` varchar(20) DEFAULT 'test' COMMENT '环境 code',
  `tenant_id` bigint(20) DEFAULT '1' COMMENT '租户 id',
  PRIMARY KEY (`id`),
  KEY `idx_an_ai` (`application_name`,`agent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='应用节点探针操作表';

-- ============================================================
-- 初始化测试数据
-- ============================================================

USE trodb;

-- 1. 插入测试应用
INSERT INTO `t_application_mnt`
(`APPLICATION_ID`, `APPLICATION_NAME`, `APPLICATION_DESC`, `USE_YN`, `ACCESS_STATUS`, `SWITCH_STATUS`, `env_code`, `tenant_id`)
VALUES
(1, 'demo-app', 'Demo Application for PyLinkAgent', 0, 0, 'OPENED', NOW(), NOW(), 'test', 1),
(2, 'test-app', 'Test Application', 0, 0, 'OPENED', NOW(), NOW(), 'test', 1);

-- 2. 插入影子库配置 (demo-app)
INSERT INTO `t_application_ds_manage`
(`APPLICATION_ID`, `APPLICATION_NAME`, `DB_TYPE`, `DS_TYPE`, `CONFIG`, `PARSE_CONFIG`, `STATUS`, `CREATE_TIME`, `UPDATE_TIME`, `env_code`, `tenant_id`)
VALUES
(1, 'demo-app', 0, 0,
'{
  "datasourceMediator": {
    "dataSourceBusiness": "dataSourceBusiness",
    "dataSourcePerformanceTest": "dataSourcePerformanceTest"
  },
  "dataSources": [
    {
      "id": "dataSourceBusiness",
      "url": "jdbc:mysql://master-db:3306/demo_db?useUnicode=true&characterEncoding=utf8",
      "username": "root",
      "password": "root123",
      "driverClassName": "com.mysql.cj.jdbc.Driver",
      "minIdle": 5,
      "maxActive": 20
    },
    {
      "id": "dataSourcePerformanceTest",
      "url": "jdbc:mysql://shadow-db:3306/demo_db_shadow?useUnicode=true&characterEncoding=utf8",
      "username": "root",
      "password": "root123",
      "driverClassName": "com.mysql.cj.jdbc.Driver",
      "minIdle": 5,
      "maxActive": 20
    }
  ]
}',
'{
  "datasourceMediator": {
    "dataSourceBusiness": "dataSourceBusiness",
    "dataSourcePerformanceTest": "dataSourcePerformanceTest"
  },
  "dataSources": [
    {
      "id": "dataSourceBusiness",
      "url": "jdbc:mysql://master-db:3306/demo_db",
      "username": "root",
      "password": "***"
    },
    {
      "id": "dataSourcePerformanceTest",
      "url": "jdbc:mysql://shadow-db:3306/demo_db_shadow",
      "username": "root",
      "password": "***"
    }
  ]
}',
0, NOW(), NOW(), 'test', 1);

-- 3. 插入影子库配置 (test-app)
INSERT INTO `t_application_ds_manage`
(`APPLICATION_ID`, `APPLICATION_NAME`, `DB_TYPE`, `DS_TYPE`, `CONFIG`, `PARSE_CONFIG`, `STATUS`, `CREATE_TIME`, `UPDATE_TIME`, `env_code`, `tenant_id`)
VALUES
(2, 'test-app', 0, 0,
'{
  "datasourceMediator": {
    "dataSourceBusiness": "master",
    "dataSourcePerformanceTest": "shadow"
  },
  "dataSources": [
    {
      "id": "master",
      "url": "jdbc:mysql://192.168.1.100:3306/test_db",
      "username": "root",
      "password": "password123"
    },
    {
      "id": "shadow",
      "url": "jdbc:mysql://192.168.1.101:3306/test_db_shadow",
      "username": "root",
      "password": "password123"
    }
  ]
}',
'{}',
0, NOW(), NOW(), 'test', 1);

-- ============================================================
-- 验证查询
-- ============================================================

-- 检查所有表
SELECT 'Tables created:' AS info;
SHOW TABLES LIKE 't_%';

-- 检查应用数据
SELECT 'Application data:' AS info;
SELECT APPLICATION_ID, APPLICATION_NAME, ACCESS_STATUS, SWITCH_STATUS FROM t_application_mnt;

-- 检查影子库配置
SELECT 'Shadow database config:' AS info;
SELECT ID, APPLICATION_NAME, DS_TYPE, STATUS FROM t_application_ds_manage;

-- ============================================================
-- 说明
-- ============================================================
-- 1. t_agent_report: 心跳数据通过 /api/agent/heartbeat 接口自动插入
-- 2. t_application_mnt: 需要预先创建应用，否则心跳上报会失败
-- 3. t_application_ds_manage: 影子库配置通过管理侧前端配置或 SQL 插入
-- 4. 所有表都包含 tenant_id 和 env_code 字段，用于多租户和环境隔离
-- ============================================================
