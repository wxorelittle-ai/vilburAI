#!/usr/bin/env bash
# Сторож: проверяет живость сайта и лечит простые падения (раздел 10 ТЗ — мониторинг).
#
# В cron от root, каждые 5 минут:
#   */5 * * * * bash /opt/brigadir_pro/deploy/watchdog.sh >> /var/log/brigadir_pro/watchdog.log 2>&1
#
# Проверяем /healthz (он же трогает БД), а не главную: gunicorn может отвечать 200,
# когда база уже недоступна. Перезапускаем только после двух неудач подряд — чтобы
# не дёргать сервис из-за одной сетевой икоты.

set -uo pipefail

URL="${HEALTH_URL:-https://vilbur.online/healthz}"
STATE="/run/brigadir_pro/watchdog.fails"
POROG=2

mkdir -p "$(dirname "$STATE")"
[ -f "$STATE" ] || echo 0 > "$STATE"
FAILS=$(cat "$STATE" 2>/dev/null || echo 0)

CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$URL" || echo 000)

if [ "$CODE" = "200" ]; then
    if [ "$FAILS" -gt 0 ]; then
        echo "[$(date '+%F %T')] ОК (код 200) — счётчик сбоев сброшен"
    fi
    echo 0 > "$STATE"
    exit 0
fi

FAILS=$((FAILS + 1))
echo "$FAILS" > "$STATE"
echo "[$(date '+%F %T')] СБОЙ: $URL вернул $CODE (подряд: $FAILS)"

if [ "$FAILS" -ge "$POROG" ]; then
    echo "[$(date '+%F %T')] Перезапускаю brigadir_pro после $FAILS сбоев подряд"
    systemctl restart brigadir_pro
    sleep 5
    NEW=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$URL" || echo 000)
    echo "[$(date '+%F %T')] После перезапуска: $NEW"
    [ "$NEW" = "200" ] && echo 0 > "$STATE"
fi
