#!/bin/bash
set -e

echo "=================================================="
echo "MCP Server"
echo "=================================================="

# Wait for SurrealDB to be ready
echo "⏳ Waiting for SurrealDB..."
max_attempts=30
attempt=0

while [ $attempt -lt $max_attempts ]; do
    if curl -sf "${SURREALDB_URL}/health" > /dev/null 2>&1; then
        echo "✅ SurrealDB is ready"
        break
    fi
    attempt=$((attempt + 1))
    echo "   Attempt $attempt/$max_attempts - waiting 2s..."
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo "⚠️  SurrealDB did not become healthy - continuing anyway"
fi

# Start MCP server with health endpoint
echo "🚀 Starting MCP server..."
cd /app/mcp
exec python server.py
