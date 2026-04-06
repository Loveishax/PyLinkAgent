# PyLinkAgent 沙箱环境

全链路压测影子库功能的完整沙箱验证环境。

## 📦 环境组件

| 组件 | 端口 | 说明 |
|------|------|------|
| MySQL (业务库) | 3306 | 业务数据存储 |
| MySQL (影子库) | 3307 | 影子数据存储 |
| Redis (影子) | 6380 | 影子 Redis（可选） |
| Demo 应用 | 8000 | 演示应用 |
| 测试 runner | - | 自动化测试 |

## 🚀 快速开始

### 启动沙箱环境

```bash
cd sandbox

# 启动所有服务
docker-compose up -d

# 查看状态
docker-compose ps

# 查看日志
docker-compose logs -f demo-app
```

### 验证功能

```bash
# 健康检查
curl http://localhost:8000/health

# 正常流量（业务库数据）
curl http://localhost:8000/api/users/1

# 压测流量（影子库数据）
curl -H "x-pressure-test: true" http://localhost:8000/api/users/1
```

### 运行自动化测试

```bash
# 确保服务已启动
docker-compose up -d

# 运行测试
python ../test_shadow_runner.py
```

## 📁 目录结构

```
sandbox/
├── docker-compose.yml       # Docker Compose 配置
├── Dockerfile               # 应用镜像
├── Dockerfile.test          # 测试镜像
├── db/
│   ├── init.sql             # 业务库初始化
│   └── init_shadow.sql      # 影子库初始化
├── README.md                # 沙箱说明
└── VALIDATION_GUIDE.md      # 验证指南
```

## 🔧 配置说明

### 影子库表映射

| 业务表 | 影子表 |
|--------|--------|
| users | shadow_users |
| orders | shadow_orders |
| products | shadow_products |

### 压测流量标识

在请求 Header 中添加：
```
x-pressure-test: true
```

### 数据库连接

**业务库:**
```
Host: localhost:3306
Database: test
User: app_user
Password: app_password
```

**影子库:**
```
Host: localhost:3307
Database: shadow_test
User: PT_app_user
Password: PT_app_password
```

## 📖 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 应用首页 |
| `/health` | GET | 健康检查 |
| `/api/users` | GET | 用户列表 |
| `/api/users/{id}` | GET | 用户详情 |
| `/api/orders` | GET | 订单列表 |
| `/api/orders/{id}` | GET | 订单详情 |
| `/api/products` | GET | 商品列表 |
| `/api/chain/{id}` | GET | 链路调用 |
| `/api/sql/rewrite` | GET | SQL 重写 |
| `/shadow/config` | POST | 注册配置 |
| `/shadow/status` | GET | 影子库状态 |

## 🧪 测试数据

### 业务库数据

- 用户：张三、李四、王五、赵六、钱七
- 订单：5 个测试订单
- 商品：iPhone、MacBook、AirPods 等

### 影子库数据

- 影子用户：影子用户 1-5
- 影子订单：金额为业务库的 10 倍
- 影子商品：名称带"影子"前缀，价格更高

## 🛠️ 故障排查

```bash
# 查看容器状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 重启服务
docker-compose restart demo-app

# 清理并重启
docker-compose down && docker-compose up -d
```

## 📚 相关文档

- [验证指南](VALIDATION_GUIDE.md) - 完整验证步骤
- [影子库实现总结](../SHADOW_DB_IMPLEMENTATION_SUMMARY.md)
- [影子库验证报告](../SHADOW_DB_VERIFICATION_REPORT.md)

---

**版本**: v1.0.0  
**最后更新**: 2026-04-07
