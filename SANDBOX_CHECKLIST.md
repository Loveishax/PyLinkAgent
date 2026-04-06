# PyLinkAgent 沙箱环境验证清单

## 📋 验证目标

在沙箱环境中完整验证 PyLinkAgent 的影子库功能，确保可用于全链路压测场景。

---

## ✅ 环境组件清单

### 已创建的文件

| 文件 | 路径 | 用途 | 状态 |
|------|------|------|------|
| Docker Compose | `sandbox/docker-compose.yml` | 编排所有服务 | ✅ |
| Dockerfile | `sandbox/Dockerfile` | 应用镜像 | ✅ |
| Dockerfile.test | `sandbox/Dockerfile.test` | 测试镜像 | ✅ |
| 业务库初始化 | `sandbox/db/init.sql` | 创建业务表和数据 | ✅ |
| 影子库初始化 | `sandbox/db/init_shadow.sql` | 创建影子表和数据 | ✅ |
| Demo 应用 | `demo_app.py` | 完整演示应用 | ✅ |
| 测试脚本 | `test_shadow_runner.py` | 自动化测试 | ✅ |
| 验证指南 | `sandbox/VALIDATION_GUIDE.md` | 完整验证步骤 | ✅ |
| 沙箱说明 | `sandbox/README.md` | 沙箱环境说明 | ✅ |

### 服务组件

| 服务 | 镜像 | 端口 | 状态 |
|------|------|------|------|
| MySQL (业务库) | mysql:8.0 | 3306 | ✅ |
| MySQL (影子库) | mysql:8.0 | 3307 | ✅ |
| Redis (影子) | redis:7-alpine | 6380 | ✅ |
| Demo 应用 | pylinkagent-demo | 8000 | ✅ |
| 测试 Runner | pylinkagent-test | - | ✅ |

---

## 🎯 验证项目

### 1. 流量染色识别

**目标**: 验证通过 Header 识别压测流量

**测试用例**:
- [ ] 正常流量无 Header → 业务库数据
- [ ] 压测流量 `x-pressure-test: true` → 影子库数据
- [ ] 压测流量 `x-shadow-flag: xxx` → 影子库数据

**验证命令**:
```bash
# 正常流量
curl http://localhost:8000/api/users/1
# 预期：{"id": 1, "name": "张三", ...}

# 压测流量
curl -H "x-pressure-test: true" http://localhost:8000/api/users/1
# 预期：{"id": 1, "name": "影子用户 1", "is_shadow": true}
```

---

### 2. 影子库路由

**目标**: 验证压测流量自动路由到影子库

**测试用例**:
- [ ] 用户查询路由
- [ ] 订单查询路由
- [ ] 商品查询路由
- [ ] 链路调用路由

**验证命令**:
```bash
curl -H "x-pressure-test: true" http://localhost:8000/api/chain/1
# 预期：routing.user_table = "shadow_users"
# 预期：routing.order_table = "shadow_orders"
```

---

### 3. 影子表映射

**目标**: 验证业务表名自动映射到影子表名

**表映射关系**:
| 业务表 | 影子表 |
|--------|--------|
| users | shadow_users |
| orders | shadow_orders |
| products | shadow_products |

**验证命令**:
```bash
curl -H "x-pressure-test: true" http://localhost:8000/api/sql/rewrite?sql=SELECT+*+FROM+users
# 预期：rewritten_sql = "SELECT * FROM shadow_users"
```

---

### 4. SQL 重写

**目标**: 验证压测流量下 SQL 语句自动重写

**测试用例**:
- [ ] 正常流量 SQL 不重写
- [ ] 压测流量 SQL 表名替换
- [ ] 多表查询重写

**验证命令**:
```bash
# 正常 SQL
curl "http://localhost:8000/api/sql/rewrite?sql=SELECT+*+FROM+users"
# 预期：rewritten_sql = "SELECT * FROM users"

# 压测 SQL
curl -H "x-pressure-test: true" "http://localhost:8000/api/sql/rewrite?sql=SELECT+*+FROM+users"
# 预期：rewritten_sql = "SELECT * FROM shadow_users"
```

---

### 5. 配置管理

**目标**: 验证影子库配置的动态注册和查询

**测试用例**:
- [ ] 注册影子库配置
- [ ] 查询影子库状态
- [ ] 配置持久化（可选）

**验证命令**:
```bash
# 注册配置
curl -X POST http://localhost:8000/shadow/config \
  -H "Content-Type: application/json" \
  -d '{"ds_type": 0, "url": "jdbc:mysql://localhost:3306/test", "shadow_url": "jdbc:mysql://localhost:3307/shadow_test", "business_shadow_tables": {"users": "shadow_users"}}'

# 查询状态
curl http://localhost:8000/shadow/status
```

---

## 🧪 自动化测试

### 运行测试

```bash
cd sandbox

# 启动环境
docker-compose up -d

# 等待服务就绪
sleep 30

# 运行测试
python ../test_shadow_runner.py
```

### 测试覆盖率

| 类别 | 测试项 | 通过率目标 | 实际 |
|------|--------|------------|------|
| 配置管理 | 1 | 100% | - |
| 流量染色 | 4 | 100% | - |
| 影子路由 | 3 | 100% | - |
| SQL 重写 | 2 | 100% | - |
| 状态检查 | 3 | 100% | - |
| **总计** | **13** | **100%** | **-** |

---

## 📊 验证报告

完成验证后生成报告，包含：

1. **测试概览**: 通过率、总耗时
2. **详细结果**: 每个测试项的状态
3. **功能验证状态**: 各功能模块验证情况
4. **问题记录**: 发现的问题和解决方案

---

## 🔧 故障排查

### 常见问题

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| 容器无法启动 | 端口冲突 | 修改 docker-compose.yml 端口 |
| 数据库连接失败 | 服务未就绪 | 等待 healthcheck 通过 |
| 测试失败 | 应用未启动 | 检查 demo-app 日志 |

### 日志查看

```bash
# 查看所有服务日志
docker-compose logs -f

# 查看应用日志
docker-compose logs -f demo-app

# 查看数据库日志
docker-compose logs -f mysql-business
docker-compose logs -f mysql-shadow
```

---

## ✅ 验收标准

完成以下检查确认验证通过：

- [ ] 所有 Docker 容器正常运行
- [ ] 健康检查接口返回 200
- [ ] 正常流量返回业务库数据
- [ ] 压测流量返回影子库数据
- [ ] 链路调用显示正确的表路由
- [ ] SQL 重写功能正常
- [ ] 自动化测试通过率 100%
- [ ] 无严重错误日志

---

## 📚 相关文档

- [沙箱验证指南](sandbox/VALIDATION_GUIDE.md) - 完整验证步骤
- [影子库实现总结](SHADOW_DB_IMPLEMENTATION_SUMMARY.md) - 技术实现细节
- [影子库验证报告](SHADOW_DB_VERIFICATION_REPORT.md) - 验证结果报告

---

**版本**: v1.0.0  
**创建日期**: 2026-04-07
