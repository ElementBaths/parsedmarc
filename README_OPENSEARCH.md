# OpenSearch/OpenSearch Dashboards Setup for parsedmarc

This guide explains how to visualize your parsedmarc DMARC reports using OpenSearch and OpenSearch Dashboards.

## Overview

parsedmarc has built-in OpenSearch support. When configured with an `[opensearch]` section in `parsedmarc.ini`, it automatically imports DMARC reports directly into OpenSearch during processing.

## Prerequisites

- OpenSearch instance (standalone or Docker)
- OpenSearch Dashboards for visualization (optional)
- parsedmarc configured with OpenSearch settings

## Configuration

### parsedmarc.ini OpenSearch Settings

Add the `[opensearch]` section to your `parsedmarc.ini`:

```ini
[opensearch]
hosts = http://localhost:9200
ssl = False
index_prefix = dmarc
```

For HTTPS connections with authentication:

```ini
[opensearch]
hosts = https://username:password@opensearch.example.com:9200
ssl = True
index_prefix = dmarc
```

### Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `hosts` | OpenSearch URL (include `http://` or `https://`) | Required |
| `ssl` | Enable SSL/TLS | `False` |
| `index_prefix` | Prefix for index names | `dmarc` |

## How It Works

When parsedmarc runs with OpenSearch configured:

1. Fetches DMARC reports from your email source (Gmail, IMAP, etc.)
2. Parses the aggregate and forensic reports
3. Saves to JSON/CSV files locally (if configured)
4. Imports data directly into OpenSearch

Data is stored in daily indices for easy retention management:
- `dmarc_aggregate-YYYY.MM.DD` - Aggregate reports
- `dmarc_forensic-YYYY.MM.DD` - Forensic reports

## Setting Up OpenSearch Dashboards

### 1. Access OpenSearch Dashboards

Open your web browser and navigate to:

```
http://localhost:5601
```

### 2. Create Index Patterns

OpenSearch Dashboards needs index patterns to visualize your data:

1. Go to **Stack Management** → **Index Patterns**
2. Create index pattern for aggregate reports:
   - Pattern: `dmarc_aggregate-*`
   - Time field: `date_begin`
   - Click "Create index pattern"
3. Create index pattern for forensic reports:
   - Pattern: `dmarc_forensic-*`
   - Time field: `arrival_date`
   - Click "Create index pattern"

### 3. Explore Your Data

Navigate to **Discover** to explore your imported DMARC data. You can:

- Filter by domain, source IP, disposition, etc.
- View time-based trends
- Search and analyze specific records

## Creating Dashboards

### Sample Visualizations

Here are some useful visualizations you can create in OpenSearch Dashboards:

1. **Email Volume Over Time**
   - Visualization type: Line chart
   - X-axis: `date_begin` (Date Histogram)
   - Y-axis: Sum of `message_count`

2. **Top Source IPs**
   - Visualization type: Data table
   - Metric: Sum of `message_count`
   - Buckets: Terms aggregation on `source_ip_address`

3. **Disposition Breakdown**
   - Visualization type: Pie chart
   - Slice by: Terms aggregation on `disposition`

4. **SPF/DKIM Alignment Status**
   - Visualization type: Vertical bar chart
   - X-axis: Terms aggregation on `spf_aligned` or `dkim_aligned`
   - Y-axis: Sum of `message_count`

5. **Geographic Distribution**
   - Visualization type: Coordinate map
   - Geo field: `source_country`

6. **Failing Domains**
   - Visualization type: Data table
   - Filter: `passed_dmarc: false`
   - Buckets: Terms on `header_from`

### Saving Dashboards

1. Create individual visualizations in the **Visualize** section
2. Save each visualization with descriptive names
3. Go to **Dashboard** → **Create dashboard**
4. Add your saved visualizations
5. Arrange and resize as needed
6. Save the dashboard

## Index Structure

### Aggregate Reports Index: `dmarc_aggregate-*`

Key fields stored by parsedmarc:

- `xml_schema`: DMARC XML schema version
- `org_name`, `org_email`: Reporting organization
- `report_id`: Unique report identifier
- `date_begin`, `date_end`: Report period
- `domain`: Protected domain (policy published)
- `source_ip_address`: Source IP
- `source_country`: Country code (GeoIP)
- `source_reverse_dns`: Reverse DNS
- `source_base_domain`: Base domain of source
- `message_count`: Number of messages
- `disposition`: DMARC disposition (none, quarantine, reject)
- `spf_aligned`, `dkim_aligned`: Alignment status (boolean)
- `passed_dmarc`: Overall DMARC pass/fail
- `header_from`, `envelope_from`: From addresses
- `dkim_results`, `spf_results`: Detailed authentication results (nested)
- `published_policy`: Full policy details (nested)

### Forensic Reports Index: `dmarc_forensic-*`

Key fields for forensic/failure reports:

- `feedback_type`: Type of feedback
- `arrival_date`: When the message arrived
- `source_ip_address`: Source IP
- `source_country`: Country code
- `authentication_results`: Auth-Results header
- `original_mail_from`: MAIL FROM address
- `subject`: Email subject (if available)
- Headers and body samples (when provided)

## Troubleshooting

### Connection Errors

If parsedmarc can't connect to OpenSearch:

1. Verify OpenSearch is running:
   ```bash
   curl http://localhost:9200
   ```

2. Check the `hosts` URL includes the protocol (`http://` or `https://`)

3. For SSL issues, ensure `ssl = False` for HTTP or `ssl = True` for HTTPS

4. Check firewall rules if OpenSearch is on a remote host

### Index Not Created

If indices aren't being created:

1. Verify the `[opensearch]` section exists in `parsedmarc.ini`
2. Check parsedmarc output for error messages
3. Ensure OpenSearch has write permissions for the index prefix

### Data Not Appearing

If data imports but doesn't appear in Dashboards:

1. Check the time range filter in Dashboards
2. Verify index patterns match the actual index names
3. Refresh the index pattern to pick up new fields

## Data Retention

parsedmarc creates daily indices (`dmarc_aggregate-YYYY.MM.DD`) which makes it easy to:

- Implement retention policies
- Delete old data for GDPR compliance
- Archive historical data

To delete indices older than 90 days:

```bash
curl -X DELETE "localhost:9200/dmarc_aggregate-$(date -d '90 days ago' +%Y.%m.%d)"
```

## Additional Resources

- [OpenSearch Documentation](https://opensearch.org/docs/latest/)
- [OpenSearch Dashboards Documentation](https://opensearch.org/docs/latest/dashboards/index/)
- [parsedmarc Documentation](https://domainaware.github.io/parsedmarc/)
- [parsedmarc OpenSearch Guide](https://domainaware.github.io/parsedmarc/opensearch.html)
