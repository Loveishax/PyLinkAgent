"""
Takin-web 轻量级模拟器 (与原始 Takin-web 接口保持一致)

实现的核心接口 (与原始 Java 项目完全一致):
- POST /api/agent/heartbeat - 心跳上报 (AgentHeartbeatController)
- POST /api/application/center/app/info - 应用上传 (ApplicationController)
- GET /api/link/ds/configs/pull - 影子库配置拉取 (ShadowTableConfigController)
- GET /api/agent/application/node/probe/operate - 命令拉取
- POST /api/agent/application/node/probe/operateResult - 命令结果上报
"""

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
import pymysql
import json
import logging
from datetime import datetime
import socket

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("takin-mock")

app = FastAPI(title="Takin-web Mock Server", version="6.0.0")

# 数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': '123456',
    'database': 'trodb',
    'charset': 'utf8mb4'
}


def get_db_connection():
    """获取数据库连接"""
    try:
        conn = pymysql.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"数据库连接失败：{e}")
        raise


def get_local_ip():
    """获取本机 IP 地址"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'


# ==================== 请求/响应模型 (与 Java 项目一致) ====================

class AgentHeartbeatRequest(BaseModel):
    """
    心跳请求 - 对应 Java: AgentHeartbeatRequest

    必填字段 (与 Java @NotNull/@NotBlank 一致):
    - projectName: 应用名
    - agentId: Agent ID
    - ipAddress: IP 地址
    - progressId: 进程号
    - curUpgradeBatch: 当前批次号
    - agentStatus: Agent 状态
    - uninstallStatus: 卸载状态
    - dormantStatus: 休眠状态
    - agentVersion: Agent 版本
    """
    projectName: str = Field(..., description="应用名")
    agentId: str = Field(..., description="Agent ID")
    ipAddress: str = Field(..., description="IP 地址")
    progressId: str = Field(..., description="进程号")
    curUpgradeBatch: str = Field(..., description="当前批次号")
    agentStatus: str = Field(..., description="Agent 状态")
    agentErrorInfo: Optional[str] = Field(None, description="Agent 错误信息")
    simulatorStatus: Optional[str] = Field(None, description="Simulator 状态")
    simulatorErrorInfo: Optional[str] = Field(None, description="Simulator 错误信息")
    uninstallStatus: int = Field(..., description="卸载状态 0:未卸载 1:已卸载")
    dormantStatus: int = Field(..., description="休眠状态 0:未休眠 1:已休眠")
    agentVersion: str = Field(..., description="Agent 版本")
    simulatorVersion: Optional[str] = Field(None, description="Simulator 版本")
    dependencyInfo: Optional[str] = Field(None, description="Agent 依赖信息")
    commandResult: Optional[List[Dict[str, Any]]] = Field(None, description="命令执行结果")
    flag: Optional[str] = Field("shulieEnterprise", description="企业版标识")
    taskExceed: Optional[bool] = Field(False, description="任务超时标识")


class AgentCommandResBO(BaseModel):
    """
    命令响应 - 对应 Java: AgentCommandResBO

    返回给 Agent 的待执行命令
    """
    id: int = Field(default=-1, description="命令 ID")
    commandType: int = Field(default=1, description="命令类型 1:框架命令 2:模块命令")
    operateType: int = Field(default=1, description="操作类型 1:安装 2:卸载 3:升级")
    dataPath: Optional[str] = Field(None, description="数据路径")
    commandTime: int = Field(default=0, description="命令时间戳")
    liveTime: int = Field(default=-1, description="存活时间 -1:无限")
    useLocal: bool = Field(default=False, description="是否使用本地")
    extras: Optional[Dict[str, Any]] = Field(default=None, description="扩展数据")
    extrasString: Optional[str] = Field(None, description="扩展字符串数据")


class ApplicationVo(BaseModel):
    """
    应用信息 - 对应 Java: ApplicationVo

    用于应用上传和查询
    """
    id: Optional[str] = Field(None, description="系统 ID")
    applicationName: str = Field(..., description="应用名称")
    applicationDesc: Optional[str] = Field(None, description="应用描述")
    useYn: int = Field(default=0, description="是否启用 0:启用 1:禁用")
    accessStatus: int = Field(default=0, description="接入状态 0:正常 1:待配置 2:待检测 3:异常")
    switchStatus: str = Field(default="OPENED", description="开关状态 OPENED/CLOSED")
    nodeNum: int = Field(default=1, description="节点数")
    agentVersion: Optional[str] = Field(None, description="Agent 版本")
    pradarVersion: Optional[str] = Field(None, description="Pradar 版本")
    envCode: Optional[str] = Field("test", description="环境代码")
    tenantId: Optional[int] = Field(1, description="租户 ID")


class ResponseModel(BaseModel):
    """
    通用响应模型 - 对应 Java: Response<T>
    """
    success: bool = Field(default=True, description="是否成功")
    data: Optional[Any] = Field(default=None, description="响应数据")
    errorCode: Optional[str] = Field(default=None, description="错误编码")
    errorMessage: Optional[str] = Field(default=None, description="错误信息")
    message: Optional[str] = Field(default="success", description="响应消息")


class ShadowTableConfigVo(BaseModel):
    """
    影子表配置 - 对应 Java: TShadowTableConfigVo
    """
    id: Optional[int] = Field(None, description="ID")
    applicationId: int = Field(..., description="应用 ID")
    applicationName: str = Field(..., description="应用名称")
    dsType: int = Field(default=0, description="数据源类型 0:数据库 1:Redis 2:MQ 等")
    config: str = Field(..., description="配置 JSON 字符串")
    parseConfig: str = Field(default="{}", description="解析后的配置")
    status: int = Field(default=0, description="状态 0:启用 1:禁用")
    envCode: Optional[str] = Field("test", description="环境代码")
    tenantId: Optional[int] = Field(1, description="租户 ID")


# ==================== 数据库操作 ====================

def save_heartbeat_to_db(request: AgentHeartbeatRequest) -> bool:
    """
    保存心跳记录到数据库 t_agent_report

    对应 Java: AgentReportService.insertOrUpdate()
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 查询应用 ID
        cursor.execute(
            "SELECT APPLICATION_ID FROM t_application_mnt WHERE APPLICATION_NAME = %s",
            (request.projectName,)
        )
        result = cursor.fetchone()
        application_id = result[0] if result else 0

        # 根据 agentStatus 和 simulatorStatus 计算 status
        # 对应 Java: AgentReportStatusEnum
        status = 0  # UNKNOWN
        if request.uninstallStatus == 1:
            status = 5  # UNINSTALL
        elif request.dormantStatus == 1:
            status = 4  # SLEEP
        elif request.agentStatus == "INSTALLED" and not request.simulatorStatus:
            status = 2  # STARTING
        elif request.agentStatus == "UNINSTALL" and not request.simulatorStatus:
            status = 1  # BEGIN
        elif request.agentStatus == "INSTALL_FAILED":
            status = 6  # ERROR
        elif request.agentStatus == "INSTALLED" and request.simulatorStatus == "INSTALLED":
            status = 3  # RUNNING

        # 插入心跳记录
        sql = """
        INSERT INTO t_agent_report
        (application_id, application_name, agent_id, status, ip_address,
         agent_version, simulator_version, gmt_update, tenant_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), 1)
        ON DUPLICATE KEY UPDATE
        status = VALUES(status), gmt_update = NOW(), ip_address = VALUES(ip_address), agent_version = VALUES(agent_version)
        """
        cursor.execute(sql, (
            application_id,
            request.projectName,
            request.agentId,
            status,
            request.ipAddress,
            request.agentVersion,
            request.simulatorVersion or ""
        ))
        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"心跳已保存：application={request.projectName}, agent={request.agentId}, status={status}")
        return True
    except Exception as e:
        logger.error(f"保存心跳失败：{e}")
        return False


