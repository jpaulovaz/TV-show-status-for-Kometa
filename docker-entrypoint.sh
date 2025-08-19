#!/bin/bash

# Copiar arquivos padrão para o volume se não existirem
if [ ! -f /app/config/config.example.yml ]; then
  cp /app/config.example.yml /app/config/config.example.yml
fi

# Exemplo para copiar uma pasta inteira (se necessário)
if [ ! -d /app/config/kometa ]; then
  cp -r /app/kometa /app/config/kometa
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