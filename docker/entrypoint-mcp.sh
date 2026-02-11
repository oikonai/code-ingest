#!/bin/bash
set -e

echo "=================================================="
echo "MCP Server"
echo "=================================================="

# Wait for Qdrant to be ready
echo "⏳ Waiting for Qdrant..."
max_attempts=30
attempt=0

# Determine Qdrant URL (default to local Docker, or use cloud URL)
QDRANT_CHECK_URL="${QDRANT_URL:-http://qdrant:6333}"

while [ $attempt -lt $max_attempts ]; do
    if curl -sf "${QDRANT_CHECK_URL}/" > /dev/null 2>&1; then
        echo "✅ Qdrant is ready"
        break
    fi
    attempt=$((attempt + 1))
    echo "   Attempt $attempt/$max_attempts - waiting 2s..."
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo "⚠️  Qdrant did not become healthy - continuing anyway"
fi

# Start MCP server with health endpoint
echo "🚀 Starting MCP server..."
cd /app/mcp
exec python server.py
