# OpenSearch/OpenSearch Dashboards Setup for parsedmarc

This guide explains how to set up OpenSearch and OpenSearch Dashboards using Docker to visualize your parsedmarc DMARC reports.

## Prerequisites

- Docker and Docker Compose installed on your system
- Python 3.6+ with `opensearch-py` package installed
- Existing parsedmarc JSON files in `dmarc_reports/` directory

## Installation

### 1. Install Python Dependencies

Create a virtual environment and install the required Python package:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Or install directly:

```bash
python3 -m venv venv
source venv/bin/activate
pip install opensearch-py
```

**Note**: Always activate the virtual environment before running the import script:
```bash
source venv/bin/activate
```

### 2. Start OpenSearch and OpenSearch Dashboards

Start the Docker containers:

```bash
docker-compose up -d
```

This will start:
- **OpenSearch** on port 9200
- **OpenSearch Dashboards** on port 5601

Wait for the services to be healthy (about 1-2 minutes). You can check the status with:

```bash
docker-compose ps
```

Verify OpenSearch is running:

```bash
curl http://localhost:9200
```

### 3. Import Existing Data

Make sure your virtual environment is activated, then import your existing parsedmarc JSON files into OpenSearch:

```bash
source venv/bin/activate
python3 import_to_opensearch.py
```

The script will:
- Connect to OpenSearch
- Create appropriate index mappings
- Import aggregate reports from `dmarc_reports/aggregate.json`
- Import forensic reports from `dmarc_reports/forensic.json`

You can customize the import with command-line options:

```bash
python3 import_to_opensearch.py --host localhost --port 9200 \
  --aggregate-file ./dmarc_reports/aggregate.json \
  --forensic-file ./dmarc_reports/forensic.json
```

## Configuring OpenSearch Dashboards

### 1. Access OpenSearch Dashboards

Open your web browser and navigate to:

```
http://localhost:5601
```

### 2. Create Index Patterns

OpenSearch Dashboards needs index patterns to visualize your data:

1. Go to **Stack Management** → **Index Patterns** (or click "Create index pattern")
2. Create index pattern for aggregate reports:
   - Pattern: `dmarc-aggregate-*`
   - Time field: `@timestamp`
   - Click "Create index pattern"
3. Create index pattern for forensic reports:
   - Pattern: `dmarc-forensic-*`
   - Time field: `@timestamp`
   - Click "Create index pattern"

### 3. Explore Your Data

Navigate to **Discover** to explore your imported DMARC data. You can:

- Filter by domain, source IP, disposition, etc.
- View time-based trends
- Search and analyze specific records

## Future Reports

With the OpenSearch configuration added to `parsedmarc.ini`, future parsedmarc runs will automatically send data to OpenSearch:

```ini
[opensearch]
hosts = localhost:9200
save_aggregate = True
save_forensic = True
index_prefix = dmarc
ssl_enabled = False
```

When you run parsedmarc (e.g., `parsedmarc -c parsedmarc.ini`), it will:
- Continue saving JSON/CSV files locally
- Also send data directly to OpenSearch
- Create indices automatically with date-based naming

## Creating Dashboards

### Sample Visualizations

Here are some useful visualizations you can create in OpenSearch Dashboards:

1. **Email Volume Over Time**
   - Visualization type: Line chart
   - X-axis: `@timestamp` (Date Histogram)
   - Y-axis: Count

2. **Top Source IPs**
   - Visualization type: Data table
   - Metric: Count
   - Buckets: Terms aggregation on `source_ip`

3. **Disposition Breakdown**
   - Visualization type: Pie chart
   - Slice by: Terms aggregation on `disposition`

4. **SPF/DKIM Alignment Status**
   - Visualization type: Vertical bar chart
   - X-axis: Terms aggregation on `spf_aligned` or `dkim_aligned`
   - Y-axis: Count

5. **Geographic Distribution**
   - Visualization type: Coordinate map
   - Geo field: `source_country`

### Saving Dashboards

1. Create individual visualizations in the **Visualize** section
2. Save each visualization with descriptive names
3. Go to **Dashboard** → **Create dashboard**
4. Add your saved visualizations
5. Arrange and resize as needed
6. Save the dashboard

## Troubleshooting

### OpenSearch Not Starting

If OpenSearch fails to start, check:

```bash
docker-compose logs opensearch
```

Common issues:
- **Memory**: Ensure Docker has at least 2GB RAM allocated
- **Port conflicts**: Make sure ports 9200 and 5601 are not in use
- **Permissions**: On Linux, you may need to adjust `vm.max_map_count`:
  ```bash
  sudo sysctl -w vm.max_map_count=262144
  ```

### Import Script Errors

If the import script fails:

1. Verify OpenSearch is running:
   ```bash
   curl http://localhost:9200
   ```

2. Check the script output for specific error messages

3. Ensure JSON files exist and are valid:
   ```bash
   python3 -m json.tool dmarc_reports/aggregate.json > /dev/null
   ```

### OpenSearch Dashboards Can't Connect to OpenSearch

If OpenSearch Dashboards shows connection errors:

1. Check that OpenSearch is healthy:
   ```bash
   docker-compose ps
   ```

2. Verify network connectivity:
   ```bash
   docker-compose exec opensearch-dashboards curl http://opensearch:9200
   ```

3. Restart both services:
   ```bash
   docker-compose restart
   ```

## Stopping the Services

To stop OpenSearch and OpenSearch Dashboards:

```bash
docker-compose down
```

To stop and remove all data (volumes):

```bash
docker-compose down -v
```

**Warning**: The `-v` flag will delete all indexed data. Use with caution.

## Data Persistence

Data is persisted in Docker volumes. To backup your OpenSearch data:

```bash
docker run --rm -v parsedmarc_opensearch_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/opensearch-backup.tar.gz -C /data .
```

To restore:

```bash
docker run --rm -v parsedmarc_opensearch_data:/data -v $(pwd):/backup \
  alpine tar xzf /backup/opensearch-backup.tar.gz -C /data
```

## Additional Resources

- [OpenSearch Documentation](https://opensearch.org/docs/latest/)
- [OpenSearch Dashboards Documentation](https://opensearch.org/docs/latest/dashboards/index/)
- [parsedmarc Documentation](https://domainaware.github.io/parsedmarc/)

## Index Structure

### Aggregate Reports Index: `dmarc-aggregate-*`

Each document represents a single record from an aggregate report:

- `@timestamp`: Report begin date
- `report_id`: Unique report identifier
- `domain`: Protected domain
- `source_ip`: Source IP address
- `source_country`: Country code
- `count`: Number of messages
- `disposition`: DMARC disposition (none, quarantine, reject)
- `spf_result`, `dkim_result`: Authentication results
- `spf_aligned`, `dkim_aligned`, `dmarc_aligned`: Alignment status
- `interval_begin`, `interval_end`: Time range for the record

### Forensic Reports Index: `dmarc-forensic-*`

Each document represents a single forensic report:

- `@timestamp`: Arrival date
- `report_id`: Unique report identifier
- `domain`: Protected domain
- `subject`: Email subject
- `from`, `to`: Email addresses
- `source_ip`: Source IP address
- `disposition`: DMARC disposition
- `arrival_date`: When the message arrived

Both indices include a `_source_full` field containing the complete original report/record data for reference.
