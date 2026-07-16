#!/usr/bin/env bash
# Ежедневный автоматический бэкап базы и медиа (раздел 8 ТЗ — обязательное требование).
#
# Ставится в cron от root:
#   0 3 * * * bash /opt/brigadir_pro/deploy/backup.sh >> /var/log/brigadir_pro/backup.log 2>&1
#
# Дамп снимаем от системного пользователя postgres (peer-аутентификация): так не
# нужен пароль ни в cron, ни в файле скрипта. Запускать от root.

set -euo pipefail

BACKUP_DIR="/var/backups/brigadir_pro"
APP_DIR="/opt/brigadir_pro"
DB_NAME="brigadir_pro"
KEEP_DAYS=14
MIN_SIZE=1000   # байт: меньше — значит дамп пустой/битый

mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y-%m-%d_%H%M%S)
FILE="$BACKUP_DIR/brigadir_pro_${TIMESTAMP}.sql.gz"

echo "[$(date '+%F %T')] Старт бэкапа"

sudo -u postgres pg_dump "$DB_NAME" | gzip > "$FILE"

# Пустой бэкап хуже, чем его отсутствие: лучше упасть громко, чем тихо хранить мусор
SIZE=$(stat -c%s "$FILE")
if [ "$SIZE" -lt "$MIN_SIZE" ]; then
    echo "ОШИБКА: дамп подозрительно мал (${SIZE} б) — $FILE" >&2
    exit 1
fi
echo "БД: $FILE (${SIZE} б)"

# Медиа: логотипы, PDF документов и смет, фото-акты
if [ -d "$APP_DIR/media" ]; then
    tar -czf "$BACKUP_DIR/media_${TIMESTAMP}.tar.gz" -C "$APP_DIR" media/
    echo "Медиа: $BACKUP_DIR/media_${TIMESTAMP}.tar.gz"
fi

# Ротация — удаляем копии старше KEEP_DAYS дней
find "$BACKUP_DIR" -name '*.gz' -mtime "+${KEEP_DAYS}" -delete
echo "[$(date '+%F %T')] Готово. Копии старше ${KEEP_DAYS} дн. удалены."
