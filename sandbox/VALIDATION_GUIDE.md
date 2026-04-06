# PyLinkAgent 沙箱环境验证指南

本指南介绍如何在沙箱环境中完整验证 PyLinkAgent 的影子库功能。

---

## 📋 目录

1. [环境准备](#1-环境准备)
2. [启动沙箱环境](#2-启动沙箱环境)
3. [验证影子库功能](#3-验证影子库功能)
4. [自动化测试](#4-自动化测试)
5. [故障排查](#5-故障排查)

---

## 1. 环境准备

### 1.1 系统要求

| 组件 | 版本 | 检查命令 |
|------|------|----------|
| Docker | 20.10+ | `docker --version` |
| Docker Compose | 2.0+ | `docker-compose --version` |
| Python | 3.8+ | `python --version` |

### 1.2 项目结构

```
PyLinkAgent/
├── sandbox/                    # 沙箱环境目录
│   ├── docker-compose.yml      # Docker Compose 配置
│   ├── Dockerfile              # 应用镜像
│   ├── Dockerfile.test         # 测试镜像
│   ├── db/                     # 数据库初始化脚本
│   │   ├── init.sql            # 业务库初始化
│   │   └── init_shadow.sql     # 影子库初始化
│   └── README.md               # 沙箱说明
├── demo_app.py                 # Demo 应用
├── test_shadow_runner.py       # 自动化测试脚本
└── pylinkagent/                # PyLinkAgent 核心包
```

---

## 2. 启动沙箱环境

### 方式一：Docker Compose（推荐）

一键启动所有服务：

```bash
cd PyLinkAgent/sandbox

# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f demo-app
```

### 服务说明

| 服务名 | 端口 | 说明 |
|--------|------|------|
| `mysql-business` | 3306 | 业务数据库 |
| `mysql-shadow` | 3307 | 影子数据库 |
| `redis-shadow` | 6380 | 影子 Redis（可选） |
| `demo-app` | 8000 | Demo 应用 |
| `test-runner` | - | 自动化测试 |

### 方式二：本地启动

如果没有 Docker，可以本地启动：

```bash
# 1. 安装依赖
pip install -r requirements.txt
pip install -r requirements-test.txt

# 2. 启动 Demo 应用
python demo_app.py

# 3. 在另一个终端运行测试
python test_shadow_runner.py
```

---

## 3. 验证影子库功能

### 3.1 健康检查

```bash
curl http://localhost:8000/health
```

预期响应：
```json
{
  "status": "healthy",
  "service": "pylinkagent-demo",
  "shadow_db_support": true
}
```

### 3.2 正常流量测试

```bash
# 获取用户列表（业务库数据）
curl http://localhost:8000/api/users

# 获取用户详情
curl http://localhost:8000/api/users/1

# 获取订单列表
curl http://localhost:8000/api/orders

# 获取商品列表
curl http://localhost:8000/api/products
```

### 3.3 压测流量测试

添加 `x-pressure-test: true` Header：

```bash
# 获取影子用户列表
curl -H "x-pressure-test: true" http://localhost:8000/api/users

# 获取影子用户详情
curl -H "x-pressure-test: true" http://localhost:8000/api/users/1

# 获取影子订单列表
curl -H "x-pressure-test: true" http://localhost:8000/api/orders

# 获取影子商品列表
curl -H "x-pressure-test: true" http://localhost:8000/api/products
```

### 3.4 链路调用测试

```bash
# 正常链路调用
curl http://localhost:8000/api/chain/1

# 压测链路调用
curl -H "x-pressure-test: true" http://localhost:8000/api/chain/1
```

### 3.5 SQL 重写测试

```bash
# 正常 SQL（不重写）
curl "http://localhost:8000/api/sql/rewrite?sql=SELECT * FROM users"

# 压测 SQL（重写表名）
curl -H "x-pressure-test: true" "http://localhost:8000/api/sql/rewrite?sql=SELECT * FROM users"
```

### 3.6 注册影子库配置

```bash
curl -X POST http://localhost:8000/shadow/config \
  -H "Content-Type: application/json" \
  -d '{
    "ds_type": 0,
    "url": "jdbc:mysql://localhost:3306/test",
    "username": "root",
    "shadow_url": "jdbc:mysql://localhost:3307/shadow_test",
    "shadow_username": "PT_root",
    "business_shadow_tables": {
      "users": "shadow_users",
      "orders": "shadow_orders",
      "products": "shadow_products"
    }
  }'
```

### 3.7 查看影子库状态

```bash
curl http://localhost:8000/shadow/status
```

---

## 4. 自动化测试

### 4.1 运行测试脚本

```bash
cd PyLinkAgent/sandbox

# 确保 Demo 应用已启动
# 方式 1：docker-compose up -d demo-app
# 方式 2：python ../demo_app.py

# 运行自动化测试
python ../test_shadow_runner.py
```

### 4.2 测试覆盖

| 测试类别 | 测试项 | 说明 |
|----------|--------|------|
| 配置管理 | 影子库配置注册 | 动态注册配置 |
| 流量染色 | 正常/压测用户请求 | Header 识别 |
| 影子路由 | 正常/压测订单请求 | 影子库路由 |
| 链路追踪 | 正常/压测链路调用 | 多级调用 |
| SQL 重写 | 正常/压测 SQL | 表名替换 |
| 状态检查 | 数据库状态、配置查询 | 状态监控 |

### 4.3 Docker 中运行测试

```bash
# 运行测试容器
docker-compose up test-runner

# 查看测试结果
docker-compose logs test-runner
```

---

## 5. 故障排查

### 5.1 服务无法启动

```bash
# 检查 Docker 容器状态
docker-compose ps

# 查看错误日志
docker-compose logs demo-app
docker-compose logs mysql-business
docker-compose logs mysql-shadow
```

### 5.2 数据库连接失败

```bash
# 测试数据库连接
docker exec -it pylinkagent-mysql-business mysql -uroot -proot123 -e "SHOW TABLES;"
docker exec -it pylinkagent-mysql-shadow mysql -uroot -proot123 -e "SHOW TABLES;"
```

### 5.3 端口冲突

如果端口被占用，修改 `docker-compose.yml`：

```yaml
ports:
  - "8001:8000"  # 改为其他端口
```

### 5.4 测试失败

```bash
# 检查应用日志
docker-compose logs -f demo-app

# 手动测试 API
curl -v http://localhost:8000/health

# 检查测试脚本输出
python ../test_shadow_runner.py 2>&1 | tee test-output.log
```

---

## 6. 验证清单

完成以下检查确认沙箱环境正常：

- [ ] Docker 容器全部运行（`docker-compose ps` 显示 Up）
- [ ] 健康检查接口返回正常（`/health` 返回 200）
- [ ] 正常流量返回业务库数据
- [ ] 压测流量返回影子库数据
- [ ] 链路调用显示正确的表路由
- [ ] SQL 重写功能正常
- [ ] 自动化测试全部通过

---

## 7. 清理环境

```bash
# 停止所有服务
docker-compose down

# 停止服务并删除数据卷
docker-compose down -v

# 删除所有相关镜像
docker-compose down --rmi all
```

---

## 8. 相关文档

- [Demo 应用说明](README.md)
- [影子库实现总结](../SHADOW_DB_IMPLEMENTATION_SUMMARY.md)
- [影子库验证报告](../SHADOW_DB_VERIFICATION_REPORT.md)

---

**验证指南版本**: v1.0.0  
**最后更新**: 2026-04-07
