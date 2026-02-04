# Docker Compose Local Setup

This directory contains Docker Compose configuration for running the code ingestion system locally with SurrealDB as the vector database.

## Architecture

```
┌─────────────┐
│  SurrealDB  │  ← Local vector database
└──────┬──────┘
       │
       ├─────► ┌──────────────┐
       │       │   Ingestion  │  ← One-shot: clone repos, ingest, exit
       │       └──────────────┘
       │
       └─────► ┌──────────────┐
               │  MCP Server  │  ← Query interface with health endpoint
               └──────────────┘
```

## Prerequisites

1. **Docker and Docker Compose** installed
2. **Environment variables** configured:
   - Copy `.env.example` to `.env`
   - Set `VECTOR_BACKEND=surrealdb`
   - Configure embedding service (DeepInfra)
   - Add GitHub token for repository cloning

## Quick Start

1. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env and set:
   # - VECTOR_BACKEND=surrealdb
   # - DEEPINFRA_API_KEY
   # - GITHUB_TOKEN (for cloning repos)
   ```

2. **Start services**:
   ```bash
   docker compose up
   ```

   This will:
   - Start SurrealDB on port 8000
   - Run ingestion (clones repos, ingests code, writes to SurrealDB)
   - Start MCP server on port 8001 with health endpoint

3. **Check health**:
   ```bash
   curl http://localhost:8001/health
   ```

   Response when ready:
   ```json
   {
     "status": "ready",
     "surrealdb": "ok",
     "ingestion": "complete",
     "backend_type": "surrealdb"
   }
   ```

   While ingestion is running:
   ```json
   {
     "status": "waiting_for_ingestion",
     "surrealdb": "ok",
     "ingestion": "pending",
     "backend_type": "surrealdb"
   }
   ```

## Services

### SurrealDB
- **Port**: 8000
- **Data**: Persisted in Docker volume `code-ingest-surrealdb-data`
- **Credentials**: root/root (default)
- **Health**: `http://localhost:8000/health`

### Ingestion
- **Type**: One-shot (restarts: "no")
- **Clones repos** from `config/repositories.yaml`
- **Priority filter**: Set `PRIORITY=high|medium|low` in `.env` (default: high)
- **Status file**: Writes `/app/status/ingestion_complete` when done
- **Logs**: `docker compose logs ingest`

### MCP Server
- **Port**: 8001 (stdio for MCP, HTTP for health)
- **Health endpoint**: `http://localhost:8001/health`
- **Depends on**: SurrealDB (and optionally ingestion completion)
- **Logs**: `docker compose logs mcp`

## Volumes

- **surrealdb-data**: Persistent vector database storage
- **ingest-status**: Shared status files (ingestion completion flag)
- **./repos**: Bind-mounted for local repo access (optional)
- **./config**: Bind-mounted for shared configuration

## Configuration

### Priority-based Ingestion

Control which repositories to ingest:

```bash
# High priority only (default)
PRIORITY=high docker compose up

# Medium + high
PRIORITY=medium docker compose up

# All repositories
PRIORITY=ALL docker compose up
```

### Repository Configuration

Edit `config/repositories.yaml` to add/remove repositories:

```yaml
repositories:
  - id: my-service
    github_url: https://github.com/myorg/my-service
    repo_type: backend
    languages: [rust]
    priority: high
```

## Stopping and Cleanup

```bash
# Stop services (preserves data)
docker compose down

# Stop and remove volumes (deletes data)
docker compose down -v

# Restart just ingestion
docker compose up ingest

# Restart just MCP
docker compose restart mcp
```

## Troubleshooting

### Ingestion fails
```bash
# Check logs
docker compose logs ingest

# Common issues:
# - Missing GITHUB_TOKEN
# - Missing embedding service credentials
# - SurrealDB not ready (check healthcheck)
```

### MCP health shows "waiting_for_ingestion"
This is normal while ingestion is running. Wait for ingestion to complete.

### SurrealDB connection refused
```bash
# Check SurrealDB health
curl http://localhost:8000/health

# Check logs
docker compose logs surrealdb
```

### Reset everything
```bash
docker compose down -v
docker compose up --build
```

## Using with Cursor IDE

1. Start services: `docker compose up`
2. Wait for health: `curl http://localhost:8001/health`
3. Configure Cursor MCP settings to connect to `http://localhost:8001`
4. MCP server will query local SurrealDB for semantic code search

## Cloud vs Local

**Local (Docker Compose)**:
- `VECTOR_BACKEND=surrealdb`
- No cloud costs
- Full control over data
- Requires Docker

**Cloud (Qdrant)**:
- `VECTOR_BACKEND=qdrant`
- Set `QDRANT_URL` and `QDRANT_API_KEY`
- Managed service
- Network-dependent

Both use the same ingestion pipeline and MCP server—only the vector backend changes.
