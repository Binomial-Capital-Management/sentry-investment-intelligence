# Binomial Risk Analyst V6 - Development Makefile
# Professional-grade linting, testing, and development commands

.PHONY: help install lint lint-py lint-ts format format-py format-ts test test-py test-ts clean build dev prod

# Default target
help:
	@echo "Binomial Risk Analyst V6 - Development Commands"
	@echo "================================================"
	@echo ""
	@echo "🔧 Development Setup:"
	@echo "  install          Install all dependencies (Python + Node.js)"
	@echo "  install-py       Install Python dependencies"
	@echo "  install-ts       Install TypeScript/Node.js dependencies"
	@echo ""
	@echo "✨ Code Quality:"
	@echo "  lint             Run all linters (Python + TypeScript)"
	@echo "  lint-py          Run Python linters (flake8, pylint, mypy, bandit)"
	@echo "  lint-ts          Run TypeScript linter (ESLint)"
	@echo "  format           Format all code (black, isort, prettier)"
	@echo "  format-py        Format Python code (black + isort)"
	@echo "  format-ts        Format TypeScript code (prettier)"
	@echo "  type-check       Run type checking (mypy + tsc)"
	@echo ""
	@echo "🧪 Testing:"
	@echo "  test             Run all tests (Python + TypeScript)"
	@echo "  test-py          Run Python tests (pytest)"
	@echo "  test-ts          Run TypeScript tests (vitest)"
	@echo "  test-coverage    Run tests with coverage reports"
	@echo ""
	@echo "🚀 Application:"
	@echo "  dev              Start development servers (FastAPI + Vite)"
	@echo "  dev-py           Start Python/FastAPI development server"
	@echo "  dev-ts           Start TypeScript/React development server"
	@echo "  build            Build production application"
	@echo "  build-ts         Build frontend for production"
	@echo ""
	@echo "🔒 Security:"
	@echo "  security         Run security scans (bandit + npm audit)"
	@echo "  security-py      Run Python security scan (bandit)"
	@echo "  security-ts      Run Node.js security audit"
	@echo ""
	@echo "🧹 Maintenance:"
	@echo "  clean            Clean build artifacts and caches"
	@echo "  clean-py         Clean Python caches"
	@echo "  clean-ts         Clean Node.js caches"

# =============================================================================
# INSTALLATION
# =============================================================================

install: install-py install-ts
	@echo "✅ All dependencies installed successfully"

install-py:
	@echo "📦 Installing Python dependencies..."
	pip install -e .
	pip install black isort flake8 pylint mypy bandit pytest pytest-cov pytest-asyncio
	@echo "✅ Python dependencies installed"

install-ts:
	@echo "📦 Installing TypeScript dependencies..."
	cd frontend && npm install
	@echo "✅ TypeScript dependencies installed"

# =============================================================================
# CODE QUALITY & LINTING
# =============================================================================

lint: lint-py lint-ts
	@echo "✅ All linting completed"

lint-py:
	@echo "🔍 Running Python linters..."
	@echo "  → flake8 (style + complexity)"
	flake8 core api tests --statistics
	@echo "  → pylint (code quality)"
	pylint core api --rcfile=pyproject.toml || true
	@echo "  → mypy (type checking)"
	mypy core api --config-file=pyproject.toml
	@echo "  → bandit (security)"
	bandit -r core api -f json -o security-report.json || true
	bandit -r core api
	@echo "✅ Python linting completed"

lint-ts:
	@echo "🔍 Running TypeScript linter..."
	cd frontend && npm run lint
	@echo "✅ TypeScript linting completed"

format: format-py format-ts
	@echo "✅ All code formatted"

format-py:
	@echo "🎨 Formatting Python code..."
	@echo "  → isort (import sorting)"
	isort core api tests
	@echo "  → black (code formatting)"
	black core api tests
	@echo "✅ Python code formatted"

format-ts:
	@echo "🎨 Formatting TypeScript code..."
	cd frontend && npx prettier --write "src/**/*.{ts,tsx,js,jsx,css,scss,json}"
	@echo "✅ TypeScript code formatted"

