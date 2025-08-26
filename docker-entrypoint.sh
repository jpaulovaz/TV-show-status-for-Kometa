#!/bin/bash

# Cria a pasta /app/config se não existir
mkdir -p /app/config/kometa/tssk

# Copia todo o conteúdo de /app/files para /app/config (sobrescreve arquivos existentes)
cp -r /app/files/* /app/config/

# Ajustar permissões se necessário
chown -R "${PUID}:${PGID}" /app

# Escreve as variáveis necessárias em um arquivo oculto para que o cron possa acessá-las
echo "export DOCKER=$DOCKER" > /app/.cron_env
echo "export PUID=$PUID" >> /app/.cron_env
echo "export PGID=$PGID" >> /app/.cron_env
echo "export TZ=$TZ" >> /app/.cron_env # Inclui TZ para o contexto do cron

# Limpa o arquivo de configuração do cron para evitar duplicações ou entradas antigas
> /etc/cron.d/tssk-cron

# Define o shell e o usuário para as tarefas cron
echo "SHELL=/bin/bash" > /etc/cron.d/tssk-cron
echo "USER=appuser" >> /etc/cron.d/tssk-cron

# Priorizar a nova variável DAILY_TIMES para horários em formato "normal"
if [ -n "$DAILY_TIMES" ]; then
    echo "Configurando agendamentos diários a partir de DAILY_TIMES: $DAILY_TIMES"
    IFS=',' read -ra ADDR <<< "$DAILY_TIMES"
    for i in "${ADDR[@]}"; do
        time_str=$(echo "$i" | xargs)
        if [[ "$time_str" =~ ^([0-1]?[0-9]|2[0-3]):([0-5]?[0-9])$ ]]; then
            HOUR=${BASH_REMATCH[1]}
            MINUTE=${BASH_REMATCH[2]}
            echo "$MINUTE $HOUR * * * source /app/.cron_env && cd /app && /usr/local/bin/python TSSK.py 2>&1 | tee -a /var/log/cron.log" >> /etc/cron.d/tssk-cron
            echo "  - Tarefa cron adicionada para: $time_str"
        else
            echo "  - Aviso: Formato de hora inválido '$time_str' em DAILY_TIMES. Esperado HH:MM. Ignorando."
        fi
    done
elif [ -n "$CRON" ]; then
    echo "Configurando agendamento a partir de CRON: $CRON"
    echo "$CRON source /app/.cron_env && cd /app && /usr/local/bin/python TSSK.py 2>&1 | tee -a /var/log/cron.log" >> /etc/cron.d/tssk-cron
else
    echo "Nenhuma variável de ambiente DAILY_TIMES ou CRON foi definida. Nenhuma tarefa cron será agendada."
    echo "# Nenhuma tarefa cron configurada." >> /etc/cron.d/tssk-cron # Garante que o arquivo não fique vazio
fi

chmod 0644 /etc/cron.d/tssk-cron

cron -f &

echo "O TSSK está sendo iniciado com a seguinte programação cron:"
cat /etc/cron.d/tssk-cron
echo ""

touch /var/log/cron.log 
tail -f /var/log/cron.log