#!/bin/bash

# Defaults seguros para evitar variaveis vazias vindas do Docker/compose.
DOCKER="${DOCKER:-true}"
PUID="${PUID:-1000}"
PGID="${PGID:-1000}"
TZ="${TZ:-America/Sao_Paulo}"

# Valida o timezone tambem no sistema do container, para o cron usar o horario esperado.
if [ ! -f "/usr/share/zoneinfo/$TZ" ]; then
    echo "Aviso: TZ invalido ou nao encontrado: '$TZ'. Usando America/Sao_Paulo."
    TZ="America/Sao_Paulo"
fi
ln -snf "/usr/share/zoneinfo/$TZ" /etc/localtime
echo "$TZ" > /etc/timezone
export DOCKER PUID PGID TZ

# Cria a pasta /app/config se nao existir
mkdir -p /app/config/kometa/tssk /app/config/logs

# Copia todo o conteudo de /app/files para /app/config (sobrescreve arquivos existentes)
cp -r /app/files/* /app/config/

# Ajusta as permissoes do diretorio de configuracao para que o appuser possa escrever nele.
chown -R "${PUID}:${PGID}" /app/config

# Escreve as variaveis e a funcao de rotacao de logs em um arquivo para o cron. Foi necessario pois o LOG de eventos estava quebrando o cron
cat > /app/.cron_env <<EOF_CRON_ENV
export DOCKER="$DOCKER"
export PUID="$PUID"
export PGID="$PGID"
export TZ="$TZ"

rotate_logs() {
    LOG_DIR="/app/config/logs"
    LOG_FILE="\$LOG_DIR/tssk.log"
    MAX_LOGS=5

    mkdir -p "\$LOG_DIR"

    # Rotaciona os logs apenas se o arquivo principal existir
    if [ -f "\$LOG_FILE" ]; then
        # Remove o log mais antigo
        rm -f "\$LOG_DIR/tssk-\$MAX_LOGS.log"
        # Renomeia os logs existentes
        for i in \$(seq \$((MAX_LOGS - 1)) -1 1); do
            if [ -f "\$LOG_DIR/tssk-\$i.log" ]; then
                mv "\$LOG_DIR/tssk-\$i.log" "\$LOG_DIR/tssk-\$((i+1)).log"
            fi
        done
        mv "\$LOG_FILE" "\$LOG_DIR/tssk-1.log"
    fi
}
EOF_CRON_ENV
chown "${PUID}:${PGID}" /app/.cron_env

# Limpa o arquivo de configuracao do cron para evitar duplicacoes ou entradas antigas
> /etc/cron.d/tssk-cron

# Define o shell e o usuario para as tarefas cron
echo "SHELL=/bin/bash" >> /etc/cron.d/tssk-cron

# Priorizar a variavel CRON para agendamento em formato cron.
if [ -n "$CRON" ]; then
    echo "Configurando agendamento a partir de CRON: $CRON"
    echo "$CRON appuser bash -c 'source /app/.cron_env && rotate_logs && cd /app && /usr/local/bin/python TSSK.py >> /app/config/logs/tssk.log 2>&1'" >> /etc/cron.d/tssk-cron

elif [ -n "$HORARIOS_DE_EXECUCAO" ]; then
    echo "Configurando agendamentos diarios a partir de HORARIOS_DE_EXECUCAO: $HORARIOS_DE_EXECUCAO"
    # Remove aspas (simples e duplas) do inicio e do fim da string para evitar erros de parsing
    CLEANED_TIMES=$(echo "$HORARIOS_DE_EXECUCAO" | sed "s/^'//;s/'$//;s/^\"//;s/\"$//")
    IFS=',' read -ra ADDR <<< "$CLEANED_TIMES"
    for i in "${ADDR[@]}"; do
        # Remove espacos em branco da string de tempo
        time_str=$(echo "$i" | xargs)
        if [[ "$time_str" =~ ^([0-1]?[0-9]|2[0-3]):([0-5]?[0-9])$ ]]; then
            HOUR=${BASH_REMATCH[1]}
            MINUTE=${BASH_REMATCH[2]}
            echo "$MINUTE $HOUR * * * appuser bash -c 'source /app/.cron_env && rotate_logs && cd /app && /usr/local/bin/python TSSK.py >> /app/config/logs/tssk.log 2>&1'" >> /etc/cron.d/tssk-cron
            echo "  - Tarefa cron adicionada para: $time_str"
        else
            echo "  - Aviso: Formato de hora invalido '$time_str' em HORARIOS_DE_EXECUCAO. Esperado HH:MM. Ignorando."
        fi
    done
else
    DEFAULT_CRON="0 2 * * *"
    echo "Nenhuma variavel HORARIOS_DE_EXECUCAO ou CRON foi definida. Usando agendamento padrao: $DEFAULT_CRON"
    echo "$DEFAULT_CRON appuser bash -c 'source /app/.cron_env && rotate_logs && cd /app && /usr/local/bin/python TSSK.py >> /app/config/logs/tssk.log 2>&1'" >> /etc/cron.d/tssk-cron
fi

chmod 0644 /etc/cron.d/tssk-cron

# Cria o diretorio de logs e o arquivo inicial para o tail funcionar
touch /app/config/logs/tssk.log
chown -R "${PUID}:${PGID}" /app/config/logs

# Verifica se a variavel EXECUTAR_AO_INICIAR esta definida como "true" (ignora maiusculas/minusculas)
if [[ "${EXECUTAR_AO_INICIAR,,}" == "true" ]]; then
    echo "Executando o script imediatamente na inicializacao (EXECUTAR_AO_INICIAR=true)..."
    su -s /bin/bash -c "source /app/.cron_env && rotate_logs && cd /app && /usr/local/bin/python TSSK.py >> /app/config/logs/tssk.log 2>&1" appuser &
fi

# --- Inicia o Cron e o Log --- #
cron -f &
echo "Monitorando o arquivo de log em /app/config/logs/tssk.log..."
exec tail -F /app/config/logs/tssk.log
