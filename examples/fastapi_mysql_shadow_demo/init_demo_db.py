"""
Initialize local MySQL databases for the FastAPI shadow-routing demo.
"""

import pymysql


MYSQL_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "123456",
    "charset": "utf8mb4",
    "autocommit": True,
}

BUSINESS_DB = "pylinkagent_demo_biz"
SHADOW_DB = "pylinkagent_demo_shadow"


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS demo_users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(64) NOT NULL,
    note VARCHAR(128) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


def _exec(sql: str, database: str = None, params=None):
    conn = pymysql.connect(database=database, **MYSQL_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
    finally:
        conn.close()


def _seed_db(database: str, rows):
    _exec(CREATE_TABLE_SQL, database=database)
    _exec("TRUNCATE TABLE demo_users", database=database)
    for name, note in rows:
        _exec(
            "INSERT INTO demo_users(name, note) VALUES (%s, %s)",
            database=database,
            params=(name, note),
        )


def main():
    _exec(f"CREATE DATABASE IF NOT EXISTS {BUSINESS_DB} DEFAULT CHARACTER SET utf8mb4")
    _exec(f"CREATE DATABASE IF NOT EXISTS {SHADOW_DB} DEFAULT CHARACTER SET utf8mb4")

    _seed_db(
        BUSINESS_DB,
        [
            ("biz-alice", "seed-business"),
            ("biz-bob", "seed-business"),
        ],
    )
    _seed_db(
        SHADOW_DB,
        [
            ("shadow-alice", "seed-shadow"),
            ("shadow-bob", "seed-shadow"),
        ],
    )

    print("Initialized demo databases:")
    print(f"  business: {BUSINESS_DB}")
    print(f"  shadow:   {SHADOW_DB}")


if __name__ == "__main__":
    main()
