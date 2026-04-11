-- ============================================================
-- PyLinkAgent 配套数据库表定义
-- 适用于 Takin-web / takin-ee-web 后端服务
-- ============================================================

-- ----------------------------
-- 1. 探针心跳数据表 (t_agent_report)
-- 用途：存储 Agent 上报的心跳数据，展示应用节点状态
-- 对应接口：POST /api/agent/heartbeat
-- ----------------------------
DROP TABLE IF EXISTS `t_agent_report`;
CREATE TABLE `t_agent_report` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `application_id` bigint(20) DEFAULT '0' COMMENT '应用 id',
  `application_name` varchar(64) DEFAULT '' COMMENT '应用名',
  `agent_id` varchar(600) NOT NULL COMMENT 'Agent 唯一标识',
  `ip_address` varchar(1024) DEFAULT '' COMMENT '节点 IP 地址',
  `progress_id` varchar(20) DEFAULT '' COMMENT '进程号',
  `agent_version` varchar(1024) DEFAULT '' COMMENT 'agent 版本号',
  `simulator_version` varchar(1024) DEFAULT NULL COMMENT 'simulator 版本 (Pradar 版本)',
  `cur_upgrade_batch` varchar(64) DEFAULT '0' COMMENT '升级批次，根据升级内容生成 MD5',
  `status` tinyint(2) DEFAULT '0' COMMENT '节点状态 0:未知，1:启动中，2:升级待重启，3:运行中，4:异常，5:休眠，6:卸载',
  `agent_error_info` varchar(1024) DEFAULT NULL COMMENT 'agent 的错误信息',
  `simulator_error_info` varchar(1024) DEFAULT NULL COMMENT 'simulator 错误信息',
  `gmt_create` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `gmt_update` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `env_code` varchar(100) DEFAULT 'test' COMMENT '环境标识',
  `tenant_id` bigint(20) DEFAULT '1' COMMENT '租户 id，默认 1',
  `IS_DELETED` tinyint(4) NOT NULL DEFAULT '0' COMMENT '是否有效 0:有效;1:无效',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE KEY `uni_applicationId_agentId_envCode_tenantId` (`application_id`,`agent_id`,`env_code`,`tenant_id`) USING BTREE,
  KEY `idx_tenant_env` (`tenant_id`,`env_code`) USING BTREE,
  KEY `idx_application_id` (`application_id`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='探针心跳数据';

-- ----------------------------
-- 2. 应用管理表 (t_application_mnt)
-- 用途：存储应用基本信息，Agent 上报时需要先有应用记录
-- 对应接口：GET /api/application/center/app/info (管理侧内部使用)
-- ----------------------------
DROP TABLE IF EXISTS `t_application_mnt`;
CREATE TABLE `t_application_mnt` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `APPLICATION_ID` bigint(19) NOT NULL COMMENT '应用 id',
  `APPLICATION_NAME` varchar(50) NOT NULL COMMENT '应用名称',
  `APPLICATION_DESC` varchar(200) DEFAULT NULL COMMENT '应用说明',
  `DDL_SCRIPT_PATH` varchar(200) NOT NULL DEFAULT '' COMMENT '影子库表结构脚本路径',
  `CLEAN_SCRIPT_PATH` varchar(200) NOT NULL DEFAULT '' COMMENT '数据清理脚本路径',
  `READY_SCRIPT_PATH` varchar(200) NOT NULL DEFAULT '' COMMENT '基础数据准备脚本路径',
  `BASIC_SCRIPT_PATH` varchar(200) NOT NULL DEFAULT '' COMMENT '铺底数据脚本路径',
  `CACHE_SCRIPT_PATH` varchar(200) NOT NULL DEFAULT '' COMMENT '缓存预热脚本地址',
  `CACHE_EXP_TIME` bigint(19) NOT NULL DEFAULT '0' COMMENT '缓存失效时间 (单位秒)',
  `USE_YN` int(1) DEFAULT NULL COMMENT '是否可用 (0 表示启用，1 表示未启用)',
  `AGENT_VERSION` varchar(16) DEFAULT NULL COMMENT 'java agent 版本',
  `NODE_NUM` int(4) NOT NULL DEFAULT '1' COMMENT '节点数量',
  `ACCESS_STATUS` int(2) NOT NULL DEFAULT '1' COMMENT '接入状态；0：正常；1；待配置；2：待检测;3：异常',
  `SWITCH_STATUS` varchar(255) NOT NULL DEFAULT 'OPENED' COMMENT 'OPENED:已开启，OPENING:开启中，OPEN_FAILING:开启异常，CLOSED:已关闭，CLOSING:关闭中，CLOSE_FAILING:关闭异常',
  `EXCEPTION_INFO` text COMMENT '接入异常信息',
  `CREATE_TIME` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `UPDATE_TIME` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  `ALARM_PERSON` varchar(64) DEFAULT NULL COMMENT '告警人',
  `PRADAR_VERSION` varchar(30) DEFAULT NULL COMMENT 'pradar Agent 版本',
  `customer_id` bigint(20) DEFAULT NULL COMMENT '租户 id (已废弃)',
  `USER_ID` bigint(11) DEFAULT NULL COMMENT '所属用户',
  `env_code` varchar(20) DEFAULT 'test' COMMENT '环境 code',
  `tenant_id` bigint(20) DEFAULT '1' COMMENT '租户 id',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE KEY `index_identifier_application_name` (`APPLICATION_NAME`,`customer_id`) USING BTREE,
  KEY `T_APLICATION_MNT_INDEX2` (`USE_YN`) USING BTREE,
  KEY `t_application_mnt_tenant_id_env_code_APPLICATION_ID_index` (`tenant_id`,`env_code`,`APPLICATION_ID`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COMMENT='应用管理表';

-- ----------------------------
-- 3. 应用数据源配置表 (t_application_ds_manage)
-- 用途：存储影子库配置数据，Agent 通过配置拉取接口获取
-- 对应接口：GET /api/link/ds/configs/pull
-- ----------------------------
DROP TABLE IF EXISTS `t_application_ds_manage`;
CREATE TABLE `t_application_ds_manage` (
  `ID` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '主键',
  `APPLICATION_ID` bigint(20) DEFAULT NULL COMMENT '应用主键',
  `APPLICATION_NAME` varchar(50) DEFAULT NULL COMMENT '应用名称',
  `DB_TYPE` tinyint(4) DEFAULT '0' COMMENT '存储类型 0:数据库 1:缓存',
  `DS_TYPE` tinyint(4) DEFAULT '0' COMMENT '方案类型 0:影子库 1:影子表 2:影子 server',
  `URL` varchar(250) DEFAULT NULL COMMENT '数据库 url，影子表需填',
  `CONFIG` longtext COMMENT 'xml 配置或 JSON 配置',
  `PARSE_CONFIG` longtext COMMENT '解析后配置 (JSON 格式)',
  `STATUS` tinyint(4) DEFAULT '0' COMMENT '状态 0:启用；1:禁用',
  `customer_id` bigint(20) DEFAULT NULL COMMENT '租户 id (已废弃)',
  `USER_ID` bigint(20) DEFAULT NULL COMMENT '用户 id',
  `CREATE_TIME` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `UPDATE_TIME` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '更新时间',
  `IS_DELETED` tinyint(4) DEFAULT '0' COMMENT '是否有效 0:有效;1:无效',
  `env_code` varchar(20) DEFAULT 'test' COMMENT '环境 code',
  `tenant_id` bigint(20) DEFAULT '1' COMMENT '租户 id',
  `sign` varchar(255) DEFAULT NULL COMMENT '数据签名',
  PRIMARY KEY (`ID`) USING BTREE,
  KEY `idx_application_id` (`APPLICATION_ID`) USING BTREE,
  KEY `idx_tenant_env` (`tenant_id`,`env_code`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='应用数据源配置表';

-- ----------------------------
-- 4. 影子表数据源表 (t_shadow_table_datasource)
-- 用途：存储影子表数据源配置
-- ----------------------------
DROP TABLE IF EXISTS `t_shadow_table_datasource`;
CREATE TABLE `t_shadow_table_datasource` (
  `SHADOW_DATASOURCE_ID` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '影子表数据源 id',
  `APPLICATION_ID` bigint(20) NOT NULL COMMENT '关联应用主键 id',
  `DATABASE_IPPORT` varchar(128) NOT NULL COMMENT '数据库 ip 端口 xx.xx.xx.xx:xx',
  `DATABASE_NAME` varchar(128) NOT NULL COMMENT '数据库名称',
  `USE_SHADOW_TABLE` int(11) DEFAULT NULL COMMENT '是否使用影子表 1:使用 0:不使用',
  `CREATE_TIME` datetime DEFAULT NULL COMMENT '插入时间',
  `UPDATE_TIME` datetime DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `tenant_id` bigint(20) NOT NULL DEFAULT '1' COMMENT '租户 id',
  `env_code` varchar(20) NOT NULL DEFAULT 'test' COMMENT '环境变量',
  PRIMARY KEY (`SHADOW_DATASOURCE_ID`) USING BTREE,
  KEY `idx_application_id` (`APPLICATION_ID`) USING BTREE,
  KEY `idx_tenant_env` (`tenant_id`,`env_code`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='影子表数据源';

-- ----------------------------
-- 5. 影子 Job 配置表 (t_shadow_job_config)
-- 用途：存储影子 Job 配置，Agent 通过配置拉取接口获取
-- 对应接口：GET /api/shadow/job/queryByAppName
-- ----------------------------
DROP TABLE IF EXISTS `t_shadow_job_config`;
CREATE TABLE `t_shadow_job_config` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'id',
  `application_id` bigint(20) NOT NULL COMMENT '应用 ID',
  `name` varchar(256) DEFAULT NULL COMMENT 'Job 名称',
  `type` tinyint(4) NOT NULL COMMENT 'JOB 类型 0:quartz、1:elastic-job、2:xxl-job',
  `config_code` text COMMENT '配置代码 (JSON 格式)',
  `status` tinyint(3) DEFAULT '1' COMMENT '0:可用 1:不可用',
  `active` tinyint(3) DEFAULT '1' COMMENT '0:启用 1:禁用',
  `customer_id` bigint(20) DEFAULT NULL COMMENT '租户 id(已废弃)',
  `user_id` bigint(20) DEFAULT NULL COMMENT '用户 id',
  `is_deleted` tinyint(3) unsigned DEFAULT '0' COMMENT '是否删除 0:未删除、1:已删除',
  `gmt_create` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `gmt_update` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `env_code` varchar(100) DEFAULT 'test' COMMENT '环境标识',
  `tenant_id` bigint(20) DEFAULT '1' COMMENT '租户 id',
  PRIMARY KEY (`id`) USING BTREE,
  KEY `idx_application_id` (`application_id`) USING BTREE,
  KEY `idx_tenant_env` (`tenant_id`,`env_code`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='影子 Job 配置';

-- ----------------------------
-- 6. 影子 MQ 消费者表 (t_shadow_mq_consumer)
-- 用途：存储影子 MQ 消费者配置，Agent 通过配置拉取接口获取
-- 对应接口：GET /api/agent/configs/shadow/consumer
-- ----------------------------
DROP TABLE IF EXISTS `t_shadow_mq_consumer`;
CREATE TABLE `t_shadow_mq_consumer` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '主键 id',
  `topic_group` varchar(1000) DEFAULT NULL COMMENT 'topic+group，以#号拼接',
  `type` varchar(20) DEFAULT NULL COMMENT '白名单类型',
  `application_id` bigint(20) DEFAULT NULL COMMENT '应用 id',
  `application_name` varchar(200) DEFAULT NULL COMMENT '应用名称',
  `status` int(11) DEFAULT '1' COMMENT '是否可用 (0:未启用，1:已启用)',
  `deleted` int(11) DEFAULT '0' COMMENT '是否删除 (0:未删除，1:已删除)',
  `customer_id` bigint(20) DEFAULT NULL COMMENT '租户 id(已废弃)',
  `user_id` bigint(20) DEFAULT NULL COMMENT '用户 id',
  `feature` text COMMENT '拓展字段',
  `gmt_create` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `gmt_update` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `env_code` varchar(100) DEFAULT 'test' COMMENT '环境标识',
  `tenant_id` bigint(20) DEFAULT '1' COMMENT '租户 id',
  PRIMARY KEY (`id`) USING BTREE,
  KEY `idx_application_id` (`application_id`) USING BTREE,
  KEY `idx_tenant_env` (`tenant_id`,`env_code`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='影子 MQ 消费者';

-- ----------------------------
-- 7. 应用节点探针操作表 (t_application_node_probe)
-- 用途：存储 Agent 节点操作记录 (安装/升级/卸载)
-- 对应接口：GET /api/agent/application/node/probe/operate
-- ----------------------------
DROP TABLE IF EXISTS `t_application_node_probe`;
CREATE TABLE `t_application_node_probe` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `customer_id` bigint(20) unsigned NOT NULL DEFAULT '1' COMMENT '租户 id',
  `application_name` varchar(100) NOT NULL COMMENT '应用名称',
  `agent_id` varchar(100) NOT NULL COMMENT 'Agent ID',
  `operate` tinyint(3) unsigned DEFAULT '0' COMMENT '操作类型 1:安装，3:升级，2:卸载，0:无',
  `operate_result` tinyint(4) unsigned DEFAULT '99' COMMENT '操作结果 0:失败，1:成功，99:无',
  `operate_id` bigint(20) unsigned DEFAULT '0' COMMENT '操作 id，时间戳递增',
  `probe_id` bigint(20) unsigned DEFAULT '0' COMMENT '对应的探针包记录 id',
  `remark` varchar(500) DEFAULT '' COMMENT '备注信息',
  `gmt_create` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `gmt_update` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `is_deleted` tinyint(3) unsigned DEFAULT '0' COMMENT '逻辑删除 0:未删除，1:已删除',
  `env_code` varchar(20) DEFAULT 'test' COMMENT '环境 code',
  `tenant_id` bigint(20) DEFAULT '1' COMMENT '租户 id',
  `sign` varchar(255) DEFAULT NULL COMMENT '数据签名',
  PRIMARY KEY (`id`) USING BTREE,
  KEY `idx_an_ai_cid` (`application_name`,`agent_id`,`customer_id`) USING BTREE,
  KEY `idx_tenant_env` (`tenant_id`,`env_code`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='应用节点探针操作表';

-- ============================================================
-- 初始化数据 - 用于测试验证
-- ============================================================

-- 1. 插入测试应用
INSERT INTO `t_application_mnt`
(`APPLICATION_ID`, `APPLICATION_NAME`, `APPLICATION_DESC`, `USE_YN`, `ACCESS_STATUS`, `SWITCH_STATUS`, `CREATE_TIME`, `UPDATE_TIME`, `env_code`, `tenant_id`)
VALUES
(1, 'test-app', '测试应用', 0, 0, 'OPENED', NOW(), NOW(), 'test', 1);

-- 2. 插入影子库配置 (JSON 格式)
INSERT INTO `t_application_ds_manage`
(`APPLICATION_ID`, `APPLICATION_NAME`, `DB_TYPE`, `DS_TYPE`, `CONFIG`, `PARSE_CONFIG`, `STATUS`, `CREATE_TIME`, `UPDATE_TIME`, `env_code`, `tenant_id`)
VALUES
(1, 'test-app', 0, 0,
'{
  "datasourceMediator": {
    "dataSourceBusiness": "dataSourceBusiness",
    "dataSourcePerformanceTest": "dataSourcePerformanceTest"
  },
  "dataSources": [
    {
      "id": "dataSourceBusiness",
      "url": "jdbc:mysql://master-db:3306/test_db?useUnicode=true&characterEncoding=utf8",
      "username": "root",
      "password": "password123"
    },
    {
      "id": "dataSourcePerformanceTest",
      "url": "jdbc:mysql://shadow-db:3306/test_db_shadow?useUnicode=true&characterEncoding=utf8",
      "username": "root_shadow",
      "password": "shadow_password123",
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
      "url": "jdbc:mysql://master-db:3306/test_db",
      "username": "root"
    },
    {
      "id": "dataSourcePerformanceTest",
      "url": "jdbc:mysql://shadow-db:3306/test_db_shadow",
      "username": "root_shadow",
      "password": "***",
      "minIdle": 5,
      "maxActive": 20
    }
  ]
}',
0, NOW(), NOW(), 'test', 1);

-- ============================================================
-- 说明
-- ============================================================
-- 1. t_agent_report: 心跳数据通过 /api/agent/heartbeat 接口自动插入
-- 2. t_application_mnt: 需要预先创建应用，否则心跳上报会失败
-- 3. t_application_ds_manage: 影子库配置通过管理侧前端配置或 SQL 插入
-- 4. 所有表都包含 tenant_id 和 env_code 字段，用于多租户和环境隔离
-- 5. 时间字段使用 datetime 类型，兼容 MySQL 5.7+
-- ============================================================
