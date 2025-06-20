#!/bin/bash

# ItemRadar Development Startup Script

echo "🚀 Starting ItemRadar Development Environment..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3 first."
    exit 1
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js first."
    exit 1
fi

# Install Python dependencies if requirements.txt exists
if [ -f "requirements.txt" ]; then
    echo "📦 Installing Python dependencies..."
    pip3 install -r requirements.txt
fi

# Install frontend dependencies if package.json exists
if [ -f "frontend/package.json" ]; then
    echo "📦 Installing frontend dependencies..."
    cd frontend
    npm install
    cd ..
fi

# Start the API server in the background
echo "🔧 Starting API server on http://localhost:8000..."
python3 run_api.py &
API_PID=$!

# Wait a moment for the API to start
sleep 3

# Start the frontend development server
echo "🌐 Starting frontend on http://localhost:9002..."
cd frontend
npm run dev &
FRONTEND_PID=$!

# Function to cleanup on exit
cleanup() {
    echo "🛑 Shutting down servers..."
    kill $API_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

echo "✅ Development environment started!"
echo "📱 Frontend: http://localhost:9002"
echo "🔧 API: http://localhost:8000"
echo "📚 API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all servers"

# Wait for both processes
wait 