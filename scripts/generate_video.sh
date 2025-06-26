#!/bin/bash

# Script to generate a video without uploading to YT Shorts

# Check which interpreter to use (python)
if [ -x "$(command -v python3)" ]; then
  PYTHON=python3
else
  PYTHON=python
fi

# Function to show usage
show_usage() {
    echo "Usage: $0 [options] [account_id]"
    echo "Options:"
    echo "  -n, --new    Force create a new video session"
    echo "  -c, --clean  Clean up all incomplete sessions"
    echo "  -h, --help   Show this help message"
    echo ""
    echo "If no options are provided, the script will attempt to resume"
    echo "the most recent incomplete session if one exists."
}

# Parse command line arguments
FORCE_NEW=false
CLEAN_SESSIONS=false
ACCOUNT_ID=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--new)
            FORCE_NEW=true
            shift
            ;;
        -c|--clean)
            CLEAN_SESSIONS=true
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            if [ -z "$ACCOUNT_ID" ]; then
                ACCOUNT_ID="$1"
            else
                echo "Error: Unexpected argument: $1"
                show_usage
                exit 1
            fi
            shift
            ;;
    esac
done

# Build the command with appropriate flags
CMD="$PYTHON src/cron.py video_generate"

# Add account ID if provided
if [ -n "$ACCOUNT_ID" ]; then
    CMD="$CMD $ACCOUNT_ID"
fi

# Add flags for new session and cleanup
if [ "$FORCE_NEW" = true ]; then
    CMD="$CMD --new"
fi

if [ "$CLEAN_SESSIONS" = true ]; then
    CMD="$CMD --clean"
fi

# Execute the command
$CMD