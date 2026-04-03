# API Migration Guide

## v1.0 → v2.0

### Breaking Changes

#### 1. Authentication Required
All endpoints except `/health` now require JWT authentication.

**Before:**
```bash
curl http://localhost:8000/memories
```

**After:**
```bash
curl -H "Authorization: Bearer $JWT_TOKEN" http://localhost:8000/memories
```

#### 2. No Default Credentials
Environment variables `POSTGRES_HOST`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `OPENAI_API_KEY` are now required. The server will fail-fast if any are missing.

**Before:**
```bash
# Defaults were used
POSTGRES_HOST=postgres  # default
POSTGRES_PASSWORD=postgres  # default
```

**After:**
```bash
# Must be explicitly set
export POSTGRES_HOST=your-host
export POSTGRES_PASSWORD=your-secure-password
```

#### 3. Response Format Changes
- `GET /memories` now returns paginated response: `{items, next_cursor, total_count}`
- Error responses now include `request_id` field

**Before:**
```json
[{"id": "123", "memory": "..."}]
```

**After:**
```json
{
  "items": [{"id": "123", "memory": "..."}],
  "next_cursor": "mem_456",
  "total_count": 42
}
```

#### 4. New Required Headers
- `X-Request-Id` is now generated automatically and returned in response headers
- `Content-Type: application/json` is set on all responses

### New Features

#### Idempotency Keys
```bash
curl -X POST http://localhost:8000/memories \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello"}], "user_id": "u1", "idempotency_key": "req_123"}'
```

#### Bulk Operations
```bash
curl -X POST http://localhost:8000/memories/bulk \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"items": [{"messages": [...], "user_id": "u1"}, ...]}'
```

#### SSE Streaming
```bash
curl -N -X POST http://localhost:8000/memories/stream \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello"}], "user_id": "u1"}'
```

### Migration Steps

1. **Set environment variables** — Copy `.env.example` to `.env` and fill in all required values
2. **Generate JWT secret** — `export JWT_SECRET=$(openssl rand -hex 32)`
3. **Update client code** — Add `Authorization: Bearer <token>` to all requests
4. **Update response parsing** — Handle paginated response format for `GET /memories`
5. **Test with health endpoint** — `curl http://localhost:8000/health` should return `{"status": "healthy"}`

### Rollback

If you need to rollback to v1.0:
```bash
git checkout v1.0.0
docker-compose down
docker-compose up -d
```
