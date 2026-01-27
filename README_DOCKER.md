# Docker Setup for ParseDmarc

This project runs inside a Docker container with hourly cron execution, automatic failure notifications via Postmark, centralized logging, and OpenSearch integration for DMARC report visualization.

## Prerequisites

- Docker and Docker Compose installed
- Postmark API token (for failure notifications)
- Gmail API credentials (`credentials.json` and `token.pickle`)
- OpenSearch instance accessible from the container

## Setup

### 1. Configure Postmark

Copy the example configuration file and fill in your Postmark credentials:

```bash
cp postmark.conf.example postmark.conf
```

Edit `postmark.conf` with your Postmark API token and email addresses:

```bash
POSTMARK_API_TOKEN=your_postmark_api_token_here
POSTMARK_FROM_EMAIL=noreply@yourdomain.com
POSTMARK_TO_EMAIL=admin@yourdomain.com
```

**Note:** The `POSTMARK_FROM_EMAIL` must be a verified sender in your Postmark account.

### 2. Configure OpenSearch

Edit `parsedmarc.ini` to set your OpenSearch host:

```ini
[opensearch]
hosts = http://your-opensearch-host:9200
ssl = False
index_prefix = dmarc
```

For HTTPS connections:
```ini
[opensearch]
hosts = https://your-opensearch-host:9200
ssl = True
index_prefix = dmarc
```

### 3. Create Logs Directory

The logs directory will be created automatically, but you can create it manually:

```bash
mkdir -p logs
```

### 4. Build and Start

Build the Docker image:

```bash
docker-compose build parsedmarc-processor
```

Start the service:

```bash
docker-compose up -d
```

## Monitoring

### View Logs

Logs are written to `./logs/app.log` on the host:

```bash
tail -f logs/app.log
```

### Check Container Status

```bash
docker-compose ps parsedmarc-processor
```

### View Container Logs

```bash
docker-compose logs -f parsedmarc-processor
```

### Manual Execution

To manually trigger the wrapper script (useful for testing):

```bash
docker-compose exec parsedmarc-processor /app/wrapper.sh
```

## Cron Schedule

The wrapper script runs automatically every hour at minute 0 (e.g., 1:00, 2:00, 3:00, etc.).

To modify the schedule, edit the `crontab` file and rebuild the image.

## Log Format

Logs follow syslog format with detailed output.

### Success Example

```
Jan 27 14:00:01 parsedmarc-processor wrapper.sh[1234]: [info] Process started at 2026-01-27 14:00:01 UTC
Jan 27 14:00:15 parsedmarc-processor wrapper.sh[1234]: [info] process_and_import.py completed successfully (exit code: 0)
Jan 27 14:00:15 parsedmarc-processor wrapper.sh[1234]: [info] Output: 25 lines
Jan 27 14:00:15 parsedmarc-processor wrapper.sh[1234]: [info] ========== OUTPUT SUMMARY ==========
Jan 27 14:00:15 parsedmarc-processor wrapper.sh[1234]: [info] ✓ parsedmarc completed successfully
Jan 27 14:00:15 parsedmarc-processor wrapper.sh[1234]: [info] Pipeline completed successfully!
Jan 27 14:00:15 parsedmarc-processor wrapper.sh[1234]: [info] ✓ DMARC reports processed from Gmail
Jan 27 14:00:15 parsedmarc-processor wrapper.sh[1234]: [info] ✓ Reports imported into OpenSearch
Jan 27 14:00:15 parsedmarc-processor wrapper.sh[1234]: [info] ========== END SUMMARY ==========
Jan 27 14:00:15 parsedmarc-processor wrapper.sh[1234]: [info] Process completed at 2026-01-27 14:00:15 UTC
```

### Failure Example (with full output and stack trace)

```
Jan 27 15:00:01 parsedmarc-processor wrapper.sh[1234]: [info] Process started at 2026-01-27 15:00:01 UTC
Jan 27 15:00:25 parsedmarc-processor wrapper.sh[1234]: [error] process_and_import.py failed with exit code: 1
Jan 27 15:00:25 parsedmarc-processor wrapper.sh[1234]: [error] ========== BEGIN FULL OUTPUT ==========
Jan 27 15:00:25 parsedmarc-processor wrapper.sh[1234]: [error] DMARC Processing Pipeline
Jan 27 15:00:25 parsedmarc-processor wrapper.sh[1234]: [error] ============================================================
Jan 27 15:00:25 parsedmarc-processor wrapper.sh[1234]: [error] Processing DMARC reports from Gmail
Jan 27 15:00:25 parsedmarc-processor wrapper.sh[1234]: [error] Traceback (most recent call last):
Jan 27 15:00:25 parsedmarc-processor wrapper.sh[1234]: [error]   File "/usr/local/lib/python3.11/site-packages/parsedmarc/__init__.py", line 123, in fetch
Jan 27 15:00:25 parsedmarc-processor wrapper.sh[1234]: [error]     raise AuthenticationError("Invalid credentials")
Jan 27 15:00:25 parsedmarc-processor wrapper.sh[1234]: [error] parsedmarc.errors.AuthenticationError: Invalid credentials
Jan 27 15:00:25 parsedmarc-processor wrapper.sh[1234]: [error] ✗ parsedmarc failed with exit code 1
Jan 27 15:00:25 parsedmarc-processor wrapper.sh[1234]: [error] ========== END FULL OUTPUT ==========
Jan 27 15:00:25 parsedmarc-processor wrapper.sh[1234]: [info] Process completed at 2026-01-27 15:00:25 UTC
Jan 27 15:00:26 parsedmarc-processor wrapper.sh[1234]: [info] Failure email sent via Postmark API
```

## Troubleshooting

### Container won't start

Check that all required files are present:
- `credentials.json`
- `token.pickle`
- `parsedmarc.ini`
- `postmark.conf`

### Cron not running

Check cron logs:
```bash
docker-compose exec parsedmarc-processor cat /var/log/cron.log
```

Verify cron is installed and running:
```bash
docker-compose exec parsedmarc-processor ps aux | grep cron
```

### Email notifications not working

1. Verify `postmark.conf` is mounted correctly:
   ```bash
   docker-compose exec parsedmarc-processor cat /app/postmark.conf
   ```

2. Check wrapper script logs for Postmark API errors

3. Verify Postmark API token is valid and sender email is verified

### OpenSearch connection issues

1. Verify OpenSearch is accessible from the container:
   ```bash
   docker-compose exec parsedmarc-processor curl http://your-opensearch-host:9200
   ```

2. Check that `parsedmarc.ini` has the correct `[opensearch]` settings

3. For SSL issues, ensure `ssl = False` for HTTP or `ssl = True` for HTTPS

## File Structure

```
.
├── Dockerfile                 # Container definition
├── docker-compose.yml         # Service orchestration
├── docker-entrypoint.sh      # Container startup script
├── wrapper.sh                # Main wrapper script with monitoring
├── crontab                   # Cron schedule configuration
├── postmark.conf.example     # Postmark config template
├── postmark.conf             # Postmark config (not in git)
├── parsedmarc.ini            # parsedmarc configuration (includes OpenSearch settings)
├── logs/                     # Log directory (mounted volume)
│   └── app.log              # Application logs
└── dmarc_reports/           # Parsed DMARC reports (mounted volume)
```

## Stopping Services

```bash
docker-compose down
```
