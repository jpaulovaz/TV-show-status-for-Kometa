# Use a slim Python image as the base
FROM python:3.13.7-slim

# Disable .pyc files and enable real-time logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Define a variável CRON para o agendamento
ARG CRON="0 2 * * *" 

# Set working directory
WORKDIR /app

# Install cron and tzdata (timezone handling if needed)
RUN apt-get update && \
    apt-get install -y --no-install-recommends cron tzdata && \
    rm -rf /var/lib/apt/lists/*

# Copy only what we need
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy remaining app files
COPY . .

# Copy and prepare the entrypoint
COPY docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Start with the entrypoint script (sets up cron)
ENTRYPOINT ["/entrypoint.sh"]