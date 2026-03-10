# Security Policy - Mem0-Supabase

> ⚠️ **For the complete security guide** with detailed threat models, mitigations, and operational procedures, see [`SECURITY_COMPLETE.md`](./SECURITY_COMPLETE.md)

---

## 🛡️ Security Baseline

Mem0-Supabase follows a **Deny-by-Default** security posture. All memory operations (add, search, update, delete) must be scoped to a valid tenant identifier (`user_id`, `agent_id`, or `run_id`).

### Defense-in-Depth Architecture

```text
API Layer → Application Security → Database Security
  ↓            ↓                     ↓
  Input     require_tenant         RLS
  Validation   StorageGuard      Parameterized
  MCP Schema   ContextFirewall    Queries
  Budgets      Surprise Engine    Vault
```

---

## 🗺️ Threat Model Summary

Mem0-Supabase mitigates **8 major threat vectors**:

| # | Threat | Severity | Mitigation | Status |
| :--- | :--- | :--- | :--- | :--- |
| **T1** | SQL Injection | 🔴 Critical | Parameterized RPCs | ✅ PR3, PR5 |
| **T2** | Cross-Tenant Leak | 🔴 Critical | require_tenant + RLS | ✅ PR2 |
| **T3** | Prompt Injection | 🟠 High | Context Firewall | ✅ PR2 |
| **T4** | Path Traversal | 🟠 High | StorageGuard | ✅ PR1 |
| **T5** | Memory Poisoning | 🟡 Medium | SurpriseEngine | ✅ PR2 |
| **T6** | DoS Attacks | 🟡 Medium | Budgets + Limits | ✅ PR2 |
| **T7** | PII Exfiltration | 🟡 Medium | ContextFirewall | ✅ PR2 |
| **T8** | Unauthorized Tools | 🟡 Medium | MCP Schema | ✅ PR2 |

**Detailed analysis**: See [`SECURITY_COMPLETE.md`](./SECURITY_COMPLETE.md)

---

## 🛠️ Security Controls

### 1. Tenant Scoping (`require_tenant`)

Every memory operation is validated:

```python
from mem0.security.tenant_scope import require_tenant

@require_tenant
def search(self, query: str, *, user_id=None, agent_id=None, run_id=None):
    # Raises SecurityException if ALL tenant IDs are missing
    ...
```

**Coverage**: All CRUD operations in `Memory`, `AsyncMemory`, `RecollectionEngine`

---

### 2. Context Firewall (PII Redaction)

Automatically redacts sensitive data before sending to LLMs:

**Patterns Detected**:

- Emails: `user@example.com` → `[REDACTED]`
- Phones: `(555) 123-4567` → `[REDACTED]`
- SSNs: `123-45-6789` → `[REDACTED]`
- Credit Cards: `1234-5678-9012-3456` → `[REDACTED]`
- IP Addresses: `192.168.1.1` → `[REDACTED]`

**Prompt Injection Prevention**:

- Detects: "ignore previous instructions", "disregard all prior", etc.
- Wraps content in `<DATA>` tags to prevent execution

```python
from mem0.security.context_firewall import ContextFirewall

firewall = ContextFirewall()
safe_memories = firewall.sanitize(retrieved_memories)
```

---

### 3. StorageGuard (Path Validation)

Prevents path traversal and file system attacks:

```python
from mem0.security.storage_guard import StorageGuard

guard = StorageGuard()

# ✅ Valid
guard.validate("mem0/org1/team1/user123/document.pdf")

# ❌ Blocked
guard.validate("mem0/../../../etc/passwd")  # Path traversal
guard.validate("mem0/file$(rm -rf).jpg")    # Shell injection
```

**Rules**:

- Max 10 segments (prevents deep nesting)
- No `..` (prevents traversal)
- Regex: `^[a-zA-Z0-9/_.-]+$` (alphanumeric only)
- MIME type validation
- Size limit: 25MB per artifact

---

### 4. SQL Injection Prevention (RPC-First)

All database queries use **parameterized statements**:

```python
# ❌ VULNERABLE (Never do this)
sql = f"SELECT * FROM memories WHERE user_id = '{user_id}'"

# ✅ SECURE (Always do this)
from sqlalchemy import text
sql = text("SELECT * FROM memories WHERE user_id = :user_id")
conn.execute(sql, {"user_id": user_id})
```

