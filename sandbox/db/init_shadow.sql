-- PyLinkAgent 影子库功能 - 影子数据库初始化脚本

-- 创建影子用户表
CREATE TABLE IF NOT EXISTS shadow_users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 创建影子订单表
CREATE TABLE IF NOT EXISTS shadow_orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    total DECIMAL(10, 2) NOT NULL,
    status VARCHAR(50) DEFAULT 'shadow_pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES shadow_users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 创建影子商品表
CREATE TABLE IF NOT EXISTS shadow_products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    stock INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 插入影子测试数据 (与业务库数据区分)
INSERT INTO shadow_users (name, email) VALUES
    ('影子用户 1', 'shadow_user1@test.com'),
    ('影子用户 2', 'shadow_user2@test.com'),
    ('影子用户 3', 'shadow_user3@test.com'),
    ('影子用户 4', 'shadow_user4@test.com'),
    ('影子用户 5', 'shadow_user5@test.com');

INSERT INTO shadow_orders (user_id, total, status) VALUES
    (1, 999.99, 'shadow_completed'),
    (1, 1999.99, 'shadow_pending'),
    (2, 2999.99, 'shadow_shipped'),
    (3, 3999.99, 'shadow_completed'),
    (4, 4999.99, 'shadow_pending');

INSERT INTO shadow_products (name, price, stock) VALUES
    ('影子 iPhone 15 Pro', 9999.00, 10),
    ('影子 MacBook Pro 14', 19999.00, 5),
    ('影子 AirPods Pro', 2899.00, 20),
    ('影子 iPad Air', 6799.00, 8),
    ('影子 Apple Watch', 4199.00, 15);

-- 创建影子视图
CREATE OR REPLACE VIEW shadow_user_orders_view AS
SELECT
    u.id as user_id,
    u.name as user_name,
    u.email,
    o.id as order_id,
    o.total,
    o.status
FROM shadow_users u
LEFT JOIN shadow_orders o ON u.id = o.user_id;

-- 显示创建的表
SHOW TABLES;
SELECT 'Shadow Users:' as '', COUNT(*) as COUNT FROM shadow_users;
SELECT 'Shadow Orders:' as '', COUNT(*) as COUNT FROM shadow_orders;
SELECT 'Shadow Products:' as '', COUNT(*) as COUNT FROM shadow_products;