type-check:
	@echo "🔍 Running type checking..."
	@echo "  → mypy (Python)"
	mypy core api --config-file=pyproject.toml
	@echo "  → tsc (TypeScript)"
	cd frontend && npm run type-check
	@echo "✅ Type checking completed"

# =============================================================================
# TESTING
# =============================================================================

test: test-py test-ts
	@echo "✅ All tests completed"

test-py:
	@echo "🧪 Running Python tests..."
	pytest tests/ -v --tb=short
	@echo "✅ Python tests completed"

test-ts:
	@echo "🧪 Running TypeScript tests..."
	cd frontend && npm run test
	@echo "✅ TypeScript tests completed"

test-coverage:
	@echo "🧪 Running tests with coverage..."
	pytest tests/ -v --cov=core --cov=api --cov-report=html --cov-report=term
	@echo "📊 Coverage report generated in htmlcov/"
	@echo "✅ Coverage testing completed"

test-integration:
	@echo "🧪 Running integration tests..."
	pytest tests/ -v -m integration
	@echo "✅ Integration tests completed"

test-unit:
	@echo "🧪 Running unit tests..."
	pytest tests/ -v -m "not integration and not slow"
	@echo "✅ Unit tests completed"

# =============================================================================
# SECURITY
# =============================================================================

security: security-py security-ts
	@echo "✅ Security scans completed"

security-py:
	@echo "🔒 Running Python security scan..."
	bandit -r core api -f json -o security-report.json
	bandit -r core api
	@echo "✅ Python security scan completed"

security-ts:
	@echo "🔒 Running Node.js security audit..."
	cd frontend && npm audit --audit-level=moderate
	@echo "✅ Node.js security audit completed"

# =============================================================================
# DEVELOPMENT
# =============================================================================

dev:
	@echo "🚀 Starting development servers..."
	@echo "  Backend:  http://localhost:8002"
	@echo "  Frontend: http://localhost:3000"
	@echo ""
	@echo "Use Ctrl+C to stop servers"
	@$(MAKE) -j2 dev-py dev-ts

dev-py:
	@echo "🐍 Starting Python/FastAPI development server..."
	python app_fastapi.py

dev-ts:
	@echo "⚛️  Starting TypeScript/React development server..."
	cd frontend && npm run dev

# =============================================================================
# BUILD
# =============================================================================

build: build-ts
	@echo "✅ Production build completed"

build-ts:
	@echo "📦 Building frontend for production..."
	cd frontend && npm run build
	@echo "✅ Frontend build completed"

# =============================================================================
# MAINTENANCE
# =============================================================================

clean: clean-py clean-ts
	@echo "✅ All caches cleaned"

clean-py:
	@echo "🧹 Cleaning Python caches..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ .coverage htmlcov/ .pytest_cache/ .mypy_cache/
	@echo "✅ Python caches cleaned"

clean-ts:
	@echo "🧹 Cleaning TypeScript caches..."
	cd frontend && rm -rf node_modules/.cache/ dist/ .vite/
	@echo "✅ TypeScript caches cleaned"

# =============================================================================
# CI/CD PIPELINE TARGETS
# =============================================================================

ci-lint: lint
	@echo "✅ CI: Linting passed"

ci-test: test
	@echo "✅ CI: Tests passed"

ci-security: security
	@echo "✅ CI: Security checks passed"

ci-build: build
	@echo "✅ CI: Build successful"

ci-all: clean install ci-lint ci-security ci-test ci-build
	@echo "✅ CI: All checks passed"

# =============================================================================
# QUICK COMMANDS
# =============================================================================

# Quick fix - format and lint
fix: format lint
	@echo "✅ Code fixed and validated"

# Pre-commit - run before committing
pre-commit: format lint test-unit
	@echo "✅ Pre-commit checks passed"

# Full quality check
quality: clean install lint type-check security test-coverage
	@echo "✅ Full quality check completed"