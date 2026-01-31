#!/usr/bin/env python3
"""
Classify DMARC failures using Claude AI.

This script queries OpenSearch for unclassified DMARC failures,
uses Claude to analyze and classify each failure, and updates
the documents with AI analysis results.

Runs after parsedmarc import via wrapper.sh cron job.
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

import anthropic
from opensearchpy import OpenSearch

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Constants
OPENSEARCH_HOST = os.environ.get('OPENSEARCH_HOST', '192.168.1.111')
OPENSEARCH_PORT = int(os.environ.get('OPENSEARCH_PORT', '9200'))
OPENSEARCH_USER = os.environ.get('OPENSEARCH_USER', 'admin')
OPENSEARCH_PASSWORD = os.environ.get('OPENSEARCH_PASSWORD', '')
OPENSEARCH_SSL = os.environ.get('OPENSEARCH_SSL', 'true').lower() in ('true', '1', 'yes')
OPENSEARCH_INDEX_PREFIX = os.environ.get('OPENSEARCH_INDEX_PREFIX', 'dmarcdmarc_aggregate')
CLAUDE_MODEL = 'claude-sonnet-4-20250514'
LOOKBACK_DAYS = 30
BATCH_SIZE = 100


def get_opensearch_client() -> OpenSearch:
    """Create and return an OpenSearch client."""
    # Build auth tuple if credentials provided
    http_auth = None
    if OPENSEARCH_USER and OPENSEARCH_PASSWORD:
        http_auth = (OPENSEARCH_USER, OPENSEARCH_PASSWORD)
    
    return OpenSearch(
        hosts=[{'host': OPENSEARCH_HOST, 'port': OPENSEARCH_PORT}],
        http_auth=http_auth,
        http_compress=True,
        use_ssl=OPENSEARCH_SSL,
        verify_certs=False,
        ssl_show_warn=False,
    )


def get_anthropic_client() -> anthropic.Anthropic:
    """Create and return an Anthropic client."""
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is required")
    return anthropic.Anthropic(api_key=api_key)


def query_unclassified_failures(client: OpenSearch) -> list[dict[str, Any]]:
    """
    Query OpenSearch for DMARC records with authentication issues that haven't been classified yet.
    
    Returns documents where:
    - passed_dmarc is false, OR
    - spf_aligned is false, OR
    - dkim_aligned is false
    - AND ai_analysis field does not exist
    - AND within the last LOOKBACK_DAYS days
    
    This catches partial failures (e.g., DKIM fails but SPF passes) that may need attention.
    """
    # Calculate date range
    now = datetime.now(timezone.utc)
    lookback_date = now - timedelta(days=LOOKBACK_DAYS)
    
    # Build index pattern for date-based indices
    index_pattern = f"{OPENSEARCH_INDEX_PREFIX}-*"
    
    query = {
        "size": BATCH_SIZE,
        "query": {
            "bool": {
                "should": [
                    {"term": {"passed_dmarc": False}},
                    {"term": {"spf_aligned": False}},
                    {"term": {"dkim_aligned": False}}
                ],
                "minimum_should_match": 1,
                "must_not": [
                    {"exists": {"field": "ai_analysis"}}
                ],
                "filter": [
                    {
                        "range": {
                            "date_begin": {
                                "gte": lookback_date.strftime("%Y-%m-%dT%H:%M:%SZ")
                            }
                        }
                    }
                ]
            }
        },
        "_source": True
    }
    
    try:
        response = client.search(index=index_pattern, body=query)
        hits = response.get('hits', {}).get('hits', [])
        logger.info(f"Found {len(hits)} unclassified DMARC records with authentication issues")
        return hits
    except Exception as e:
        logger.error(f"Error querying OpenSearch: {e}")
        return []


def build_classification_prompt(doc: dict[str, Any]) -> str:
    """Build the prompt for Claude to classify a DMARC record with authentication issues."""
    source = doc.get('_source', {})
    
    # Extract relevant fields
    source_ip = source.get('source_ip_address', 'Unknown')
    source_country = source.get('source_country', 'Unknown')
    source_reverse_dns = source.get('source_reverse_dns', 'Unknown')
    source_base_domain = source.get('source_base_domain', 'Unknown')
    header_from = source.get('header_from', 'Unknown')
    envelope_from = source.get('envelope_from', 'Unknown')
    message_count = source.get('message_count', 0)
    disposition = source.get('disposition', 'Unknown')
    passed_dmarc = source.get('passed_dmarc', False)
    spf_aligned = source.get('spf_aligned', False)
    dkim_aligned = source.get('dkim_aligned', False)
    spf_results = source.get('spf_results', [])
    dkim_results = source.get('dkim_results', [])
    org_name = source.get('org_name', 'Unknown')
    
    prompt = f"""Analyze this DMARC report and classify it. This record has authentication issues that may need attention.

## DMARC Report Details

**Source Information:**
- IP Address: {source_ip}
- Reverse DNS: {source_reverse_dns}
- Base Domain: {source_base_domain}
- Country: {source_country}

**Email Headers:**
- Header From: {header_from}
- Envelope From: {envelope_from}

**Authentication Results:**
- DMARC Passed: {passed_dmarc}
- SPF Aligned: {spf_aligned}
- DKIM Aligned: {dkim_aligned}
- Disposition: {disposition}
- Message Count: {message_count}

**SPF Results:** {json.dumps(spf_results, indent=2) if spf_results else 'None'}

**DKIM Results:** {json.dumps(dkim_results, indent=2) if dkim_results else 'None'}

**Reporting Organization:** {org_name}

