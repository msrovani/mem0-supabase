#!/usr/bin/env bash
# ============================================
# Mem0 Backup & Restore Scripts
# ============================================
# Usage:
#   ./scripts/backup.sh              # Full backup
#   ./scripts/backup.sh --restore backup_20240101.sql  # Restore
# ============================================

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/backup_${TIMESTAMP}.sql"

# Database connection
DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"
DB_NAME="${POSTGRES_DB:-mem0}"
DB_USER="${POSTGRES_USER:-postgres}"

mkdir -p "${BACKUP_DIR}"

backup() {
    echo "🔄 Starting backup to ${BACKUP_FILE}..."

    # Schema + data
    pg_dump -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" \
        --format=plain --no-owner --no-acl \
        --verbose > "${BACKUP_FILE}" 2>"${BACKUP_FILE}.log"

    # Compress
    gzip "${BACKUP_FILE}"
    echo "✅ Backup complete: ${BACKUP_FILE}.gz"

    # Cleanup old backups (keep last 7 days)
    find "${BACKUP_DIR}" -name "backup_*.sql.gz" -mtime +7 -delete
    echo "🧹 Cleaned up backups older than 7 days"

    # Show size
    ls -lh "${BACKUP_FILE}.gz"
}

restore() {
    local file="$1"

    if [[ ! -f "${file}" ]]; then
        echo "❌ Backup file not found: ${file}"
        exit 1
    fi

    echo "⚠️  Restoring from ${file}..."
    echo "⚠️  This will OVERWRITE the current database!"
    read -p "Continue? (yes/no): " confirm

    if [[ "${confirm}" != "yes" ]]; then
        echo "❌ Restore cancelled"
        exit 1
    fi

    # Decompress if needed
    if [[ "${file}" == *.gz ]]; then
        gunzip -k "${file}"
        file="${file%.gz}"
    fi

    psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" \
        -f "${file}"

    echo "✅ Restore complete"
}

# Main
case "${1:-backup}" in
    --backup|backup)
        backup
        ;;
    --restore|restore)
        if [[ -z "${2:-}" ]]; then
            echo "Usage: $0 --restore <backup_file>"
            echo "Available backups:"
            ls -la "${BACKUP_DIR}"/backup_*.sql.gz 2>/dev/null || echo "  (none)"
            exit 1
        fi
        restore "$2"
        ;;
    --list|list)
        echo "Available backups:"
        ls -lh "${BACKUP_DIR}"/backup_*.sql.gz 2>/dev/null || echo "  (none found)"
        ;;
    *)
        echo "Usage: $0 {backup|restore|list}"
        exit 1
        ;;
esac
