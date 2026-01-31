# Docker Setup for ParseDmarc

This project runs inside a Docker container with hourly cron execution, automatic failure notifications via Postmark, centralized logging, OpenSearch integration for DMARC report visualization, and AI-powered classification of DMARC failures using Claude.

## Prerequisites

- Docker and Docker Compose installed
- Postmark API token (for failure notifications)
- Gmail API credentials (`credentials.json` and `token.pickle`)
- OpenSearch instance accessible from the container
- Anthropic API key (optional, for AI classification of DMARC failures)

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

### 3. Configure AI Classification (Optional)

The system can automatically classify DMARC failures using Claude AI. After each parsedmarc import, failures are analyzed and tagged with:

- **Status**: `OK`, `ATTENTION`, or `CRITICAL`
- **Classification**: `LEGITIMATE_SERVICE`, `FORWARDING`, `SPOOFING`, `INTERNAL_CONFIG`, or `UNKNOWN`
- **Failure details**: Specific explanations for SPF/DKIM/alignment failures
- **Recommended action**: Actionable next steps

#### Getting an Anthropic API Key

1. Create an account at [console.anthropic.com](https://console.anthropic.com/)
2. Navigate to **API Keys** in the dashboard
3. Click **Create Key** and give it a descriptive name
4. Copy the key (starts with `sk-ant-`)

**Pricing**: Claude API usage is pay-per-token. The `claude-sonnet-4-20250514` model costs approximately $3 per million input tokens and $15 per million output tokens. For typical DMARC classification (a few hundred failures per day), expect costs under $1/month.

#### Setting the API Key

Create a `.env` file in the project directory:

```bash
ANTHROPIC_API_KEY=sk-ant-your-api-key-here
```

Then update `docker-compose.yml` to load the environment variable:

```yaml
services:
  parsedmarc-processor:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: parsedmarc-processor
    env_file:
      - .env
    volumes:
      # ... existing volumes
```

Alternatively, set it directly in `docker-compose.yml`:

```yaml
services:
  parsedmarc-processor:
    environment:
      - ANTHROPIC_API_KEY=sk-ant-your-api-key-here
```

**Note**: If `ANTHROPIC_API_KEY` is not set, the AI classification step is skipped silently. The parsedmarc import will still run normally.

#### OpenSearch Environment Variables

The classification script uses these environment variables (with defaults):

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENSEARCH_HOST` | `localhost` | OpenSearch hostname |
| `OPENSEARCH_PORT` | `9200` | OpenSearch port |
| `OPENSEARCH_INDEX_PREFIX` | `dmarc_aggregate` | Index prefix for DMARC data |

### 4. Create Logs Directory

The logs directory will be created automatically, but you can create it manually:

```bash
mkdir -p logs
```

### 5. Build and Start

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
Jan 27 14:00:15 parsedmarc-processor wrapper.sh[1234]: [info] Starting AI classification of DMARC failures
Jan 27 14:00:25 parsedmarc-processor wrapper.sh[1234]: [info] AI classification completed successfully
Jan 27 14:00:25 parsedmarc-processor wrapper.sh[1234]: [info] ========== CLASSIFICATION SUMMARY ==========
Jan 27 14:00:25 parsedmarc-processor wrapper.sh[1234]: [info] Classification complete
Jan 27 14:00:25 parsedmarc-processor wrapper.sh[1234]: [info]   Processed: 5
Jan 27 14:00:25 parsedmarc-processor wrapper.sh[1234]: [info]   OK: 3
Jan 27 14:00:25 parsedmarc-processor wrapper.sh[1234]: [info]   Attention: 2
Jan 27 14:00:25 parsedmarc-processor wrapper.sh[1234]: [info]   Critical: 0
Jan 27 14:00:25 parsedmarc-processor wrapper.sh[1234]: [info]   Errors: 0
Jan 27 14:00:25 parsedmarc-processor wrapper.sh[1234]: [info] ========== END CLASSIFICATION ==========
Jan 27 14:00:25 parsedmarc-processor wrapper.sh[1234]: [info] Process completed at 2026-01-27 14:00:25 UTC
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

### AI classification not running

1. Verify `ANTHROPIC_API_KEY` is set:
   ```bash
   docker-compose exec parsedmarc-processor printenv ANTHROPIC_API_KEY
   ```

2. Check that the API key is valid at [console.anthropic.com](https://console.anthropic.com/)

3. If you see "ANTHROPIC_API_KEY not set - skipping AI classification" in logs, ensure the `.env` file exists and `docker-compose.yml` includes `env_file: - .env`

4. Check for rate limiting errors in the logs - Anthropic has per-minute request limits

### AI classification errors

1. Check the classification output in logs for specific errors:
   ```bash
   grep -i "classify" logs/app.log | tail -20
   ```

2. Run the classification script manually for debugging:
   ```bash
   docker-compose exec parsedmarc-processor python3 /app/classify_dmarc_failures.py
   ```

3. Verify OpenSearch connectivity from the classification script:
   ```bash
   docker-compose exec parsedmarc-processor python3 -c "from opensearchpy import OpenSearch; c = OpenSearch([{'host': 'localhost', 'port': 9200}]); print(c.info())"
   ```

## File Structure

```
.
├── Dockerfile                     # Container definition
├── docker-compose.yml             # Service orchestration
├── docker-entrypoint.sh           # Container startup script
├── wrapper.sh                     # Main wrapper script with monitoring
├── crontab                        # Cron schedule configuration
├── process_and_import.py          # DMARC report processing script
├── classify_dmarc_failures.py     # AI classification script
├── postmark.conf.example          # Postmark config template
├── postmark.conf                  # Postmark config (not in git)
├── parsedmarc.ini                 # parsedmarc configuration
├── .env                           # Environment variables including ANTHROPIC_API_KEY (not in git)
├── logs/                          # Log directory (mounted volume)
│   └── app.log                    # Application logs
└── dmarc_reports/                 # Parsed DMARC reports (mounted volume)
```

## Stopping Services

```bash
docker-compose down
```
