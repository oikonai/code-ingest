# Code Ingestion System - Multi-Language Vector Database Pipeline
# Comprehensive Makefile for ingestion capabilities

.PHONY: help install deps setup venv sync test clean ingest ingest-warmup ingest-search vector-status index-check clone-repos clone-repos-medium clone-repos-all collection-cleanup collection-status repo-metadata stats-report health check-env status info

# Colors for better readability
YELLOW := \033[33m
GREEN := \033[32m
BLUE := \033[34m
RED := \033[31m
RESET := \033[0m

help:
	@echo "$(GREEN)Code Ingestion System - Available Commands:$(RESET)"
	@echo ""
	@echo "$(BLUE)🏗️  Setup & Installation:$(RESET)"
	@echo "  make venv             Create virtual environment using uv"
	@echo "  make install          Install Python dependencies (creates venv if needed)"
	@echo "  make sync             Sync dependencies with uv (faster than install)"
	@echo "  make setup            Complete system setup (venv + install + check environment)"
	@echo "  make check-env        Verify environment variables and credentials"
	@echo ""
	@echo "$(BLUE)🗄️  Vector Database & Ingestion:$(RESET)"
	@echo "  make ingest           Full ingestion pipeline (Rust + TypeScript + Solidity + YAML + Terraform)"
	@echo "  make ingest-warmup    Warm up embedding service before ingestion"
	@echo "  make ingest-search QUERY='text'  Test vector search functionality"
	@echo "  make vector-status    Check Qdrant collections and vector counts"
	@echo "  make index-check      Check vector indexing progress (after ingestion)"
	@echo ""
	@echo "$(BLUE)📦 Repository Management (Priority-based):$(RESET)"
	@echo "  make clone-repos      Clone high-priority repos only (~10 repos)"
	@echo "  make clone-repos-medium  Clone medium+high priority repos (~16 repos)"
	@echo "  make clone-repos-all  Clone ALL 25 configured repositories"
	@echo "  make collection-cleanup   Clean/recreate all vector collections"
	@echo "  make collection-status    Get detailed collection statistics"
	@echo "  make repo-metadata        Capture repository commit metadata"
	@echo "  make stats-report         Generate comprehensive statistics report"
	@echo ""
	@echo "$(BLUE)⚙️  System Management:$(RESET)"
	@echo "  make health           System health check (ingestion + vector search)"
	@echo "  make test             Run all tests"
	@echo "  make clean            Clean up generated files and caches"
	@echo ""
	@echo "$(YELLOW)Example Usage:$(RESET)"
	@echo "  make ingest"
	@echo "  make ingest-search QUERY='authentication service'"
	@echo "  make health"

# Installation & Setup
venv:
	@echo "$(GREEN)🐍 Creating virtual environment with uv...$(RESET)"
	@if ! command -v uv >/dev/null 2>&1; then \
		echo "$(RED)❌ uv not found. Installing uv...$(RESET)"; \
		curl -LsSf https://astral.sh/uv/install.sh | sh; \
		export PATH="$$HOME/.local/bin:$$PATH"; \
	fi
	@if [ ! -d ".venv" ]; then \
		PATH="$$HOME/.local/bin:$$PATH" uv venv; \
		echo "$(GREEN)✅ Virtual environment created at .venv$(RESET)"; \
		echo "$(YELLOW)💡 Activate with: source .venv/bin/activate$(RESET)"; \
	else \
		echo "$(YELLOW)⚠️  Virtual environment already exists at .venv$(RESET)"; \
	fi

install: venv
	@echo "$(GREEN)📦 Installing Python dependencies with uv...$(RESET)"
	@if [ ! -f ".venv/bin/python" ] && [ ! -f ".venv/Scripts/python.exe" ]; then \
		echo "$(RED)❌ Virtual environment not found. Run 'make venv' first.$(RESET)"; \
		exit 1; \
	fi
	@PATH="$$HOME/.local/bin:$$PATH" uv pip install -r requirements.txt
	@echo "$(GREEN)✅ Dependencies installed$(RESET)"

sync: venv
	@echo "$(GREEN)⚡ Syncing dependencies with uv (fast mode)...$(RESET)"
	@PATH="$$HOME/.local/bin:$$PATH" uv pip sync requirements.txt
	@echo "$(GREEN)✅ Dependencies synced$(RESET)"

deps: install

setup: venv install check-env
	@echo "$(GREEN)🎉 Ingestion system setup complete!$(RESET)"
	@echo "$(YELLOW)💡 Remember to activate your virtual environment:$(RESET)"
	@echo "$(YELLOW)   source .venv/bin/activate$(RESET)"

check-env:
	@echo "$(BLUE)🔍 Checking environment configuration...$(RESET)"
	@python -c "import os; from dotenv import load_dotenv; load_dotenv(); \
	required = ['QDRANT_URL', 'QDRANT_API_KEY', 'DEEPINFRA_API_KEY']; \
	optional = ['EMBEDDING_MODEL', 'GITHUB_TOKEN']; \
	missing = [k for k in required if not os.getenv(k)]; \
	missing_opt = [k for k in optional if not os.getenv(k)]; \
	print('✅ All required environment variables set' if not missing else f'❌ Missing required: {missing}'); \
	print(f'⚠️  Optional variables not set: {missing_opt}' if missing_opt else '✅ All optional variables set'); \
	exit(1 if missing else 0)"

# Vector Database & Ingestion
ingest:
	@echo "$(GREEN)🔄 Running full multi-language ingestion pipeline...$(RESET)"
	@python -c "from modules import IngestionPipeline; import sys, os; pipeline = IngestionPipeline(); priority = os.getenv('PRIORITY'); stats = pipeline.ingest_repositories(min_priority=priority); sys.exit(0 if 'error' not in stats else 1)"
	@echo "$(GREEN)✅ Ingestion complete$(RESET)"

ingest-warmup:
	@echo "$(GREEN)🔥 Warming up embedding service...$(RESET)"
	@python -c "from modules import IngestionPipeline; import sys; pipeline = IngestionPipeline(skip_vector_init=True); success = pipeline.warmup_services(skip_vector_setup=True); sys.exit(0 if success else 1)"
	@echo "$(GREEN)✅ Embedding service warmed up$(RESET)"

ingest-search:
	@if [ -z "$(QUERY)" ]; then \
		echo "$(RED)❌ Please provide a QUERY parameter$(RESET)"; \
		echo "$(YELLOW)Usage: make ingest-search QUERY='authentication service'$(RESET)"; \
		exit 1; \
	fi
	@echo "$(GREEN)🔍 Searching for: $(QUERY)$(RESET)"
	@python modules/ingest/scripts/search_test.py --query "$(QUERY)" --limit 10

vector-status:
	@echo "$(BLUE)📊 Vector Database Quality Analysis...$(RESET)"
	@python modules/ingest/scripts/collection_manager.py status

index-check:
	@echo "$(BLUE)📊 Checking vector indexing progress...$(RESET)"
	@python modules/ingest/scripts/collection_manager.py status --format text | grep -A 20 "Vector Database Status"

# Repository and collection management targets
clone-repos:
	@echo "$(GREEN)🔄 Cloning high-priority repositories...$(RESET)"
	@python modules/ingest/scripts/repo_cloner.py --min-priority high

clone-repos-medium:
	@echo "$(GREEN)🔄 Cloning medium+ priority repositories...$(RESET)"
	@python modules/ingest/scripts/repo_cloner.py --min-priority medium

clone-repos-all:
	@echo "$(GREEN)🔄 Cloning ALL configured repositories...$(RESET)"
	@python modules/ingest/scripts/repo_cloner.py --min-priority ALL

collection-cleanup:
	@echo "$(YELLOW)🗑️  Cleaning all vector collections...$(RESET)"
	@python modules/ingest/scripts/collection_manager.py cleanup

collection-status:
	@echo "$(BLUE)📊 Vector collection status...$(RESET)"
	@python modules/ingest/scripts/collection_manager.py status --format text

repo-metadata:
	@echo "$(BLUE)📝 Capturing repository metadata...$(RESET)"
	@python modules/ingest/scripts/repo_metadata.py capture --format text

stats-report:
	@echo "$(BLUE)📊 Generating statistics report...$(RESET)"
	@python modules/ingest/scripts/stats_reporter.py --format markdown

# System Management
health:
	@echo "$(BLUE)🩺 Ingestion System Health Check...$(RESET)"
	@python -c "from modules import IngestionPipeline; \
	import sys; \
	try: \
		pipeline = IngestionPipeline(); \
		print('\\n📊 System Health:'); \
		print('  ✅ IngestionPipeline initialized'); \
		print('  ✅ Qdrant connection available'); \
		print('  ✅ Embedding service configured'); \
		sys.exit(0); \
	except Exception as e: \
		print(f'\\n❌ Health check failed: {e}'); \
		sys.exit(1)"

test:
	@echo "$(BLUE)🧪 Running tests...$(RESET)"
	@python -c "from modules import IngestionPipeline; \
	print('✅ Basic import test passed'); \
	pipeline = IngestionPipeline(); \
	print('✅ Pipeline initialization test passed')"

clean:
	@echo "$(YELLOW)🧹 Cleaning up generated files...$(RESET)"
	@rm -f ingestion_checkpoint.json
	@rm -rf __pycache__/ */__pycache__/ */*/__pycache__/
	@rm -rf *.cache
	@echo "$(GREEN)✅ Cleanup complete$(RESET)"

# Utility targets
.PHONY: status info
status: vector-status health

info:
	@echo "$(GREEN)Code Ingestion System$(RESET)"
	@echo "$(BLUE)Multi-Language Vector Database Pipeline$(RESET)"
	@echo ""
	@echo "Features:"
	@echo "  📂 GitHub repository cloning"
	@echo "  🔍 Multi-language parsing (Rust, TypeScript, Solidity, Documentation)"
	@echo "  🧠 Semantic embeddings via DeepInfra"
	@echo "  💾 Qdrant vector database storage"
	@echo "  🔎 Cross-language semantic search"
	@echo "  📊 Comprehensive statistics and monitoring"
