#!/bin/bash
# Wrapper script for process_and_import.py
# Monitors execution, logs to syslog, and sends email notifications on failure

set -euo pipefail

SCRIPT_NAME="wrapper.sh"
TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M:%S UTC")
LOG_TAG="wrapper.sh"

# Function to log to syslog
log_message() {
    local level=$1
    shift
    logger -t "$LOG_TAG" -p "local0.$level" "[$level] $*"
}

# Function to escape string for JSON
json_escape() {
    # Escape backslashes, quotes, and control characters for JSON
    printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' -e 's/\t/\\t/g' | tr '\n' ' '
}

# Function to send email via Postmark API
send_failure_email() {
    local exit_code=$1
    local error_msg=$2
    
    # Source Postmark configuration
    if [ ! -f "/app/postmark.conf" ]; then
        log_message "error" "Postmark configuration file not found at /app/postmark.conf"
        return 1
    fi
    
    # Read configuration
    source <(grep -v '^#' /app/postmark.conf | grep -v '^$' | sed 's/^/export /')
    
    if [ -z "${POSTMARK_API_TOKEN:-}" ] || [ -z "${POSTMARK_FROM_EMAIL:-}" ] || [ -z "${POSTMARK_TO_EMAIL:-}" ]; then
        log_message "error" "Postmark configuration incomplete. Missing API_TOKEN, FROM_EMAIL, or TO_EMAIL"
        return 1
    fi
    
    local subject="ParseDmarc Processing Failed - $TIMESTAMP"
    
    # Sanitize error message for JSON (remove special chars, escape quotes)
    local safe_error_msg=$(json_escape "$error_msg")
    
    local body="ParseDmarc processing failed at $TIMESTAMP\\n\\nExit Code: $exit_code\\nError: $safe_error_msg\\n\\nPlease check the logs for more details."
    
    # Send email via Postmark API
    local response=$(curl -s -w "\n%{http_code}" -X POST "https://api.postmarkapp.com/email" \
        -H "Accept: application/json" \
        -H "Content-Type: application/json" \
        -H "X-Postmark-Server-Token: $POSTMARK_API_TOKEN" \
        -d "{\"From\": \"$POSTMARK_FROM_EMAIL\", \"To\": \"$POSTMARK_TO_EMAIL\", \"Subject\": \"$subject\", \"TextBody\": \"$body\"}")
    
    local http_code=$(echo "$response" | tail -n1)
    local response_body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" -eq 200 ]; then
        log_message "info" "Failure email sent via Postmark API"
        return 0
    else
        log_message "error" "Failed to send email via Postmark API. HTTP code: $http_code, Response: $response_body"
        return 1
    fi
}

# Main execution
main() {
    log_message "info" "Process started at $TIMESTAMP"
    
    # Execute process_and_import.py
    # Capture exit code but don't fail wrapper script if Python script fails
    set +e
    python3 /app/process_and_import.py \
        > /tmp/process_output.log 2>&1
    exit_code=$?
    set -e
    
    if [ $exit_code -eq 0 ]; then
        log_message "info" "process_and_import.py completed successfully (exit code: 0)"
        
        # Log output summary on success
        line_count=$(wc -l < /tmp/process_output.log)
        log_message "info" "Output: $line_count lines"
        
        # Log last few lines as summary
        log_message "info" "========== OUTPUT SUMMARY =========="
        while IFS= read -r line; do
            log_message "info" "$line"
        done < <(tail -n 10 /tmp/process_output.log)
        log_message "info" "========== END SUMMARY =========="
        
        # Run AI classification on DMARC failures
        log_message "info" "Starting AI classification of DMARC failures"
        set +e
        python3 /app/classify_dmarc_failures.py \
            > /tmp/classify_output.log 2>&1
        classify_exit_code=$?
        set -e
        
        if [ $classify_exit_code -eq 0 ]; then
            log_message "info" "AI classification completed successfully"
            # Log classification summary
            log_message "info" "========== CLASSIFICATION SUMMARY =========="
            while IFS= read -r line; do
                log_message "info" "$line"
            done < <(tail -n 10 /tmp/classify_output.log)
            log_message "info" "========== END CLASSIFICATION =========="
        else
            log_message "warning" "AI classification failed with exit code: $classify_exit_code"
            # Log error output but don't fail the whole process
            while IFS= read -r line; do
                log_message "warning" "$line"
            done < <(tail -n 20 /tmp/classify_output.log)
        fi
        
        log_message "info" "Process completed at $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
        exit 0
    else
        # Log full output for debugging
        log_message "error" "process_and_import.py failed with exit code: $exit_code"
        log_message "error" "========== BEGIN FULL OUTPUT =========="
        
        # Log each line of output to syslog
        while IFS= read -r line; do
            log_message "error" "$line"
        done < /tmp/process_output.log
        
        log_message "error" "========== END FULL OUTPUT =========="
        log_message "info" "Process completed at $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
        
        # Extract summary error for email (strip special chars for JSON safety)
        error_msg=$(tail -n 20 /tmp/process_output.log | grep -i "error\|failed\|exception\|traceback" | head -n 3 | tr '\n' ' ' | tr -cd '[:print:]' || echo "Unknown error")
        
        # Send failure notification email
        send_failure_email "$exit_code" "$error_msg" || true
        
        exit $exit_code
    fi
}

# Run main function
main "$@"
