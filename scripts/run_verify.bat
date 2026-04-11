@echo off
REM PyLinkAgent 端到端验证快速启动脚本 (Windows 批处理版本)
REM
REM 使用方法:
REM   run_verify.bat [MYSQL_HOST] [MYSQL_PORT] [MYSQL_USER] [MYSQL_PASSWORD]
REM
REM 示例:
REM   run_verify.bat localhost 3306 root password123

setlocal enabledelayedexpansion

echo ============================================================
echo PyLinkAgent 端到端验证快速启动
echo ============================================================
echo.

REM 配置变量
set MYSQL_HOST=%~1
if "%MYSQL_HOST%"=="" set MYSQL_HOST=localhost

set MYSQL_PORT=%~2
if "%MYSQL_PORT%"=="" set MYSQL_PORT=3306

set MYSQL_USER=%~3
if "%MYSQL_USER%"=="" set MYSQL_USER=root

set MYSQL_PASSWORD=%~4

set MYSQL_DB=trodb
set TAKIN_URL=http://localhost:9999
set APP_NAME=demo-app
set AGENT_ID=pylinkagent-001

echo 配置信息:
echo   MySQL: %MYSQL_HOST%:%MYSQL_PORT%
echo   数据库：%MYSQL_DB%
echo   Takin-web Mock: %TAKIN_URL%
echo   应用：%APP_NAME%
echo   Agent ID: %AGENT_ID%
echo.

REM 切换到脚本所在目录
cd /d "%~dp0"
set WORK_DIR=%CD%
set PYLINKAGENT_DIR=%WORK_DIR%\..

REM 步骤 1: 检查 Python 环境
echo [1/6] 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误：未找到 Python
    exit /b 1
)
echo ✓ Python 环境检查通过
echo.

REM 步骤 2: 安装依赖
echo [2/6] 安装 Python 依赖...
cd "%PYLINKAGENT_DIR%"
pip install -q -r requirements.txt
pip install -q pymysql httpx fastapi uvicorn
echo ✓ 依赖安装完成
echo.

REM 步骤 3: 初始化数据库
echo [3/6] 初始化数据库...
where mysql >nul 2>&1
if errorlevel 1 (
    echo 警告：未找到 MySQL 客户端，跳过数据库初始化
    echo 请手动执行：mysql -u %MYSQL_USER% -p ^< database\end_to_end_init.sql
) else (
    echo 执行数据库初始化脚本...
    if "%MYSQL_PASSWORD%"=="" (
        mysql -h%MYSQL_HOST% -P%MYSQL_PORT% -u%MYSQL_USER% ^< database\end_to_end_init.sql
    ) else (
        mysql -h%MYSQL_HOST% -P%MYSQL_PORT% -u%MYSQL_USER% -p%MYSQL_PASSWORD% ^< database\end_to_end_init.sql
    )
    echo ✓ 数据库初始化完成
)
echo.

REM 步骤 4: 启动 Takin-web Mock Server
echo [4/6] 启动 Takin-web Mock Server...
start "Takin-web Mock Server" cmd /k "cd %PYLINKAGENT_DIR% && python takin_mock_server.py --port 9999 --db-host %MYSQL_HOST% --db-port %MYSQL_PORT% --db-user %MYSQL_USER% --db-password %MYSQL_PASSWORD% --db-name %MYSQL_DB%"
echo ✓ Takin-web Mock Server 已启动 (端口 9999)
timeout /t 3 /nobreak >nul
echo.

REM 步骤 5: 检查 Mock Server 状态
echo [5/6] 检查 Mock Server 状态...
curl -s %TAKIN_URL%/health >nul 2>&1
if errorlevel 1 (
    echo 警告：Mock Server 可能未正常启动
) else (
    echo ✓ Mock Server 运行正常
)
echo.

REM 步骤 6: 运行端到端验证
echo [6/6] 运行端到端验证...
python scripts\end_to_end_verify.py ^
    --mysql-host %MYSQL_HOST% ^
    --mysql-port %MYSQL_PORT% ^
    --mysql-user %MYSQL_USER% ^
    --mysql-db %MYSQL_DB% ^
    --takin-url %TAKIN_URL% ^
    --app-name %APP_NAME% ^
    --agent-id %AGENT_ID%

set VERIFY_RESULT=%ERRORLEVEL%
echo.

REM 显示结果
echo ============================================================
echo 验证结果...
echo ============================================================
if %VERIFY_RESULT% equ 0 (
    echo ✓ 所有验证通过！
) else (
    echo ✗ 部分验证失败，请查看日志文件
)
echo.

REM 显示下一步操作
echo ============================================================
echo 下一步操作:
echo ============================================================
echo.
echo 1. 启动 Demo 应用 (新命令行窗口):
echo    cd %PYLINKAGENT_DIR%
echo    python demo_app.py
echo.
echo 2. 测试压测流量路由:
echo    REM 正常流量
echo    curl http://localhost:8000/api/users
echo.
echo    REM 压测流量
echo    curl http://localhost:8000/api/users -H "x-pressure-test: true"
echo.
echo 3. 查看 PyLinkAgent 状态:
echo    curl http://localhost:8000/pylinkagent/status
echo.
echo 4. 查看影子库配置:
echo    curl http://localhost:8000/pylinkagent/config
echo.
echo 5. 查看心跳记录:
echo    mysql -u %MYSQL_USER% -p -e "SELECT * FROM trodb.t_agent_report ORDER BY gmt_update DESC LIMIT 5;"
echo.
echo ============================================================
echo 验证完成！
echo ============================================================

if exist verify_result.txt (
    echo.
    echo 验证报告已保存到：verify_result.txt
)

exit /b %VERIFY_RESULT%
