#!/usr/bin/env python3
"""
Process DMARC reports from Gmail and import into OpenSearch.

This script:
1. Runs parsedmarc to fetch and parse DMARC reports from Gmail
2. If successful, imports the parsed JSON files into OpenSearch

This is the main script to run from cron for automated DMARC processing.
"""

import subprocess
import sys
import os
from pathlib import Path


def run_parsedmarc(config_file: str = 'parsedmarc.ini') -> bool:
    """
    Run parsedmarc to process DMARC reports from Gmail.
    
    Args:
        config_file: Path to parsedmarc configuration file
        
    Returns:
        True if successful, False otherwise
    """
    print("=" * 60)
    print("Step 1: Processing DMARC reports from Gmail")
    print("=" * 60)
    
    if not os.path.exists(config_file):
        print(f"Error: Configuration file {config_file} not found")
        return False
    
    try:
        # Run parsedmarc with the config file
        result = subprocess.run(
            ['parsedmarc', '-c', config_file],
            capture_output=False,  # Show output in real-time
            text=True,
            check=True
        )
        print("\n✓ parsedmarc completed successfully")
        return True
    
    except subprocess.CalledProcessError as e:
        print(f"\n✗ parsedmarc failed with exit code {e.returncode}")
        return False
    
    except FileNotFoundError:
        print("\n✗ Error: parsedmarc command not found")
        print("  Make sure parsedmarc is installed and in your PATH")
        print("  Install with: pip install parsedmarc")
        return False


def run_import_to_opensearch(
    aggregate_file: str = './dmarc_reports/aggregate.json',
    forensic_file: str = './dmarc_reports/forensic.json',
    host: str = 'localhost',
    port: int = 9200
) -> bool:
    """
    Run import_to_opensearch.py to import parsed JSON files.
    
    Args:
        aggregate_file: Path to aggregate.json file
        forensic_file: Path to forensic.json file
        host: OpenSearch host
        port: OpenSearch port
        
    Returns:
        True if successful, False otherwise
    """
    print("\n" + "=" * 60)
    print("Step 2: Importing parsed reports into OpenSearch")
    print("=" * 60)
    
    script_path = Path(__file__).parent / 'import_to_opensearch.py'
    
    if not script_path.exists():
        print(f"Error: import_to_opensearch.py not found at {script_path}")
        return False
    
    try:
        # Run import script with arguments
        result = subprocess.run(
            [
                sys.executable,
                str(script_path),
                '--host', host,
                '--port', str(port),
                '--aggregate-file', aggregate_file,
                '--forensic-file', forensic_file
            ],
            capture_output=False,  # Show output in real-time
            text=True,
            check=True
        )
        print("\n✓ Import to OpenSearch completed successfully")
        return True
    
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Import to OpenSearch failed with exit code {e.returncode}")
        return False


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Process DMARC reports from Gmail and import into OpenSearch"
    )
    parser.add_argument(
        '--config',
        default='parsedmarc.ini',
        help='Path to parsedmarc configuration file (default: parsedmarc.ini)'
    )
    parser.add_argument(
        '--opensearch-host',
        default='localhost',
        help='OpenSearch host (default: localhost)'
    )
    parser.add_argument(
        '--opensearch-port',
        type=int,
        default=9200,
        help='OpenSearch port (default: 9200)'
    )
    parser.add_argument(
        '--skip-parsedmarc',
        action='store_true',
        help='Skip parsedmarc step and only run import (useful for testing)'
    )
    parser.add_argument(
        '--skip-import',
        action='store_true',
        help='Skip import step and only run parsedmarc (useful for testing)'
    )
    
    args = parser.parse_args()
    
    print("DMARC Processing and Import Pipeline")
    print("=" * 60)
    
    # Step 1: Run parsedmarc
    parsedmarc_success = True
    if not args.skip_parsedmarc:
        parsedmarc_success = run_parsedmarc(args.config)
        if not parsedmarc_success:
            print("\n" + "=" * 60)
            print("Pipeline stopped: parsedmarc failed")
            print("=" * 60)
            sys.exit(1)
    else:
        print("\nSkipping parsedmarc step (--skip-parsedmarc)")
    
    # Step 2: Import to OpenSearch
    import_success = True
    if not args.skip_import:
        import_success = run_import_to_opensearch(
            host=args.opensearch_host,
            port=args.opensearch_port
        )
        if not import_success:
            print("\n" + "=" * 60)
            print("Warning: Import to OpenSearch failed")
            print("=" * 60)
            sys.exit(1)
    else:
        print("\nSkipping import step (--skip-import)")
    
    # Success summary
    print("\n" + "=" * 60)
    print("Pipeline completed successfully!")
    print("=" * 60)
    if not args.skip_parsedmarc:
        print("✓ DMARC reports processed from Gmail")
    if not args.skip_import:
        print("✓ Reports imported into OpenSearch")
    print("\nAccess OpenSearch Dashboards at: http://localhost:5601")


if __name__ == '__main__':
    main()
