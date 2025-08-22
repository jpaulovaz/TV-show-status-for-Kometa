#!/bin/bash

# Cria a pasta /app/config se não existir
mkdir -p /app/config/kometa/tssk

# Copia todo o conteúdo de /app/files para /app/config (sobrescreve arquivos existentes)
cp -r /app/files/* /app/config/

# Ajustar permissões se necessário
chown -R "${PUID}:${PGID}" /app

# Adiciona a diretiva USER para que o cron execute o trabalho como 'appuser'
echo "SHELL=/bin/bash" > /etc/cron.d/tssk-cron
echo "USER=appuser" >> /etc/cron.d/tssk-cron
echo "$CRON DOCKER=$DOCKER cd /app && /usr/local/bin/python /app/TSSK.py 2>&1 | tee -a /var/log/cron.log" >> /etc/cron.d/tssk-cron

chmod 0644 /etc/cron.d/tssk-cron
crontab /etc/cron.d/tssk-cron
echo "TSSK is starting with the following cron schedule: $CRON"
touch /var/log/cron.log
cron
tail -f /var/log/cron.log