def get_application_id_by_name(app_name: str) -> Optional[int]:
    """根据应用名查询应用 ID"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT APPLICATION_ID FROM t_application_mnt WHERE APPLICATION_NAME = %s", (app_name,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        logger.error(f"查询应用 ID 失败：{e}")
        return None


def save_application_info_to_db(app_info: ApplicationVo) -> bool:
    """
    保存应用信息到数据库 t_application_mnt

    对应 Java: ApplicationService.addApplication()
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 检查应用是否已存在
        cursor.execute(
            "SELECT APPLICATION_ID FROM t_application_mnt WHERE APPLICATION_NAME = %s",
            (app_info.applicationName,)
        )
        result = cursor.fetchone()

        if not result:
            # 插入新应用
            application_id = int(datetime.now().timestamp() * 1000) % 10000000000
            sql = """
            INSERT INTO t_application_mnt
            (APPLICATION_ID, APPLICATION_NAME, APPLICATION_DESC, USE_YN, ACCESS_STATUS,
             SWITCH_STATUS, env_code, tenant_id, UPDATE_TIME)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """
            cursor.execute(sql, (
                application_id,
                app_info.applicationName,
                app_info.applicationDesc or app_info.applicationName,
                app_info.useYn,
                app_info.accessStatus,
                app_info.switchStatus,
                app_info.envCode or 'test',
                app_info.tenantId or 1
            ))
            conn.commit()
            logger.info(f"应用已保存：{app_info.applicationName}, applicationId={application_id}")
        else:
            # 更新已有应用
            sql = """
            UPDATE t_application_mnt
            SET APPLICATION_DESC = %s, USE_YN = %s, ACCESS_STATUS = %s,
                SWITCH_STATUS = %s, env_code = %s, UPDATE_TIME = NOW()
            WHERE APPLICATION_NAME = %s
            """
            cursor.execute(sql, (
                app_info.applicationDesc or app_info.applicationName,
                app_info.useYn,
                app_info.accessStatus,
                app_info.switchStatus,
                app_info.envCode or 'test',
                app_info.applicationName
            ))
            conn.commit()
            logger.info(f"应用已更新：{app_info.applicationName}")

        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"保存应用信息失败：{e}")
        return False


