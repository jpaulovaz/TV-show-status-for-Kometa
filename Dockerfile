# Use a slim Python image as the base
FROM python:3.11-slim

# --- Configurações Iniciais ---
# Define o modo não interativo para evitar erros de debconf
ENV DEBIAN_FRONTEND=noninteractive

# Desabilita .pyc files e habilita logging em tempo real
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Define a variável CRON para o agendamento
    CRON="0 2 * * *"
# Padrãp: run at 2AM diariamente

# Define o diretório de trabalho
WORKDIR /app

# --- Instalação de Dependências ---
# Instala pacotes do sistema (cron e tzdata) de forma não interativa
RUN apt-get update && \
    apt-get install -y --no-install-recommends cron tzdata && \
    rm -rf /var/lib/apt/lists/*

# Copia e instala dependências Python como root
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    # Atualiza o pip para remover o aviso de nova versão
    && pip install --upgrade pip

# --- Configuração de Segurança e Arquivos ---
# Cria um usuário não-root para segurança
RUN adduser --disabled-password --gecos "" appuser && \
    # Muda a propriedade do diretório para o novo usuário
    chown -R appuser:appuser /app

# Copia o restante dos arquivos do projeto
COPY . .

# Copia e prepara o script de entrada
COPY docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Altera o usuário para o não-root 'appuser'
USER appuser

# Start with the entrypoint script (sets up cron)
ENTRYPOINT ["/entrypoint.sh"]
