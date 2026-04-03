# Deployment Guide

## Prerequisites

- Docker & Docker Compose
- PostgreSQL 16+ with pgvector extension
- OpenAI API key
- (Optional) Redis 7+

## Option 1: Docker Compose (Recommended)

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env with your credentials

# 2. Start all services
docker-compose up -d

# 3. Verify
curl http://localhost:8000/health

# 4. View logs
docker-compose logs -f mem0-api
```

## Option 2: Direct Installation

```bash
# 1. Install dependencies
pip install -r server/requirements.txt

# 2. Set environment variables
export POSTGRES_HOST=localhost
export POSTGRES_DB=mem0
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=your-password
export OPENAI_API_KEY=sk-your-key
export JWT_SECRET=your-secret-min-32-chars

# 3. Run database migrations
psql -h localhost -U postgres -d mem0 -f supabase/migrations/004_vector_index_tuning.sql

# 4. Start server
uvicorn server.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Option 3: Kubernetes

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mem0-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: mem0-api
  template:
    metadata:
      labels:
        app: mem0-api
    spec:
      containers:
      - name: mem0-api
        image: mem0-supabase:latest
        ports:
        - containerPort: 8000
        envFrom:
        - secretRef:
            name: mem0-secrets
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 15
          periodSeconds: 10
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 30
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
```

## Environment Variables

See `.env.example` for all available configuration options.

### Required
- `POSTGRES_HOST` - PostgreSQL host
- `POSTGRES_DB` - Database name
- `POSTGRES_USER` - Database user
- `POSTGRES_PASSWORD` - Database password
- `OPENAI_API_KEY` - OpenAI API key

### Recommended for Production
- `JWT_SECRET` - JWT signing key (min 32 chars)
- `DB_POOL_MIN` - Min DB connections (default: 2)
- `DB_POOL_MAX` - Max DB connections (default: 20)
- `ALLOWED_ORIGINS` - CORS allowed origins

## Monitoring

- **Health**: `GET /health` — returns DB and LLM connectivity status
- **Metrics**: Integrate with Prometheus via `/metrics` endpoint (coming soon)
- **Logs**: Structured JSON logs with request IDs

## Backup

```bash
# Backup
./scripts/backup.sh

# List backups
./scripts/backup.sh --list

# Restore
./scripts/backup.sh --restore backups/backup_20240101_120000.sql.gz
```

## Scaling

- **Horizontal**: Run multiple API instances behind a load balancer
- **Database**: Use PostgreSQL read replicas for search-heavy workloads
- **Cache**: Enable Redis for L1 caching in high-traffic scenarios
