# Complete Security Guide - Mem0-Supabase

## Table of Contents

1. [Security Architecture Overview](#security-architecture-overview)
2. [Threat Model](#threat-model)
3. [Security Controls by PR](#security-controls-by-pr)
4. [Hardening Checklist](#hardening-checklist)
5. [Operational Security](#operational-security)
6. [Incident Response](#incident-response)

---

## Security Architecture Overview

Mem0-Supabase follows a **Defense-in-Depth** strategy with multiple layers of protection:

```
┌─────────────────────────────────────────────┐
│  External Attack Surface                    │
│  ├─ API Endpoints (Memory CRUD)            │
│  ├─ MCP Server (Tool Calls)                │
│  └─ Storage Buckets (Multimodal Artifacts) │
└─────────────────────────────────────────────┘
              ↓ [Input Validation]
┌─────────────────────────────────────────────┐
│  Application Security Layer                 │
│  ├─ require_tenant (Mandatory scoping)     │
│  ├─ StorageGuard (Path validation)         │
│  ├─ Context Firewall (PII redaction)       │
│  └─ Budget Enforcement (DoS prevention)    │
└─────────────────────────────────────────────┘
              ↓ [Parameterized Queries]
┌─────────────────────────────────────────────┐
│  Database Security Layer (Supabase)         │
│  ├─ Row-Level Security (RLS)               │
│  ├─ Parameterized RPCs                     │
│  ├─ Statement Timeout (30s default)        │
│  └─ Vault (Encrypted secrets)              │
└─────────────────────────────────────────────┘
```

### Core Security Principles

1. **Deny-by-Default**: All operations require explicit tenant context
2. **Zero-Trust**: Never trust client-provided identifiers without validation
3. **Least Privilege**: Database roles have minimal necessary permissions
4. **Audit Everything**: All security events are logged

---

## Threat Model

### Attack Vectors & Mitigations

| # | Threat | STRIDE Category | Severity | Mitigation | Status |
|---|--------|-----------------|----------|------------|--------|
| **T1** | SQL Injection | Tampering | 🔴 Critical | Parameterized queries + RPC wrappers | ✅ PR5 |
| **T2** | Cross-Tenant Data Leak | Information Disclosure | 🔴 Critical | require_tenant + RLS | ✅ PR2 |
| **T3** | Prompt Injection | Tampering | 🟠 High | Context Firewall + `<DATA>` tags | ✅ PR2 |
| **T4** | Path Traversal | Elevation of Privilege | 🟠 High | StorageGuard validation | ✅ PR1 |
| **T5** | Memory Poisoning | Tampering | 🟡 Medium | SurpriseEngine + Ego Anchors | ✅ PR2 |
| **T6** | Denial of Service | Availability | 🟡 Medium | Rate limiting + Budgets | ✅ PR2 |
| **T7** | PII Exfiltration | Information Disclosure | 🟡 Medium | ContextFirewall redaction | ✅ PR2 |
| **T8** | Unauthorized Tool Access | Elevation of Privilege | 🟡 Medium | MCP schema enforcement | ✅ PR2 |

---

## Security Controls by PR

### PR1: Multimodal Envelope & Storage Guard

**Threat Addressed**: T4 (Path Traversal)

#### StorageGuard Implementation

```python
from mem0.security.storage_guard import StorageGuard

guard = StorageGuard()

# ✅ Valid path
guard.validate_storage_path("mem0/org1/team1/user123/document.pdf")

# ❌ Path traversal attempt
guard.validate_storage_path("mem0/../../../etc/passwd")
# Raises: StorageSecurityError
```

#### Protection Mechanisms

1. **Path Segmentation**: Maximum 10 segments to prevent deep nesting attacks
2. **Traversal Detection**: Rejects any path containing `..`
3. **Character Validation**: Regex `^[a-zA-Z0-9/_.-]+$` (no shell metacharacters)
4. **MIME Type Verification**: Ensures artifacts match declared type
5. **Size Limits**: `MAX_ARTIFACT_SIZE_MB = 25` to prevent DoS

#### Security Tests

```python
# tests/test_storage_guard.py
def test_path_traversal_blocked():
    guard = StorageGuard()
    with pytest.raises(StorageSecurityError):
        guard.validate("mem0/../../secret")

def test_shell_injection_blocked():
    guard = StorageGuard()
    with pytest.raises(StorageSecurityError):
        guard.validate("mem0/file$(rm -rf /)")
```

---

### PR2: Security Hardening (Tenant Scoping + Context Firewall)

**Threats Addressed**: T2 (Cross-Tenant), T3 (Prompt Injection), T5 (Poisoning), T6 (DoS), T7 (PII)

#### **2.1 Tenant Scoping (`require_tenant`)**

Every memory operation is intercepted:

```python
from mem0.security.tenant_scope import require_tenant

@require_tenant
def search(self, query: str, *, user_id=None, agent_id=None, run_id=None):
    # This decorator ensures at least ONE tenant ID is present
    # Otherwise raises SecurityException
    ...
```

**Enforcement Points**:

- `Memory.add()` - Line 410
- `Memory.search()` - Line 936
- `Memory.get()` - Line 754
- `Memory.update()` - Line 1177
- `Memory.delete()` - Line 1204
- `AsyncMemory.*` - All methods
- `RecollectionEngine.recollect()` - Line 41

**RLS Integration**:
Tenant filters are passed directly to Supabase RPCs:

```sql
-- match_memories_hybrid RPC
CREATE FUNCTION match_memories_hybrid(
    filter jsonb,  -- Contains {"user_id": "...", "org_id": "..."}
    ...
)
SELECT * FROM memories
WHERE (metadata->>'user_id' = (filter->>'user_id'))
   OR (metadata->>'org_id' = (filter->>'org_id'));
```

#### **2.2 Context Firewall**

**PII Redaction Patterns**:

```python
# Detects and redacts:
EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
PHONE_PATTERN = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
SSN_PATTERN = r'\b\d{3}-\d{2}-\d{4}\b'
IP_PATTERN = r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'
CREDIT_CARD_PATTERN = r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'
```

**Prompt Injection Neutralization**:

```python
INJECTION_PATTERNS = [
    r"ignore\s+previous\s+instructions",
    r"disregard\s+all\s+prior",
    r"forget\s+everything",
    r"new\s+instructions:",
]
```

**Usage**:

```python
from mem0.security.context_firewall import ContextFirewall

firewall = ContextFirewall()

# Before sending to LLM
safe_context = firewall.sanitize(retrieved_memories)
# PII is now [REDACTED]
# Injection attempts are flagged or removed
```

#### **2.3 Budgets & Rate Limiting**

```python
# mem0/security/budgets.py
MAX_TRANSCRIPT_CHARS = 25000
MAX_TEXT_PAYLOAD_CHARS = 10000
MAX_METADATA_BYTES = 8192
MAX_ARTIFACTS_PER_INTERACTION = 5
MAX_BATCH_SIZE = 100
DEFAULT_SQL_TIMEOUT = "30s"
```

These prevent:

- Excessive memory allocations
- Database query timeouts
- Resource exhaustion attacks

---

### PR3: RPC-First Pattern (SQL Injection Prevention)

**Threat Addressed**: T1 (SQL Injection)

#### Before PR3 (Vulnerable)

```python
# ❌ DANGEROUS - f-string interpolation
sql = f"SELECT * FROM memories WHERE user_id = '{user_id}'"
# Attacker input: user_id = "' OR 1=1 --"
# Results in: SELECT * FROM memories WHERE user_id = '' OR 1=1 --'
```

#### After PR3 (Secure)

```python
# ✅ SAFE - Parameterized query
from sqlalchemy import text

sql = text("SELECT * FROM memories WHERE user_id = :user_id")
conn.execute(sql, {"user_id": user_id})
# Parameters are properly escaped
```

#### RPC Wrapper Pattern

```python
def _call_rpc(self, rpc_name: str, params: Dict[str, Any]):
    # Build parameter placeholders
    sql = text(f"SELECT * FROM {rpc_name}({', '.join([f'{k} := :{k}' for k in params.keys()])})")
    
    # Execute with bound parameters
    result = conn.execute(sql, params)
```

**Key Protection**: RPC names are from a controlled allowlist, parameters are bound, never interpolated.

---

### PR5: Security Regression Review (SQL Injection Fix)

**Threat Addressed**: T1 (Remaining SQL Injection)

#### Issue Found

```python
# PR4 code - VULNERABLE
timeout = self.config.get("sql_timeout", budgets.DEFAULT_SQL_TIMEOUT)
conn.execute(text(f"SET statement_timeout = '{timeout}'"))
# If timeout = "1'; DROP TABLE memories; --"
```

#### Fix Applied

```python
# PR5 fix - SECURE
timeout = self.config.get("sql_timeout", budgets.DEFAULT_SQL_TIMEOUT)
conn.execute(text("SET statement_timeout = :timeout"), {"timeout": timeout})
# Timeout is now safely bound as a parameter
```

**Location**: `mem0/vector_stores/supabase.py:183`

---

## Hardening Checklist

### Pre-Deployment Security Audit

#### ✅ Database Layer

- [ ] RLS enabled on all tables (`memories`, `entities`, `relationships`)
- [ ] Service role used only for background jobs (cron, webhooks)
- [ ] Anon key has minimal permissions
- [ ] Vault configured for all secrets (no hardcoded API keys)
- [ ] Statement timeout set to 30s
- [ ] Connection pooling configured (max 20 connections)

#### ✅ Application Layer

- [ ] All memory operations use `require_tenant`
- [ ] StorageGuard validates all artifact paths
- [ ] Context Firewall enabled in production (`enable_firewall=True`)
- [ ] Budgets enforced (transcript chars, metadata size)
- [ ] Error messages don't leak sensitive data

#### ✅ Infrastructure Layer (Supabase)

- [ ] Private storage buckets for `mem0` artifacts
- [ ] Realtime channels use RLS policies
- [ ] Edge Functions enforce tenant scoping
- [ ] Database backups enabled (daily)
- [ ] Audit logging configured

#### ✅ Code Quality

- [ ] No f-string SQL interpolation
- [ ] All tests pass (`pytest tests/`)
- [ ] Security tests pass (`pytest tests/test_*_security.py`)
- [ ] Dependency scanner clean (no critical CVEs)

---

## Operational Security

### Secret Management

**Required Secrets**:

```bash
# Stored in Supabase Vault
SUPABASE_SERVICE_ROLE_KEY  # For background jobs only
OPENAI_API_KEY             # For LLM calls
EMBEDDING_API_KEY          # For embeddings (if not OpenAI)
```

**Access Pattern**:

```python
from mem0.security.secrets_provider import SecretsProvider

provider = SecretsProvider(vault_enabled=True)
api_key = provider.get_secret("OPENAI_API_KEY")
# Never logs the actual key
```

### Audit Logging

All security events are logged:

```python
from mem0.security.audit_log import audit_logger

# Successful access
audit_logger.log_event("TENANT_ACCESS", "SUCCESS", {
    "user_id": "user_123",
    "action": "search",
    "timestamp": "2024-03-20T10:00:00Z"
})

# Blocked access
audit_logger.log_event("TENANT_ACCESS", "FAILURE", {
    "reason": "Missing tenant context",
    "ip": "192.168.1.1"
})
```

**Log Retention**: 90 days minimum for compliance

---

## Incident Response

### Security Event Classification

| Severity | Event Type | Response Time | Actions |
|----------|-----------|---------------|---------|
| 🔴 **P0** | Data breach, SQL injection | Immediate | Isolate system, rotate all keys, notify users |
| 🟠 **P1** | Tenant leak, unauthorized access | 1 hour | Investigate logs, patch vulnerability, audit affected data |
| 🟡 **P2** | PII exposure, failed injection attempt | 4 hours | Review firewall rules, update patterns |
| 🟢 **P3** | Rate limit hit, DoS attempt | 24 hours | Monitor, adjust budgets if needed |

### Breach Response Playbook

1. **Detect**: Audit logs show anomalous pattern
2. **Contain**: Disable affected API keys, rotate credentials
3. **Investigate**: Query audit logs for scope

   ```sql
   SELECT * FROM audit_log
   WHERE event_type = 'TENANT_ACCESS'
     AND status = 'FAILURE'
     AND timestamp > NOW() - INTERVAL '1 hour';
   ```

4. **Remediate**: Patch vulnerability, deploy fix
5. **Notify**: Inform affected users within 72 hours (GDPR)
6. **Post-Mortem**: Document incident, update threat model

---

## Security Best Practices

### For Developers

1. **Never bypass `require_tenant`** - Even for "admin" operations
2. **Always use parameterized queries** - Never f-string interpolation
3. **Validate all inputs** - Use Pydantic models, not raw dicts
4. **Log security events** - Every access denial, every anomaly
5. **Test security controls** - Write tests for each threat scenario

### For Operators

1. **Rotate secrets quarterly** - API keys, database passwords
2. **Review audit logs weekly** - Look for patterns
3. **Update dependencies monthly** - Apply security patches
4. **Test backups monthly** - Ensure recovery works
5. **Run penetration tests annually** - Third-party assessment

---

## Compliance Considerations

### GDPR (EU)

- ✅ PII redaction via Context Firewall
- ✅ Right to erasure (`delete_all()` method)
- ✅ Data portability (`get_all()` returns JSON)
- ✅ Audit logs for data access

### SOC 2

- ✅ Tenant isolation enforced
- ✅ Encryption at rest (Supabase default)
- ✅ Encryption in transit (TLS 1.3)
- ✅ Access logging and monitoring

### HIPAA (Healthcare)

- ⚠️ Requires additional controls:
  - Business Associate Agreement (BAA) with Supabase
  - Enhanced audit logging
  - PHI-specific redaction patterns

---

## Summary

Mem0-Supabase implements **enterprise-grade security** through:

1. ✅ **Multiple layers of defense** (application + database + infrastructure)
2. ✅ **Comprehensive threat coverage** (8 major attack vectors mitigated)
3. ✅ **Automated enforcement** (security controls can't be bypassed)
4. ✅ **Continuous monitoring** (audit logs + security tests)
5. ✅ **Incident readiness** (documented response procedures)

**Security is not optional** - it's baked into every layer of the architecture.

For security concerns or to report vulnerabilities, contact: [security@mem0.ai](mailto:security@mem0.ai)