def get_shadow_config_from_db(application_name: str) -> Optional[Dict]:
    """
    从数据库获取影子库配置

    对应 Java: ShadowTableConfigService.agentGetShadowTable()
    返回格式与原始项目一致
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # 从 t_application_ds_manage 表查询配置
        sql = """
        SELECT ID, APPLICATION_ID, APPLICATION_NAME, CONFIG, PARSE_CONFIG, STATUS
        FROM t_application_ds_manage
        WHERE APPLICATION_NAME = %s AND STATUS = 0
        """
        cursor.execute(sql, (application_name,))
        result = cursor.fetchone()

        cursor.close()
        conn.close()

        if result:
            config_str = result.get('CONFIG', '{}')
            if isinstance(config_str, str):
                return json.loads(config_str)
            return config_str
        return None
    except Exception as e:
        logger.error(f"获取影子库配置失败：{e}")
        return None


def save_command_result_to_db(app_name: str, agent_id: str, result: Dict) -> bool:
    """保存命令执行结果到数据库"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        application_id = get_application_id_by_name(app_name)

        sql = """
        INSERT INTO t_application_node_probe
        (APPLICATION_ID, APPLICATION_NAME, AGENT_ID, COMMAND_ID, RESULT_STATUS,
         ERROR_MSG, gmt_create, tenant_id)
        VALUES (%s, %s, %s, %s, %s, %s, NOW(), 1)
        """
        cursor.execute(sql, (
            application_id or 0,
            app_name,
            agent_id,
            result.get('commandId', 0),
            1 if result.get('success', False) else 0,
            result.get('errorMsg', '')
        ))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"保存命令结果失败：{e}")
        return False


# ==================== API 接口 (与原始 Takin-web 完全一致) ====================

