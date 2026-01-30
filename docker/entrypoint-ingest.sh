#!/bin/bash
set -e

echo "=================================================="
echo "Code Ingestion Service"
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
    echo "❌ SurrealDB did not become healthy in time"
    exit 1
fi

# Clone repositories if repos directory is empty
if [ ! "$(ls -A /app/repos 2>/dev/null)" ]; then
    echo "📥 Cloning repositories..."
    python -m modules.ingest.scripts.repo_cloner --min-priority "${PRIORITY:-high}"
    echo "✅ Repositories cloned"
else
    echo "✅ Repositories already present"
fi

# Run ingestion
echo "🚀 Starting ingestion pipeline..."
python -c "
from modules import IngestionPipeline
import sys
import os

try:
    pipeline = IngestionPipeline()
    priority = os.getenv('PRIORITY', 'high')
    print(f'📊 Running ingestion with priority: {priority}')
    stats = pipeline.ingest_repositories(min_priority=priority)
    
    if 'error' in stats:
        print(f'❌ Ingestion failed: {stats[\"error\"]}')
        sys.exit(1)
    
    print('✅ Ingestion complete!')
    print(f'   Total chunks: {stats.get(\"total_chunks\", 0)}')
    print(f'   Repositories: {stats.get(\"repositories_processed\", 0)}')
    
    # Write completion status
    with open('/app/status/ingestion_complete', 'w') as f:
        f.write('complete')
    
    sys.exit(0)
except Exception as e:
    print(f'❌ Ingestion failed with exception: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"

echo "=================================================="
echo "Ingestion service completed"
echo "=================================================="
