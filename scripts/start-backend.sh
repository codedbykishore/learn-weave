#!/bin/bash
# ============================================
# LearnWeave - Start Backend Script
# ============================================

echo "========================================"
echo "  Starting Backend Server"
echo "========================================"
echo ""

# Navigate to backend directory
cd "$(dirname "$0")/../backend" || exit 1

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "✗ .env file not found!"
    echo "  Create it from: cp .env.example .env"
    exit 1
fi

# Check if ChromaDB is running
if ! sudo docker ps --format '{{.Names}}' 2>/dev/null | grep -q "learnweave-chromadb"; then
    echo "⚠ Warning: ChromaDB is not running"
    echo "  Start it with: ./scripts/start-chromadb.sh"
    echo ""
fi

# Check if MySQL is running
if ! systemctl is-active --quiet mysqld; then
    echo "⚠ Warning: MySQL is not running"
    echo "  Start it with: sudo systemctl start mysqld"
    echo ""
fi

# Check if port 8000 is already in use
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠ Port 8000 is already in use!"
    echo "  Stop existing backend with: pkill -f 'uvicorn src.main:app'"
    exit 1
fi

echo "Starting FastAPI backend server..."
echo ""
echo "Backend will be available at:"
echo "  • API:          http://localhost:8000"
echo "  • Docs:         http://localhost:8000/api/docs"
echo "  • Interactive:  http://localhost:8000/api/redoc"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""
echo "----------------------------------------"
echo ""

# Start the backend
python3 -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
