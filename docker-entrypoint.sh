#!/bin/bash

# Cria a pasta /app/config se não existir
mkdir -p /app/config/kometa/tssk

# Copia todo o conteúdo de /app/files para /app/config (sobrescreve arquivos existentes)
cp -r /app/files/* /app/config/

# Ajustar permissões se necessário
chown -R "${PUID}:${PGID}" /app/config

echo "$CRON cd /app && /usr/local/bin/python TSSK.py 2>&1 | tee -a /var/log/cron.log" > /etc/cron.d/tssk-cron
chmod 0644 /etc/cron.d/tssk-cron
crontab /etc/cron.d/tssk-cron
echo "TSSK is starting with the following cron schedule: $CRON"
touch /var/log/cron.log
cron
tail -f /var/log/cron.log