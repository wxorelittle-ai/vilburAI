#!/usr/bin/env bash
# Ежедневный автоматический бэкап базы данных (раздел 8 ТЗ — обязательное требование).
# Подключить в cron: 0 3 * * * /opt/brigadir_pro/deploy/backup.sh >> /var/log/brigadir_pro/backup.log 2>&1

set -euo pipefail

BACKUP_DIR="/var/backups/brigadir_pro"
DB_NAME="brigadir_pro"
DB_USER="brigadir_pro"
KEEP_DAYS=14

mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y-%m-%d_%H%M%S)
FILE="$BACKUP_DIR/brigadir_pro_${TIMESTAMP}.sql.gz"

pg_dump -U "$DB_USER" -h 127.0.0.1 "$DB_NAME" | gzip > "$FILE"
echo "Бэкап создан: $FILE"

# Бэкап медиа (логотипы, PDF документов и смет)
tar -czf "$BACKUP_DIR/media_${TIMESTAMP}.tar.gz" -C /opt/brigadir_pro media/
echo "Бэкап медиа создан"

# Ротация — удаляем бэкапы старше KEEP_DAYS дней
find "$BACKUP_DIR" -name "*.gz" -mtime "+${KEEP_DAYS}" -delete
echo "Готово. Старые бэкапы (>${KEEP_DAYS} дн.) удалены."
