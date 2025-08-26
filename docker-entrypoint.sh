#!/bin/bash

# Verifica se o usuário 'appuser' existe. Se não, encerra com erro.
if ! id -u appuser >/dev/null 2>&1; then
    echo "Erro: O usuário 'appuser' não existe na imagem. A imagem Docker precisa ser construída com este usuário."
    exit 1
fi

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

# Limpa o arquivo de configuração do cron para evitar duplicações ou entradas antigas
> /etc/cron.d/tssk-cron

# Define o shell e o usuário para as tarefas cron
echo "SHELL=/bin/bash" >> /etc/cron.d/tssk-cron

# Priorizar a nova variável DAILY_TIMES para horários em formato "normal"
if [ -n "$DAILY_TIMES" ]; then
    echo "Configurando agendamentos diários a partir de DAILY_TIMES: $DAILY_TIMES"
    # Remove aspas (simples e duplas) do início e do fim da string para evitar erros de parsing
    CLEANED_TIMES=$(echo "$DAILY_TIMES" | sed "s/^'//;s/'$//;s/^\"//;s/\"$//")
    IFS=',' read -ra ADDR <<< "$CLEANED_TIMES"
    for i in "${ADDR[@]}"; do
        # Remove espaços em branco da string de tempo
        time_str=$(echo "$i" | xargs)
        if [[ "$time_str" =~ ^([0-1]?[0-9]|2[0-3]):([0-5]?[0-9])$ ]]; then
            HOUR=${BASH_REMATCH[1]}
            MINUTE=${BASH_REMATCH[2]}
            echo "$MINUTE $HOUR * * * appuser source /app/.cron_env && cd /app && /usr/local/bin/python TSSK.py 2>&1 | tee -a /var/log/cron.log" >> /etc/cron.d/tssk-cron
            echo "  - Tarefa cron adicionada para: $time_str"
        else
            echo "  - Aviso: Formato de hora inválido '$time_str' em DAILY_TIMES. Esperado HH:MM. Ignorando."
        fi
    done
elif [ -n "$CRON" ]; then
    echo "Configurando agendamento a partir de CRON: $CRON"
    echo "$CRON appuser source /app/.cron_env && cd /app && /usr/local/bin/python TSSK.py 2>&1 | tee -a /var/log/cron.log" >> /etc/cron.d/tssk-cron
else
    echo "Nenhuma variável de ambiente DAILY_TIMES ou CRON foi definida. Nenhuma tarefa cron será agendada."
    echo "# Nenhuma tarefa cron configurada." >> /etc/cron.d/tssk-cron # Garante que o arquivo não fique vazio
fi

chmod 0644 /etc/cron.d/tssk-cron

# --- PASSO 3: Execução Imediata (Opcional) --- #
# Verifica se a variável RUN_ON_STARTUP está definida como "true" (ignorando maiúsculas/minúsculas)
if [[ "${RUN_ON_STARTUP,,}" == "true" ]]; then
    echo "Executando o script imediatamente na inicialização (RUN_ON_STARTUP=true)..."
    # Executa como 'appuser' para manter a consistência de permissões com os trabalhos do cron.
    su -s /bin/bash -c "source /app/.cron_env && cd /app && /usr/local/bin/python TSSK.py" appuser 2>&1 | tee -a /var/log/cron.log &
fi

# --- PASSO 4: Inicia o Cron e o Log --- #
cron -f &

echo "O TSSK está sendo iniciado com a seguinte programação cron:"
cat /etc/cron.d/tssk-cron
echo ""

touch /var/log/cron.log 
exec tail -f /var/log/cron.log