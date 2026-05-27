.PHONY: install install-frontend install-backend frontend backend chroma host kill help

help:
	@echo "LearnWeave - Available commands:"
	@echo ""
	@echo "  make install             Install all dependencies"
	@echo "  make install-frontend    Install frontend npm dependencies"
	@echo "  make install-backend     Install backend Python dependencies"
	@echo "  make chroma              Start ChromaDB vector database (Docker)"
	@echo "  make frontend            Start frontend dev server (port 3000)"
	@echo "  make backend             Start backend server (port 8000)"
	@echo "  make host                Start both servers + public URL (ngrok)"
	@echo "  make kill                Stop all services"

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

host:
	@echo "==> Checking prerequisites..."
	@if [ ! -f "backend/.env" ]; then echo "ERROR: backend/.env not found!"; exit 1; fi
	@if [ ! -d "backend/venv" ]; then echo "ERROR: Virtual environment not found! Run: make install-backend"; exit 1; fi
	@command -v ngrok >/dev/null 2>&1 || { echo "ERROR: ngrok not found! Install it first."; exit 1; }
	@echo "==> Killing any existing processes..."
	@kill -9 $$(lsof -t -i:3000 -i:8000 -i:4040) 2>/dev/null; sleep 1
	@echo "==> Starting backend on :8000 ..."
	@cd backend && setsid ./venv/bin/python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8000 > /tmp/backend-host.log 2>&1 &
	@sleep 3
	@echo "==> Starting frontend on :3000 ..."
	@cd frontend && setsid npm run dev > /tmp/frontend-host.log 2>&1 &
	@sleep 4
	@echo "==> Starting ngrok tunnel to frontend (port 3000)..."
	@setsid ngrok http 3000 --log=stdout > /tmp/ngrok-host.log 2>&1 &
	@sleep 6
	@echo ""
	@echo "================================================"
	@echo "  LEARNWEAVE — PUBLIC URL"
	@echo "================================================"
	@curl -s http://127.0.0.1:4040/api/tunnels 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin)['tunnels'][0]; print('  App:', d['public_url'])" 2>/dev/null || echo "  App: (starting... check http://127.0.0.1:4040)"
	@echo ""
	@echo "  Frontend  -> App URL (serves UI)"
	@echo "  Backend   -> App URL + /api (proxied)"
	@echo "  Inspect   -> http://127.0.0.1:4040"
	@echo "  Stop all  -> make kill"
	@echo "================================================"

kill:
	@echo "==> Stopping all services..."
	@kill -9 $$(lsof -t -i:3000 -i:8000 -i:4040) 2>/dev/null; echo "done"