@app.get("/")
async def index():
    """首页"""
    return {
        "service": "Takin-web Mock Server",
        "version": "6.0.0",
        "status": "running",
        "description": "模拟原始 Takin-web 的核心接口",
        "endpoints": [
            "POST /api/agent/heartbeat - 心跳上报",
            "GET /api/agent/application/node/probe/operate - 命令拉取",
            "POST /api/agent/application/node/probe/operateResult - 命令结果上报",
            "POST /api/application/center/app/info - 应用上传",
            "GET /api/link/ds/configs/pull - 影子库配置拉取"
        ]
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.post("/api/agent/heartbeat")
async def heartbeat(request: AgentHeartbeatRequest) -> List[Dict[str, Any]]:
    """
    心跳上报接口

    对应原始项目: AgentHeartbeatController.process()
    接口路径：POST /api/agent/heartbeat

    处理逻辑:
    1. 获取处理器集合 (根据 flag 判断是否企业版)
    2. 检测状态 (构建 AgentHeartbeatBO)
    3. 异步处理上报的命令结果
    4. 保存心跳数据到 t_agent_report
    5. 返回待执行命令列表

    Args:
        request: 心跳请求，包含应用名、agentId、状态等信息

    Returns:
        List[AgentCommandResBO]: 待执行命令列表，无命令时返回空数组
    """
    logger.info(f"收到心跳：application={request.projectName}, agent={request.agentId}, "
                f"status={request.agentStatus}, ip={request.ipAddress}")

    # 保存心跳数据到数据库
    save_heartbeat_to_db(request)

    # 处理上报的命令结果 (如果有)
    if request.commandResult:
        for cmd_result in request.commandResult:
            save_command_result_to_db(
                request.projectName,
                request.agentId,
                cmd_result
            )
            logger.info(f"处理命令结果：commandId={cmd_result.get('id', 'unknown')}")

    # 返回空命令列表 (没有需要执行的操作)
    # 对应 Java: 返回 List<AgentCommandResBO>
    return []


@app.post("/api/application/center/app/info")
async def upload_application_info(app_info: ApplicationVo) -> ResponseModel:
    """
    应用信息上传接口

    对应原始项目: ApplicationController.addApplication()
    接口路径：POST /console/application/center/app/info

    处理逻辑:
    1. 检查应用是否已存在
    2. 不存在则插入新应用
    3. 存在则更新应用信息
    4. 返回 applicationId

    Args:
        app_info: 应用信息，包含应用名称、描述、开关状态等

    Returns:
        Response: {success: true, data: {applicationId: xxx}}
    """
    logger.info(f"收到应用上传：application={app_info.applicationName}")

    # 保存应用信息
    save_application_info_to_db(app_info)

    # 查询 applicationId 并返回
    application_id = get_application_id_by_name(app_info.applicationName)

    return ResponseModel(
        success=True,
        data={"applicationId": application_id or 0},
        message="success"
    )


@app.get("/api/link/ds/configs/pull")
async def get_shadow_config(appName: str) -> ResponseModel:
    """
    影子库配置拉取接口

    对应原始项目: ShadowTableConfigController.agentGetShadowTableConfig()
    接口路径：GET /api/link/ds/configs/pull?appName=xxx

    处理逻辑:
    1. 根据 appName 查询 t_application_ds_manage 表
    2. 返回 CONFIG 字段的 JSON 数据

    Args:
        appName: 应用名称

    Returns:
        Response: {success: true, data: {...shadow config...}}

    配置格式示例:
    {
        "datasourceMediator": {
            "dynamicDatasource": [
                {
                    "name": "dataSourceBusiness",
                    "shadow": false,
                    "url": "jdbc:mysql://master:3306/app",
                    "username": "root",
                    "shadowUrl": "jdbc:mysql://shadow:3306/app_shadow"
                }
            ]
        }
    }
    """
    logger.info(f"收到配置拉取请求：application={appName}")

    # 从数据库获取配置
    config = get_shadow_config_from_db(appName)

    if config:
        return ResponseModel(
            success=True,
            data=config,
            message="success"
        )
    else:
        # 返回默认配置 (如果没有配置)
        default_config = {
            "datasourceMediator": {
                "dynamicDatasource": [
                    {
                        "name": "dataSourceBusiness",
                        "shadow": False,
                        "url": "jdbc:mysql://localhost:3306/demo_db",
                        "username": "root",
                        "shadowUrl": "jdbc:mysql://localhost:3306/demo_db_shadow"
                    }
                ]
            }
        }
        return ResponseModel(
            success=True,
            data=default_config,
            message="no config found, returning default"
        )


@app.get("/api/agent/application/node/probe/operate")
async def pull_commands(applicationName: Optional[str] = None, agentId: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    命令拉取接口

    对应原始项目: AgentApplicationNodeController.pullCommands()
    接口路径：GET /api/agent/application/node/probe/operate?appName=xxx&agentId=xxx

    处理逻辑:
    1. 查询 t_application_node_probe 表获取待执行命令
    2. 返回命令列表

    Args:
        applicationName: 应用名称
        agentId: Agent ID

    Returns:
        List[CommandPacket]: 命令列表，无命令时返回空数组
    """
    logger.info(f"收到命令拉取请求：application={applicationName}, agent={agentId}")

    # 返回空命令列表
    return []


@app.post("/api/agent/application/node/probe/operateResult")
async def report_command_result(request: Dict[str, Any]) -> ResponseModel:
    """
    命令结果上报接口

    对应原始项目: AgentApplicationNodeController.reportResult()
    接口路径：POST /api/agent/application/node/probe/operateResult

    处理逻辑:
    1. 接收命令执行结果
    2. 保存到 t_application_node_probe 表
    3. 返回成功响应

    Args:
        request: 命令执行结果，包含 appName, agentId, operateResult, errorMsg 等

    Returns:
        Response: {success: true, data: null}
    """
    app_name = request.get('appName', 'unknown')
    agent_id = request.get('agentId', 'unknown')
    logger.info(f"收到命令结果上报：application={app_name}, agent={agent_id}")

    save_command_result_to_db(app_name, agent_id, request)

    return ResponseModel(
        success=True,
        data=None,
        message="success"
    )


@app.get("/api/application/center/list")
async def query_application_list(
    applicationName: Optional[str] = None,
    pageNum: int = 1,
    pageSize: int = 20
) -> ResponseModel:
    """
    应用列表查询接口

    对应原始项目: ApplicationController.pageApplicationWithAuth()
    接口路径：GET /api/application/center/list

    Args:
        applicationName: 应用名称 (可选，用于模糊查询)
        pageNum: 页码
        pageSize: 每页数量

    Returns:
        Response: {success: true, data: {list: [...], total: xxx}}
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        if applicationName:
            sql = """
            SELECT APPLICATION_ID, APPLICATION_NAME, APPLICATION_DESC, USE_YN,
                   ACCESS_STATUS, SWITCH_STATUS, env_code, tenant_id, gmt_update
            FROM t_application_mnt
            WHERE APPLICATION_NAME LIKE %s
            ORDER BY gmt_update DESC
            LIMIT %s, %s
            """
            cursor.execute(sql, (f"%{applicationName}%", (pageNum - 1) * pageSize, pageSize))
        else:
            sql = """
            SELECT APPLICATION_ID, APPLICATION_NAME, APPLICATION_DESC, USE_YN,
                   ACCESS_STATUS, SWITCH_STATUS, env_code, tenant_id, gmt_update
            FROM t_application_mnt
            ORDER BY gmt_update DESC
            LIMIT %s, %s
            """
            cursor.execute(sql, ((pageNum - 1) * pageSize, pageSize))

        app_list = cursor.fetchall()

        # 查询总数
        if applicationName:
            cursor.execute("SELECT COUNT(*) as cnt FROM t_application_mnt WHERE APPLICATION_NAME LIKE %s",
                          (f"%{applicationName}%",))
        else:
            cursor.execute("SELECT COUNT(*) as cnt FROM t_application_mnt")
        total = cursor.fetchone()['cnt']

        cursor.close()
        conn.close()

        return ResponseModel(
            success=True,
            data={"list": app_list, "total": total}
        )
    except Exception as e:
        logger.error(f"查询应用列表失败：{e}")
        return ResponseModel(
            success=False,
            data={"list": [], "total": 0},
            errorCode="500",
            errorMessage=str(e)
        )


# ==================== 主程序 ====================

# 命令行参数解析
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Takin-web Mock Server")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, default=9999, help="监听端口")
    parser.add_argument("--db-host", default="localhost", help="MySQL 主机")
    parser.add_argument("--db-port", type=int, default=3306, help="MySQL 端口")
    parser.add_argument("--db-user", default="root", help="MySQL 用户")
    parser.add_argument("--db-password", default="123456", help="MySQL 密码")
    parser.add_argument("--db-name", default="trodb", help="数据库名称")

    args = parser.parse_args()

    # 更新数据库配置
    DB_CONFIG.update({
        'host': args.db_host,
        'port': args.db_port,
        'user': args.db_user,
        'password': args.db_password,
        'database': args.db_name
    })

    logger.info(f"启动 Takin-web Mock Server on {args.host}:{args.port}")
    logger.info(f"数据库配置：{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    logger.info("接口与原始 Takin-web 项目 6.0.0 版本保持一致")

    uvicorn.run(app, host=args.host, port=args.port)
