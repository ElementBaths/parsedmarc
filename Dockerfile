FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    cron \
    curl \
    rsyslog \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY process_and_import.py .
COPY wrapper.sh .
COPY docker-entrypoint.sh .

# Make scripts executable
RUN chmod +x wrapper.sh docker-entrypoint.sh

# Create logs directory
RUN mkdir -p /logs && chmod 777 /logs

# Copy cron configuration
COPY crontab /etc/cron.d/parsedmarc-cron
RUN chmod 0644 /etc/cron.d/parsedmarc-cron && \
    crontab /etc/cron.d/parsedmarc-cron

# Configure rsyslog to write to /logs/app.log
RUN echo "local0.* /logs/app.log" >> /etc/rsyslog.conf && \
    echo "& stop" >> /etc/rsyslog.conf && \
    touch /logs/app.log && chmod 666 /logs/app.log || true

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Entrypoint script starts cron and rsyslog
ENTRYPOINT ["/app/docker-entrypoint.sh"]
