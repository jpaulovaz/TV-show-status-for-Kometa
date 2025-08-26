#!/bin/bash
# Adiciona um usuário não root non-root
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

# Priorizar a variável CRON para agendamento customizado. Se não for informada, usar HORARIOS_DE_EXECUCAO.
if [ -n "$CRON" ]; then
    echo "Configurando agendamento a partir de CRON: $CRON"
    echo "$CRON appuser source /app/.cron_env && cd /app && /usr/local/bin/python TSSK.py 2>&1 | tee -a /var/log/cron.log" >> /etc/cron.d/tssk-cron
elif [ -n "$HORARIOS_DE_EXECUCAO" ]; then
    echo "Configurando agendamentos diários a partir de HORARIOS_DE_EXECUCAO: $HORARIOS_DE_EXECUCAO (CRON não foi definido)"
    # Remove aspas (simples e duplas) do início e do fim da string para evitar erros de parsing
    CLEANED_TIMES=$(echo "$HORARIOS_DE_EXECUCAO" | sed "s/^'//;s/'$//;s/^\"//;s/\"$//")
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
            echo "  - Aviso: Formato de hora inválido '$time_str' em HORARIOS_DE_EXECUCAO. Esperado HH:MM. Ignorando."
        fi
    done
else
    echo "Nenhuma variável de ambiente CRON ou HORARIOS_DE_EXECUCAO foi definida. Nenhuma tarefa cron será agendada."
    echo "# Nenhuma tarefa cron configurada." >> /etc/cron.d/tssk-cron # Garante que o arquivo não fique vazio
fi
# ALterar permição do arquivo
chmod 0644 /etc/cron.d/tssk-cron

# Verifica se a variável EXECUTAR_AO_INICIAR está definida como "true" (ignorando maiúsculas/minúsculas)
if [[ "${EXECUTAR_AO_INICIAR,,}" == "true" ]]; then
    echo "Executando o script imediatamente na inicialização (EXECUTAR_AO_INICIAR=true)..."
    # Executa como 'appuser' para manter a consistência de permissões com os trabalhos do cron.
    su -s /bin/bash -c "source /app/.cron_env && cd /app && /usr/local/bin/python TSSK.py" appuser 2>&1 | tee -a /var/log/cron.log &
fi

# ---Inicia o Cron e o Log --- #
cron -f &
touch /var/log/cron.log
chown "${PUID}:${PGID}" /var/log/cron.log
exec tail -f /var/log/cron.log