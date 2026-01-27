#!/usr/bin/env python3
"""
Import parsedmarc JSON files into OpenSearch.

This script reads aggregate.json and forensic.json files from the dmarc_reports
directory and imports them into OpenSearch for visualization in OpenSearch Dashboards.
"""

import json
import os
import sys
from datetime import datetime
from typing import List, Dict, Any
from opensearchpy import OpenSearch
from opensearchpy.helpers import bulk
from opensearchpy.helpers.errors import BulkIndexError


def create_opensearch_client(host: str = "localhost", port: int = 9200) -> OpenSearch:
    """Create and return an OpenSearch client."""
    url = f"http://{host}:{port}"
    return OpenSearch(
        [url],
        request_timeout=30,
        max_retries=3,
        retry_on_timeout=True,
        verify_certs=False,
        ssl_show_warn=False
    )


def check_opensearch_connection(es: OpenSearch) -> bool:
    """Check if OpenSearch is accessible."""
    try:
        # Use info() instead of ping() as it's more reliable
        info = es.info()
        print(f"✓ Connected to OpenSearch (cluster: {info['cluster_name']}, version: {info['version']['number']})")
        return True
    except Exception as e:
        print(f"✗ Error connecting to OpenSearch: {e}")
        return False


def create_index_mapping(es: OpenSearch, index_name: str, doc_type: str):
    """Create index with proper mapping for parsedmarc data."""
    if es.indices.exists(index=index_name):
        print(f"  Index {index_name} already exists, skipping mapping creation")
        return
    
    properties = {
        "@timestamp": {"type": "date"},
        "report_id": {"type": "keyword"},
        "report_type": {"type": "keyword"},
        "domain": {"type": "keyword"},
        "begin_date": {"type": "date"},
        "end_date": {"type": "date"},
        "org_name": {"type": "keyword"},
        "org_email": {"type": "keyword"},
        "source_ip": {"type": "ip"},
        "source_reverse_dns": {"type": "keyword"},
        "source_country": {"type": "keyword"},
        "source_base_domain": {"type": "keyword"},
        "source_name": {"type": "keyword"},
        "source_type": {"type": "keyword"},
        "count": {"type": "integer"},
        "spf_aligned": {"type": "boolean"},
        "dkim_aligned": {"type": "boolean"},
        "dmarc_aligned": {"type": "boolean"},
        "disposition": {"type": "keyword"},
        "dkim_result": {"type": "keyword"},
        "spf_result": {"type": "keyword"},
        "header_from": {"type": "keyword"},
        "envelope_from": {"type": "keyword"},
        "envelope_to": {"type": "keyword"},
        "interval_begin": {"type": "date"},
        "interval_end": {"type": "date"},
    }
    
    if doc_type == "forensic":
        # Add forensic-specific fields
        properties.update({
            "arrival_date": {"type": "date"},
            "subject": {"type": "text"},
            "from": {"type": "keyword"},
            "to": {"type": "keyword"},
            "reply_to": {"type": "keyword"},
            "message_id": {"type": "keyword"},
        })
    
    es.indices.create(
        index=index_name,
        mappings={"properties": properties}
    )
    print(f"  Created index {index_name} with mapping")


def normalize_date(date_str: str) -> str:
    """Convert date string to ISO 8601 format for OpenSearch."""
    if not date_str:
        return datetime.now().isoformat()
    try:
        # Try parsing the format "2026-01-10 16:00:00"
        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        return dt.isoformat()
    except ValueError:
        try:
            # Try ISO format already
            datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return date_str
        except ValueError:
            # Fallback to current time
            return datetime.now().isoformat()


