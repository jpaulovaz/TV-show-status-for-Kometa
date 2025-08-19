#!/bin/bash

# Se a pasta /app/config estiver vazia, copie todos os arquivos/pastas padrão
if [ -z "$(ls -A /app/config)" ]; then
  cp -r /app/config.example.yml /app/config/
  cp -r /app/kometa /app/config/
fi

# Ajustar permissões dos arquivos/pastas
chown -R "${PUID}:${PGID}" /app/config

echo "$CRON cd /app && /usr/local/bin/python TSSK.py 2>&1 | tee -a /var/log/cron.log" > /etc/cron.d/tssk-cron
chmod 0644 /etc/cron.d/tssk-cron
crontab /etc/cron.d/tssk-cron
echo "TSSK is starting with the following cron schedule: $CRON"
touch /var/log/cron.log
cron
tail -f /var/log/cron.log