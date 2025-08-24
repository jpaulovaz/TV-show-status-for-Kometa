#!/bin/bash

# Cria a pasta /app/config se não existir
mkdir -p /app/config/kometa/tssk

# Copia todo o conteúdo de /app/files para /app/config (sobrescreve arquivos existentes)
cp -r /app/files/* /app/config/

# Ajustar permissões se necessário
chown -R "${PUID}:${PGID}" /app

# --- PASSO 1: Cria um arquivo de ambiente para o cron ---
# Escreve as variáveis necessárias em um arquivo oculto
echo "export DOCKER=$DOCKER" > /app/.cron_env
echo "export PUID=$PUID" >> /app/.cron_env
echo "export PGID=$PGID" >> /app/.cron_env

# Adiciona o cronjob no arquivo do crontab
echo "SHELL=/bin/bash" > /etc/cron.d/tssk-cron
echo "USER=appuser" >> /etc/cron.d/tssk-cron

# --- PASSO 2: Carrega o arquivo de ambiente antes de rodar o comando ---
# O 'source' garante que as variáveis estejam disponíveis
echo "$CRON source /app/.cron_env && cd /app && /usr/local/bin/python TSSK.py 2>&1 | tee -a /var/log/cron.log" >> /etc/cron.d/tssk-cron

chmod 0644 /etc/cron.d/tssk-cron
crontab /etc/cron.d/tssk-cron
echo "O TSSK está sendo iniciado com a seguinte programação cron : $CRON"

touch /var/log/cron.log
cron
tail -f /var/log/cron.log