def transform_aggregate_record(report: Dict[str, Any], record: Dict[str, Any]) -> Dict[str, Any]:
    """Transform an aggregate report record into an OpenSearch document."""
    # Extract report metadata
    metadata = report.get("report_metadata", {})
    policy = report.get("policy_published", {})
    
    # Extract record data
    source = record.get("source", {})
    alignment = record.get("alignment", {})
    policy_eval = record.get("policy_evaluated", {})
    identifiers = record.get("identifiers", {})
    
    # Build the document
    doc = {
        "@timestamp": normalize_date(metadata.get("begin_date", "")),
        "report_id": metadata.get("report_id"),
        "report_type": "aggregate",
        "domain": policy.get("domain"),
        "begin_date": normalize_date(metadata.get("begin_date", "")),
        "end_date": normalize_date(metadata.get("end_date", "")),
        "org_name": metadata.get("org_name"),
        "org_email": metadata.get("org_email"),
        "source_ip": source.get("ip_address"),
        "source_reverse_dns": source.get("reverse_dns"),
        "source_country": source.get("country"),
        "source_base_domain": source.get("base_domain"),
        "source_name": source.get("name"),
        "source_type": source.get("type"),
        "count": record.get("count", 0),
        "spf_aligned": alignment.get("spf", False),
        "dkim_aligned": alignment.get("dkim", False),
        "dmarc_aligned": alignment.get("dmarc", False),
        "disposition": policy_eval.get("disposition"),
        "dkim_result": policy_eval.get("dkim"),
        "spf_result": policy_eval.get("spf"),
        "header_from": identifiers.get("header_from"),
        "envelope_from": identifiers.get("envelope_from"),
        "envelope_to": identifiers.get("envelope_to"),
        "interval_begin": normalize_date(record.get("interval_begin", "")),
        "interval_end": normalize_date(record.get("interval_end", "")),
    }
    
    # Add full record for reference
    doc["_source_full"] = {
        "report": report,
        "record": record
    }
    
    return doc


def transform_forensic_record(report: Dict[str, Any]) -> Dict[str, Any]:
    """Transform a forensic report into an OpenSearch document."""
    metadata = report.get("report_metadata", {})
    policy = report.get("policy_published", {})
    
    doc = {
        "@timestamp": normalize_date(metadata.get("arrival_date", "")),
        "report_id": metadata.get("report_id"),
        "report_type": "forensic",
        "domain": policy.get("domain"),
        "begin_date": normalize_date(metadata.get("begin_date", "")),
        "end_date": normalize_date(metadata.get("end_date", "")),
        "org_name": metadata.get("org_name"),
        "org_email": metadata.get("org_email"),
        "arrival_date": normalize_date(metadata.get("arrival_date", "")),
        "subject": report.get("subject"),
        "from": report.get("from"),
        "to": report.get("to"),
        "reply_to": report.get("reply_to"),
        "message_id": report.get("message_id"),
        "source_ip": report.get("source_ip"),
        "count": report.get("count", 1),
        "disposition": report.get("disposition"),
        "dkim_result": report.get("dkim", {}).get("result") if isinstance(report.get("dkim"), dict) else None,
        "spf_result": report.get("spf", {}).get("result") if isinstance(report.get("spf"), dict) else None,
    }
    
    # Add full report for reference
    doc["_source_full"] = report
    
    return doc


def load_json_file(json_file: str) -> List[Dict[str, Any]]:
    """Load JSON file, handling multiple arrays or malformed JSON."""
    if not os.path.exists(json_file):
        return []
    
    with open(json_file, 'r') as f:
        content = f.read().strip()
    
    all_reports = []
    
    # Try to parse as a single JSON array first
    try:
        data = json.loads(content)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return [data]
    except json.JSONDecodeError:
        # If parsing fails, the file likely has concatenated arrays
        # Pattern: [{...}], { or [{...}], [{...}]
        # Fix by replacing "],\n  {" with ",\n  {" to merge into single array
        print(f"  Warning: Standard JSON parsing failed, fixing concatenated arrays...")
        
        # Replace pattern: ],\n  { with ,\n  {
        # This merges separate arrays into one
        import re
        # Pattern: closing bracket, comma, newline, whitespace, opening brace
        fixed_content = re.sub(r'\],\s*\n\s*\{', r',\n  {', content)
        
        # Also handle ],\n  [ pattern (array followed by array)
        fixed_content = re.sub(r'\],\s*\n\s*\[', r',\n  [', fixed_content)
        
        # Try parsing the fixed content
        try:
            data = json.loads(fixed_content)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return [data]
        except json.JSONDecodeError:
            # If still fails, try parsing as multiple separate JSON arrays
            # Split on "],\n" followed by whitespace and "{"
            parts = re.split(r'\],\s*\n\s*\{', content)
            if len(parts) > 1:
                # First part should end with ]
                parts[0] = parts[0].rstrip() + ']'
                # Subsequent parts should be wrapped as objects in arrays
                for i in range(1, len(parts)):
                    parts[i] = '[{' + parts[i]
                    if not parts[i].rstrip().endswith(']'):
                        parts[i] = parts[i].rstrip() + ']}'
                
                # Parse each part
                for part in parts:
                    part = part.strip()
                    if not part:
                        continue
                    try:
                        data = json.loads(part)
                        if isinstance(data, list):
                            all_reports.extend(data)
                        elif isinstance(data, dict):
                            all_reports.append(data)
                    except json.JSONDecodeError:
                        continue
    
    return all_reports


