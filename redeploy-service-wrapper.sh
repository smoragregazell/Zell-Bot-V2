#!/bin/bash

# Wrapper script for Zell-Bot redeploy service that finds the script location dynamically
# This allows the systemd service to work from any location

# Get the directory where this wrapper script is located
WRAPPER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to that directory and run the Python script
cd "$WRAPPER_DIR"
exec /usr/bin/python3 "$WRAPPER_DIR/redeploy-service-host.py"
