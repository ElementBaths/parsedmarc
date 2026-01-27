#!/usr/bin/env python3
"""
Process DMARC reports from Gmail and import into OpenSearch.

This script runs parsedmarc to fetch DMARC reports from Gmail.
parsedmarc handles the OpenSearch import directly via the [opensearch] 
section in parsedmarc.ini.

This is the main script to run from cron for automated DMARC processing.
"""

import subprocess
import sys
import os


def run_parsedmarc(config_file: str = 'parsedmarc.ini') -> bool:
    """
    Run parsedmarc to process DMARC reports from Gmail.
    
    parsedmarc will:
    1. Fetch DMARC reports from Gmail
    2. Parse the reports
    3. Save to JSON/CSV files (if configured)
    4. Import to OpenSearch (if [opensearch] section is configured)
    
    Args:
        config_file: Path to parsedmarc configuration file
        
    Returns:
        True if successful, False otherwise
    """
    print("=" * 60)
    print("Processing DMARC reports from Gmail")
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
    
    args = parser.parse_args()
    
    print("DMARC Processing Pipeline")
    print("=" * 60)
    
    # Run parsedmarc (handles both parsing and OpenSearch import)
    success = run_parsedmarc(args.config)
    
    if not success:
        print("\n" + "=" * 60)
        print("Pipeline failed: parsedmarc encountered an error")
        print("=" * 60)
        sys.exit(1)
    
    # Success summary
    print("\n" + "=" * 60)
    print("Pipeline completed successfully!")
    print("=" * 60)
    print("✓ DMARC reports processed from Gmail")
    print("✓ Reports imported into OpenSearch")


if __name__ == '__main__':
    main()
