#!/bin/bash
# Docker entrypoint script to start cron and rsyslog

set -e

# Start rsyslog daemon
rsyslogd

# Ensure log file exists and has proper permissions
touch /logs/app.log
chmod 666 /logs/app.log

# Start cron in foreground mode
exec cron -f
