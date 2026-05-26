.PHONY: install install-frontend install-backend frontend backend chroma help

help:
	@echo "LearnWeave - Available commands:"
	@echo ""
	@echo "  make install             Install all dependencies"
	@echo "  make install-frontend    Install frontend npm dependencies"
	@echo "  make install-backend     Install backend Python dependencies"
	@echo "  make chroma              Start ChromaDB vector database (Docker)"
	@echo "  make frontend            Start frontend dev server (port 3000)"
	@echo "  make backend             Start backend server (port 8000)"

install: install-frontend install-backend
	@echo "==> All dependencies installed successfully."

install-frontend:
	@echo "==> Installing frontend dependencies..."
	cd frontend && npm install
	@echo "==> Installing code_checker dependencies..."
	cd backend/src/agents/code_checker && npm install

install-backend:
	@echo "==> Installing backend dependencies..."
	@if [ ! -d "backend/venv" ]; then \
		echo "    Creating Python virtual environment..."; \
		cd backend && python3 -m venv venv --system-site-packages; \
	fi
	cd backend && ./venv/bin/pip install -r requirements.txt

chroma:
	@if ! docker ps &> /dev/null; then \
		echo "ERROR: Docker is not running!"; \
		echo "  Start with: sudo systemctl start docker"; \
		exit 1; \
	fi
	@if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "learnweave-chromadb"; then \
		echo "==> ChromaDB is already running on http://localhost:8001"; \
	else \
		echo "==> Starting ChromaDB via Docker..."; \
		docker run -d --name learnweave-chromadb -p 8001:8000 \
			-e CHROMA_SERVER_CORS_ALLOW_ORIGINS='["*"]' \
			chromadb/chroma:latest; \
	fi

frontend:
	@echo "==> Starting frontend dev server on http://localhost:3000 ..."
	cd frontend && npm run dev

backend:
	@if [ ! -f "backend/.env" ]; then \
		echo "ERROR: backend/.env not found!"; \
		echo "  Copy from backend/.env.example and configure:"; \
		echo "    cp backend/.env.example backend/.env"; \
		exit 1; \
	fi
	@if [ ! -d "backend/venv" ]; then \
		echo "ERROR: Virtual environment not found!"; \
		echo "  Run: make install-backend"; \
		exit 1; \
	fi
	@echo "==> Starting backend server on http://localhost:8000 ..."
	cd backend && ./venv/bin/python3 -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