## Classification Task

Note: This record may have passed DMARC overall but still has SPF or DKIM issues worth reviewing.

Classify this record into one of these categories:
- LEGITIMATE_SERVICE: Known service (Google, Microsoft, Mailchimp, SendGrid, etc.) sending on behalf of the domain but not fully configured in DNS
- FORWARDING: Email was forwarded by recipient's mail server, breaking SPF/DKIM alignment
- SPOOFING: Likely malicious - unauthorized sender impersonating the domain
- INTERNAL_CONFIG: Domain's own infrastructure is misconfigured (missing DNS records, key rotation issues)
- UNKNOWN: Insufficient data to classify confidently

Determine the appropriate status:
- OK: No action needed - forwarding, legitimate service working correctly, or minor issue with no security impact
- ATTENTION: Config issues worth fixing, or services that should be added to DNS for better deliverability
- CRITICAL: Potential spoofing or high-volume failures requiring immediate review

Respond with a JSON object containing:
{{
    "status": "OK|ATTENTION|CRITICAL",
    "classification": "LEGITIMATE_SERVICE|FORWARDING|SPOOFING|INTERNAL_CONFIG|UNKNOWN",
    "confidence": 0.0-1.0,
    "summary": "One-line summary for dashboards",
    "failure_details": {{
        "spf": "Explanation of SPF status and any issues",
        "dkim": "Explanation of DKIM status and any issues",
        "alignment": "Explanation of alignment status"
    }},
    "recommended_action": "Specific actionable next step or 'No action needed' if OK",
    "risk_level": "low|medium|high"
}}

Respond ONLY with the JSON object, no additional text."""

    return prompt


def classify_failure(client: anthropic.Anthropic, doc: dict[str, Any]) -> dict[str, Any] | None:
    """
    Use Claude to classify a DMARC failure document.
    
    Returns the ai_analysis object or None if classification fails.
    """
    prompt = build_classification_prompt(doc)
    
    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        # Extract text response
        response_text = response.content[0].text.strip()
        
        # Parse JSON response
        # Handle potential markdown code blocks
        if response_text.startswith('```'):
            lines = response_text.split('\n')
            response_text = '\n'.join(lines[1:-1])
        
        analysis = json.loads(response_text)
        
        # Add timestamp
        analysis['analyzed_at'] = datetime.now(timezone.utc).isoformat()
        
        return analysis
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Claude response as JSON: {e}")
        logger.debug(f"Response was: {response_text}")
        return None
    except Exception as e:
        logger.error(f"Error calling Claude API: {e}")
        return None


def update_document_with_analysis(
    client: OpenSearch,
    index: str,
    doc_id: str,
    analysis: dict[str, Any]
) -> bool:
    """
    Update an OpenSearch document with the AI analysis.
    
    Uses partial update to add the ai_analysis field.
    """
    try:
        client.update(
            index=index,
            id=doc_id,
            body={
                "doc": {
                    "ai_analysis": analysis
                }
            }
        )
        return True
    except Exception as e:
        logger.error(f"Error updating document {doc_id} in {index}: {e}")
        return False


def main():
    """Main function to classify DMARC failures."""
    logger.info("Starting DMARC failure classification")
    
    # Check for API key early
    if not os.environ.get('ANTHROPIC_API_KEY'):
        logger.warning("ANTHROPIC_API_KEY not set - skipping AI classification")
        return 0
    
    # Initialize clients
    try:
        os_client = get_opensearch_client()
        anthropic_client = get_anthropic_client()
    except Exception as e:
        logger.error(f"Failed to initialize clients: {e}")
        return 1
    
    # Query for unclassified failures
    documents = query_unclassified_failures(os_client)
    
    if not documents:
        logger.info("No unclassified DMARC records with authentication issues found")
        return 0
    
    # Process each document
    stats = {
        'processed': 0,
        'ok': 0,
        'attention': 0,
        'critical': 0,
        'errors': 0
    }
    
    for doc in documents:
        doc_id = doc['_id']
        index = doc['_index']
        source = doc.get('_source', {})
        
        logger.info(f"Classifying document {doc_id} from {index}")
        logger.debug(f"Source IP: {source.get('source_ip_address')}, "
                    f"Header From: {source.get('header_from')}")
        
        # Classify with Claude
        analysis = classify_failure(anthropic_client, doc)
        
        if analysis is None:
            logger.warning(f"Failed to classify document {doc_id}")
            stats['errors'] += 1
            continue
        
        # Update document in OpenSearch
        if update_document_with_analysis(os_client, index, doc_id, analysis):
            stats['processed'] += 1
            
            # Track status counts
            status = analysis.get('status', 'UNKNOWN').upper()
            if status == 'OK':
                stats['ok'] += 1
            elif status == 'ATTENTION':
                stats['attention'] += 1
            elif status == 'CRITICAL':
                stats['critical'] += 1
                logger.warning(f"CRITICAL: {analysis.get('summary', 'No summary')}")
        else:
            stats['errors'] += 1
    
    # Log summary
    logger.info("=" * 50)
    logger.info("Classification complete")
    logger.info(f"  Processed: {stats['processed']}")
    logger.info(f"  OK: {stats['ok']}")
    logger.info(f"  Attention: {stats['attention']}")
    logger.info(f"  Critical: {stats['critical']}")
    logger.info(f"  Errors: {stats['errors']}")
    logger.info("=" * 50)
    
    # Return non-zero if there were critical findings
    if stats['critical'] > 0:
        logger.warning(f"Found {stats['critical']} CRITICAL classification(s) - review recommended")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
