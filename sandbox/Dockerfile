FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY pylinkagent/ ./pylinkagent/
COPY test_shadow_app.py .
COPY demo_app.py .

# 设置环境变量
ENV PYLINKAGENT_ENABLED=true
ENV PYLINKAGENT_LOG_LEVEL=INFO

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["python", "demo_app.py"]
