@echo off
REM Takin-web Mock Server 快速启动脚本
REM
REM 使用方法:
REM   start_mock.bat [DB_HOST] [DB_PORT] [DB_USER] [DB_PASSWORD]
REM
REM 示例:
REM   start_mock.bat localhost 3306 root password123

setlocal enabledelayedexpansion

echo ============================================================
echo Takin-web Mock Server 快速启动
echo ============================================================
echo.

REM 配置变量
set DB_HOST=%~1
if "%DB_HOST%"=="" set DB_HOST=localhost

set DB_PORT=%~2
if "%DB_PORT%"=="" set DB_PORT=3306

set DB_USER=%~3
if "%DB_USER%"=="" set DB_USER=root

set DB_PASSWORD=%~4

set DB_NAME=trodb
set MOCK_PORT=9999

echo 配置信息:
echo   MySQL: %DB_HOST%:%DB_PORT%
echo   数据库：%DB_NAME%
echo   Mock 服务端口：%MOCK_PORT%
echo.

REM 切换到脚本所在目录
cd /d "%~dp0"

REM 步骤 1: 检查 Python 环境
echo [1/4] 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误：未找到 Python
    exit /b 1
)
echo ✓ Python 环境检查通过
echo.

REM 步骤 2: 安装依赖
echo [2/4] 安装 Python 依赖...
pip install -q fastapi uvicorn pymysql
echo ✓ 依赖安装完成
echo.

REM 步骤 3: 检查数据库
echo [3/4] 检查 MySQL 数据库...
where mysql >nul 2>&1
if errorlevel 1 (
    echo 警告：未找到 MySQL 客户端，跳过数据库检查
    echo 请确保数据库 %DB_NAME% 已创建
) else (
    if "%DB_PASSWORD%"=="" (
        mysql -h%DB_HOST% -P%DB_PORT% -u%DB_USER% -e "USE %DB_NAME%" >nul 2>&1
    ) else (
        mysql -h%DB_HOST% -P%DB_PORT% -u%DB_USER% -p%DB_PASSWORD% -e "USE %DB_NAME%" >nul 2>&1
    )
    if errorlevel 1 (
        echo 错误：无法访问数据库 %DB_NAME%
        echo 请先执行：mysql -u %DB_USER% -p < database\end_to_end_init.sql
        exit /b 1
    )
    echo ✓ 数据库检查通过
)
echo.

REM 步骤 4: 启动 Mock 服务
echo [4/4] 启动 Takin-web Mock Server...
echo.

if "%DB_PASSWORD%"=="" (
    python takin_mock_server.py ^
        --host 0.0.0.0 ^
        --port %MOCK_PORT% ^
        --db-host %DB_HOST% ^
        --db-port %DB_PORT% ^
        --db-user %DB_USER% ^
        --db-name %DB_NAME%
) else (
    python takin_mock_server.py ^
        --host 0.0.0.0 ^
        --port %MOCK_PORT% ^
        --db-host %DB_HOST% ^
        --db-port %DB_PORT% ^
        --db-user %DB_USER% ^
        --db-password %DB_PASSWORD% ^
        --db-name %DB_NAME%
)

echo.
echo ============================================================
echo Mock 服务已停止
echo ============================================================
