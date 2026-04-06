-- PyLinkAgent 影子库功能 - 业务数据库初始化脚本

-- 创建用户表
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 创建订单表
CREATE TABLE IF NOT EXISTS orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    total DECIMAL(10, 2) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 创建商品表
CREATE TABLE IF NOT EXISTS products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    stock INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 插入测试数据
INSERT INTO users (name, email) VALUES
    ('张三', 'zhangsan@example.com'),
    ('李四', 'lisi@example.com'),
    ('王五', 'wangwu@example.com'),
    ('赵六', 'zhaoliu@example.com'),
    ('钱七', 'qianqi@example.com');

INSERT INTO orders (user_id, total, status) VALUES
    (1, 99.99, 'completed'),
    (1, 199.99, 'pending'),
    (2, 299.99, 'shipped'),
    (3, 399.99, 'completed'),
    (4, 499.99, 'pending');

INSERT INTO products (name, price, stock) VALUES
    ('iPhone 15 Pro', 7999.00, 100),
    ('MacBook Pro 14', 14999.00, 50),
    ('AirPods Pro', 1899.00, 200),
    ('iPad Air', 4799.00, 80),
    ('Apple Watch', 3199.00, 150);

-- 创建视图（用于复杂查询测试）
CREATE OR REPLACE VIEW user_orders_view AS
SELECT
    u.id as user_id,
    u.name as user_name,
    u.email,
    o.id as order_id,
    o.total,
    o.status
FROM users u
LEFT JOIN orders o ON u.id = o.user_id;

-- 显示创建的表
SHOW TABLES;
SELECT 'Users:' as '', COUNT(*) as COUNT FROM users;
SELECT 'Orders:' as '', COUNT(*) as COUNT FROM orders;
SELECT 'Products:' as '', COUNT(*) as COUNT FROM products;