**Every Supabase operation** uses this pattern (enforced in PR3, verified in PR5).

---

### 5. Resource Budgets (DoS Prevention)

```python
from mem0.security import budgets

MAX_TRANSCRIPT_CHARS = 25000        # ~5-7 pages
MAX_TEXT_PAYLOAD_CHARS = 10000      # ~2 pages
MAX_METADATA_BYTES = 8192           # 8 KB
MAX_ARTIFACTS_PER_INTERACTION = 5
MAX_BATCH_SIZE = 100
DEFAULT_SQL_TIMEOUT = "30s"
```

These limits prevent:

- Memory exhaustion
- Database timeouts
- Excessive processing

---

## ✅ Supabase Configuration Checklist

### Pre-Deployment Security Audit

#### Database Layer

- [ ] Row-Level Security (RLS) enabled on `memories`, `entities`, `relationships` tables
- [ ] Service role key used only for background jobs
- [ ] Anon key has read-only permissions
- [ ] Supabase Vault configured for all secrets
- [ ] Statement timeout set to 30s
- [ ] Connection pooling configured

#### Application Layer

- [ ] All memory operations use `@require_tenant` decorator
- [ ] Context Firewall enabled in production (`enable_firewall=True`)
- [ ] StorageGuard validates all artifact paths
- [ ] Budgets enforced (checked in code)
- [ ] Error messages don't leak sensitive data

#### Infrastructure Layer

- [ ] Private storage buckets for `mem0` artifacts
- [ ] Realtime channels use RLS policies
- [ ] Edge functions enforce tenant scoping
- [ ] Database backups enabled (daily minimum)
- [ ] Audit logging configured

---

## 🚨 Incident Response

### Severity Classification

| Level | Event | Response Time | Actions |
| :--- | :--- | :--- | :--- |
| 🔴 **P0** | Data breach, SQL injection in production | Immediate | Isolate, rotate keys, notify |
| 🟠 **P1** | Tenant leak, unauthorized access | 1 hour | Investigate, patch, audit data |
| 🟡 **P2** | PII exposure, failed injection attempt | 4 hours | Review firewall rules |
| 🟢 **P3** | Rate limit hit, DoS attempt | 24 hours | Monitor, adjust budgets |

### Emergency Contacts

For security vulnerabilities, contact: **<security@mem0.ai>**

**Do NOT** open public GitHub issues for security bugs.

---

## 📋 Compliance Considerations

### GDPR (EU)

- ✅ PII redaction via Context Firewall
- ✅ Right to erasure (`delete_all()` method)
- ✅ Data portability (`get_all()` returns JSON)
- ✅ Audit logging for data access

### SOC 2

- ✅ Tenant isolation enforced at DB + app layers
- ✅ Encryption at rest (Supabase default)
- ✅ Encryption in transit (TLS 1.3)
- ✅ Access logging and monitoring

### HIPAA (Healthcare)

⚠️ Requires additional:

- Business Associate Agreement (BAA) with Supabase
- Enhanced audit retention (7 years)
- PHI-specific redaction patterns

---

## 📚 Further Reading

- **Complete Security Guide**: [`SECURITY_COMPLETE.md`](./SECURITY_COMPLETE.md)
  - Detailed threat analysis (STRIDE methodology)
  - Implementation details for each control
  - Operational security procedures
  - Incident response playbook

- **12-Layer Architecture**: [`docs/architecture/12_LAYERS_COMPLETE.md`](./docs/architecture/12_LAYERS_COMPLETE.md)
  - Security controls at each cognitive layer
  - Performance vs security tradeoffs

- **Validation Checklist**: [`VALIDATION_CHECKLIST.md`](./VALIDATION_CHECKLIST.md)
  - Security test procedures
  - Pre-deployment verification steps

---

## 🔐 Security by Design

Mem0-Supabase is built with the principle that **security cannot be bolted on** - it must be **designed in** from the start.

Every layer, every operation, every API call enforces:

1. **Mandatory tenant scoping** (no bypass possible)
2. **Input validation** (StorageGuard, budgets, schemas)
3. **Output sanitization** (Context Firewall)
4. **Audit logging** (all security events)

**Security is not optional. It's the foundation.**
