# PyLinkAgent Makefile

.PHONY: all install dev test lint format build clean publish

# 默认目标
all: install dev test

# 安装依赖
install:
	pip install -r requirements.txt
	pip install -e .

# 开发环境设置
dev:
	pip install -r requirements-dev.txt
	pre-commit install

# 运行测试
test:
	pytest tests/ -v --cov=pylinkagent --cov-report=html

# 运行集成测试
test-integration:
	pytest tests/integration/ -v

# 运行性能测试
test-benchmark:
	pytest tests/benchmark/ -v

# 代码检查
lint:
	flake8 pylinkagent/ simulator_agent/ instrument_simulator/ instrument_modules/
	mypy pylinkagent/ simulator_agent/ instrument_simulator/
	pylint pylinkagent/ simulator_agent/ instrument_simulator/

# 代码格式化
format:
	black pylinkagent/ simulator_agent/ instrument_simulator/ instrument_modules/
	isort pylinkagent/ simulator_agent/ instrument_simulator/ instrument_modules/

# 构建分发包
build:
	python -m build

# 清理
clean:
	rm -rf dist/ build/ *.egg-info
	rm -rf .pytest_cache/ .mypy_cache/ .coverage htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# 发布到 PyPI
publish: clean build
	twine upload dist/*

# 发布测试
publish-test: clean build
	twine upload --repository testpypi dist/*

# 生成文档
docs:
	mkdocs build

# 本地预览文档
docs-serve:
	mkdocs serve

# 检查依赖
check-deps:
	pip-review --local --auto

# 更新依赖
update-deps:
	pip-review --local --interactive