def import_aggregate_reports(es: OpenSearch, json_file: str, index_prefix: str = "dmarc-aggregate"):
    """Import aggregate reports from JSON file."""
    if not os.path.exists(json_file):
        print(f"  File {json_file} not found, skipping")
        return 0
    
    print(f"\nImporting aggregate reports from {json_file}...")
    
    reports = load_json_file(json_file)
    
    if not isinstance(reports, list) or len(reports) == 0:
        print("  No reports found in file")
        return 0
    
    print(f"  Loaded {len(reports)} reports from file")
    
    # Generate index name based on date from first report
    first_report = reports[0]
    begin_date = first_report.get("report_metadata", {}).get("begin_date", "")
    if begin_date:
        try:
            date_obj = datetime.strptime(begin_date.split()[0], "%Y-%m-%d")
            index_name = f"{index_prefix}-{date_obj.strftime('%Y.%m')}"
        except:
            index_name = f"{index_prefix}-{datetime.now().strftime('%Y.%m')}"
    else:
        index_name = f"{index_prefix}-{datetime.now().strftime('%Y.%m')}"
    
    create_index_mapping(es, index_name, "aggregate")
    
    # Transform and prepare documents
    actions = []
    for report in reports:
        records = report.get("records", [])
        for record in records:
            doc = transform_aggregate_record(report, record)
            actions.append({
                "_index": index_name,
                "_source": doc
            })
    
    if not actions:
        print("  No records to import")
        return 0
    
    # Bulk index
    print(f"  Indexing {len(actions)} records...")
    try:
        # Use options() to avoid deprecation warning
        success, failed = bulk(es.options(request_timeout=60), actions, chunk_size=500, raise_on_error=False)
        print(f"  ✓ Successfully indexed {success} documents")
        if failed:
            print(f"  ✗ Failed to index {len(failed)} documents")
            # Show first few errors for debugging
            for i, error_info in enumerate(failed[:3]):
                error = error_info.get('index', {}).get('error', {})
                print(f"    Error {i+1}: {error.get('type', 'unknown')} - {error.get('reason', 'unknown reason')}")
                if i == 2 and len(failed) > 3:
                    print(f"    ... and {len(failed) - 3} more errors")
                    break
        return success
    except BulkIndexError as e:
        print(f"  ✗ Bulk indexing error: {len(e.errors)} document(s) failed")
        # Show first few errors
        for i, error_info in enumerate(e.errors[:3]):
            error = error_info.get('index', {}).get('error', {})
            print(f"    Error {i+1}: {error.get('type', 'unknown')} - {error.get('reason', 'unknown reason')}")
        return 0
    except Exception as e:
        print(f"  ✗ Error during bulk indexing: {e}")
        import traceback
        traceback.print_exc()
        return 0


