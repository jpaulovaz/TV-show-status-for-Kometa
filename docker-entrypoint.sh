#!/bin/bash

# --- Função de Rotação de Logs ---
rotate_logs() {
    LOG_DIR="/app/config/logs"
    LOG_FILE="$LOG_DIR/tssk.log"
    MAX_LOGS=5

    mkdir -p "$LOG_DIR"

    # Rotaciona os logs apenas se o arquivo principal existir
    if [ -f "$LOG_FILE" ]; then
        # Remove o log mais antigo
        rm -f "$LOG_DIR/tssk-$MAX_LOGS.log"
        # Renomeia os logs existentes
        for i in $(seq $((MAX_LOGS - 1)) -1 1); do
            if [ -f "$LOG_DIR/tssk-$i.log" ]; then
                mv "$LOG_DIR/tssk-$i.log" "$LOG_DIR/tssk-$((i+1)).log"
            fi
        done
        mv "$LOG_FILE" "$LOG_DIR/tssk-1.log"
    fi
}
export -f rotate_logs # Exporta a função para que o cron possa usá-la

# Cria a pasta /app/config se não existir
mkdir -p /app/config/kometa/tssk

# Copia todo o conteúdo de /app/files para /app/config (sobrescreve arquivos existentes)
cp -r /app/files/* /app/config/

# Ajusta as permissões do diretório de configuração para que o appuser possa escrever nele.
chown -R "${PUID}:${PGID}" /app/config

# Escreve as variáveis necessárias em um arquivo oculto para que o cron possa acessá-las
echo "export DOCKER=$DOCKER" > /app/.cron_env
echo "export PUID=$PUID" >> /app/.cron_env
echo "export PGID=$PGID" >> /app/.cron_env
echo "export TZ=$TZ" >> /app/.cron_env # Inclui TZ para o contexto do cron
chown "${PUID}:${PGID}" /app/.cron_env # Garante que o appuser possa ler este arquivo

# Limpa o arquivo de configuração do cron para evitar duplicações ou entradas antigas
> /etc/cron.d/tssk-cron

# Define o shell e o usuário para as tarefas cron
echo "SHELL=/bin/bash" >> /etc/cron.d/tssk-cron

# Priorizar a variável HORARIOS_DE_EXECUCAO para horários em formato "normal"
if [ -n "$CRON" ]; then
    echo "Configurando agendamento a partir de CRON: $CRON"
    echo "$CRON appuser bash -c 'rotate_logs && source /app/.cron_env && cd /app && /usr/local/bin/python TSSK.py >> /app/config/logs/tssk.log 2>&1'" >> /etc/cron.d/tssk-cron
    
elif [ -n "$HORARIOS_DE_EXECUCAO" ]; then
    echo "Configurando agendamentos diários a partir de HORARIOS_DE_EXECUCAO: $HORARIOS_DE_EXECUCAO"
    # Remove aspas (simples e duplas) do início e do fim da string para evitar erros de parsing
    CLEANED_TIMES=$(echo "$HORARIOS_DE_EXECUCAO" | sed "s/^'//;s/'$//;s/^\"//;s/\"$//")
    IFS=',' read -ra ADDR <<< "$CLEANED_TIMES"
    for i in "${ADDR[@]}"; do
        # Remove espaços em branco da string de tempo
        time_str=$(echo "$i" | xargs)
        if [[ "$time_str" =~ ^([0-1]?[0-9]|2[0-3]):([0-5]?[0-9])$ ]]; then
            HOUR=${BASH_REMATCH[1]}
            MINUTE=${BASH_REMATCH[2]}
            echo "$MINUTE $HOUR * * * appuser bash -c 'rotate_logs && source /app/.cron_env && cd /app && /usr/local/bin/python TSSK.py >> /app/config/logs/tssk.log 2>&1'" >> /etc/cron.d/tssk-cron
            echo "  - Tarefa cron adicionada para: $time_str"
        else
            echo "  - Aviso: Formato de hora inválido '$time_str' em HORARIOS_DE_EXECUCAO. Esperado HH:MM. Ignorando."
        fi
    done
else
    echo "Nenhuma variável de ambiente HORARIOS_DE_EXECUCAO ou CRON foi definida. Nenhuma tarefa cron será agendada."
    echo "# Nenhuma tarefa cron configurada." >> /etc/cron.d/tssk-cron # Garante que o arquivo não fique vazio
fi

chmod 0644 /etc/cron.d/tssk-cron

# Cria o diretório de logs e o arquivo inicial para o tail funcionar
mkdir -p /app/config/logs
touch /app/config/logs/tssk.log
chown -R "${PUID}:${PGID}" /app/config/logs

# Verifica se a variável EXECUTAR_AO_INICIAR está definida como "true" (ignora maiúsculas/minúsculas)
if [[ "${EXECUTAR_AO_INICIAR,,}" == "true" ]]; then
    echo "Executando o script imediatamente na inicialização (EXECUTAR_AO_INICIAR=true)..."
    su -s /bin/bash -c "rotate_logs && source /app/.cron_env && cd /app && /usr/local/bin/python TSSK.py >> /app/config/logs/tssk.log 2>&1" appuser &
fi

# --- Inicia o Cron e o Log --- #
cron -f &
exec tail -f /app/config/logs/tssk.log