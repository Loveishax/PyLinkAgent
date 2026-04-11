#!/bin/bash
# PyLinkAgent 端到端验证快速启动脚本
# 适用于 Windows Git Bash 环境

set -e

echo "============================================================"
echo "PyLinkAgent 端到端验证快速启动"
echo "============================================================"
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置变量
MYSQL_HOST="${MYSQL_HOST:-localhost}"
MYSQL_PORT="${MYSQL_PORT:-3306}"
MYSQL_USER="${MYSQL_USER:-root}"
MYSQL_PASSWORD="${MYSQL_PASSWORD:-}"
MYSQL_DB="${MYSQL_DB:-trodb}"
TAKIN_URL="${TAKIN_URL:-http://localhost:9999}"
APP_NAME="${APP_NAME:-demo-app}"
AGENT_ID="${AGENT_ID:-pylinkagent-001}"

# 切换到脚本所在目录
cd "$(dirname "$0")"
WORK_DIR=$(pwd)
PYLINKAGENT_DIR="$WORK_DIR"

echo "配置信息:"
echo "  MySQL: $MYSQL_HOST:$MYSQL_PORT"
echo "  数据库：$MYSQL_DB"
echo "  Takin-web: $TAKIN_URL"
echo "  应用：$APP_NAME"
echo "  Agent ID: $AGENT_ID"
echo ""

# 步骤 1: 检查 Python 环境
echo -e "${BLUE}[1/6] 检查 Python 环境...${NC}"
if ! command -v python &> /dev/null; then
    echo -e "${RED}错误：未找到 Python${NC}"
    exit 1
fi
python --version
echo -e "${GREEN}✓ Python 环境检查通过${NC}"
echo ""

# 步骤 2: 安装依赖
echo -e "${BLUE}[2/6] 安装 Python 依赖...${NC}"
cd "$PYLINKAGENT_DIR"
pip install -q -r requirements.txt
pip install -q pymysql httpx
echo -e "${GREEN}✓ 依赖安装完成${NC}"
echo ""

# 步骤 3: 初始化数据库
echo -e "${BLUE}[3/6] 初始化数据库...${NC}"
if command -v mysql &> /dev/null; then
    echo "执行数据库初始化脚本..."
    if [ -n "$MYSQL_PASSWORD" ]; then
        mysql -h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" < database/end_to_end_init.sql
    else
        mysql -h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER" < database/end_to_end_init.sql
    fi
    echo -e "${GREEN}✓ 数据库初始化完成${NC}"
else
    echo -e "${YELLOW}警告：未找到 MySQL 客户端，跳过数据库初始化${NC}"
    echo "请手动执行：mysql -u $MYSQL_USER < database/end_to_end_init.sql"
fi
echo ""

# 步骤 4: 检查 Takin-web 服务
echo -e "${BLUE}[4/6] 检查 Takin-web 服务...${NC}"
if curl -s "$TAKIN_URL" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Takin-web 服务可访问${NC}"
else
    echo -e "${YELLOW}警告：Takin-web 服务不可访问 ($TAKIN_URL)${NC}"
    echo "请确保 Takin-web 服务已启动"
fi
echo ""

# 步骤 5: 运行端到端验证
echo -e "${BLUE}[5/6] 运行端到端验证...${NC}"
python scripts/end_to_end_verify.py \
    --mysql-host "$MYSQL_HOST" \
    --mysql-port "$MYSQL_PORT" \
    --mysql-user "$MYSQL_USER" \
    --mysql-password "$MYSQL_PASSWORD" \
    --mysql-db "$MYSQL_DB" \
    --takin-url "$TAKIN_URL" \
    --app-name "$APP_NAME" \
    --agent-id "$AGENT_ID"

VERIFY_RESULT=$?
echo ""

# 步骤 6: 显示结果
echo -e "${BLUE}[6/6] 验证结果...${NC}"
if [ $VERIFY_RESULT -eq 0 ]; then
    echo -e "${GREEN}✓ 所有验证通过！${NC}"
else
    echo -e "${RED}✗ 部分验证失败，请查看日志文件${NC}"
fi
echo ""

# 显示下一步操作
echo "============================================================"
echo "下一步操作:"
echo "============================================================"
echo ""
echo "1. 启动 Demo 应用:"
echo "   cd $PYLINKAGENT_DIR"
echo "   python demo_app.py"
echo ""
echo "2. 测试压测流量路由:"
echo "   # 正常流量"
echo '   curl http://localhost:8000/api/users'
echo ""
echo "   # 压测流量"
echo '   curl http://localhost:8000/api/users -H "x-pressure-test: true"'
echo ""
echo "3. 查看 PyLinkAgent 状态:"
echo '   curl http://localhost:8000/pylinkagent/status'
echo ""
echo "4. 查看影子库配置:"
echo '   curl http://localhost:8000/pylinkagent/config'
echo ""
echo "5. 查看验证日志:"
echo "   cat verify_result.txt"
echo ""
echo "============================================================"
echo "验证完成！"
echo "============================================================"

exit $VERIFY_RESULT