def import_forensic_reports(es: OpenSearch, json_file: str, index_prefix: str = "dmarc-forensic"):
    """Import forensic reports from JSON file."""
    if not os.path.exists(json_file):
        print(f"  File {json_file} not found, skipping")
        return 0
    
    print(f"\nImporting forensic reports from {json_file}...")
    
    reports = load_json_file(json_file)
    
    if not isinstance(reports, list) or len(reports) == 0:
        print("  No reports found in file")
        return 0
    
    print(f"  Loaded {len(reports)} reports from file")
    
    # Generate index name based on date from first report
    first_report = reports[0]
    begin_date = first_report.get("report_metadata", {}).get("begin_date", "")
    if begin_date:
        try:
            date_obj = datetime.strptime(begin_date.split()[0], "%Y-%m-%d")
            index_name = f"{index_prefix}-{date_obj.strftime('%Y.%m')}"
        except:
            index_name = f"{index_prefix}-{datetime.now().strftime('%Y.%m')}"
    else:
        index_name = f"{index_prefix}-{datetime.now().strftime('%Y.%m')}"
    
    create_index_mapping(es, index_name, "forensic")
    
    # Transform and prepare documents
    actions = []
    for report in reports:
        doc = transform_forensic_record(report)
        actions.append({
            "_index": index_name,
            "_source": doc
        })
    
    if not actions:
        print("  No reports to import")
        return 0
    
    # Bulk index
    print(f"  Indexing {len(actions)} reports...")
    try:
        # Use options() to avoid deprecation warning
        success, failed = bulk(es.options(request_timeout=60), actions, chunk_size=500, raise_on_error=False)
        print(f"  ✓ Successfully indexed {success} documents")
        if failed:
            print(f"  ✗ Failed to index {len(failed)} documents")
            # Show first few errors for debugging
            for i, error_info in enumerate(failed[:3]):
                error = error_info.get('index', {}).get('error', {})
                print(f"    Error {i+1}: {error.get('type', 'unknown')} - {error.get('reason', 'unknown reason')}")
                if i == 2 and len(failed) > 3:
                    print(f"    ... and {len(failed) - 3} more errors")
                    break
        return success
    except BulkIndexError as e:
        print(f"  ✗ Bulk indexing error: {len(e.errors)} document(s) failed")
        # Show first few errors
        for i, error_info in enumerate(e.errors[:3]):
            error = error_info.get('index', {}).get('error', {})
            print(f"    Error {i+1}: {error.get('type', 'unknown')} - {error.get('reason', 'unknown reason')}")
        return 0
    except Exception as e:
        print(f"  ✗ Error during bulk indexing: {e}")
        import traceback
        traceback.print_exc()
        return 0


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Import parsedmarc JSON files into OpenSearch")
    parser.add_argument(
        "--host",
        default="localhost",
        help="OpenSearch host (default: localhost)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=9200,
        help="OpenSearch port (default: 9200)"
    )
    parser.add_argument(
        "--aggregate-file",
        default="./dmarc_reports/aggregate.json",
        help="Path to aggregate.json file (default: ./dmarc_reports/aggregate.json)"
    )
    parser.add_argument(
        "--forensic-file",
        default="./dmarc_reports/forensic.json",
        help="Path to forensic.json file (default: ./dmarc_reports/forensic.json)"
    )
    
    args = parser.parse_args()
    
    print("parsedmarc OpenSearch Import Tool")
    print("=" * 50)
    
    # Create OpenSearch client
    es = create_opensearch_client(args.host, args.port)
    
    # Check connection
    if not check_opensearch_connection(es):
        print("\nMake sure OpenSearch is running:")
        print("  docker-compose up -d")
        sys.exit(1)
    
    # Import aggregate reports
    aggregate_count = import_aggregate_reports(es, args.aggregate_file)
    
    # Import forensic reports
    forensic_count = import_forensic_reports(es, args.forensic_file)
    
    # Summary
    print("\n" + "=" * 50)
    print("Import Summary:")
    print(f"  Aggregate records: {aggregate_count}")
    print(f"  Forensic reports: {forensic_count}")
    print(f"  Total: {aggregate_count + forensic_count}")
    print("\nAccess OpenSearch Dashboards at: http://localhost:5601")


if __name__ == "__main__":
    main()
