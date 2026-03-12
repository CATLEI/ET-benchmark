#!/bin/sh
# Docker entrypoint script for WBP algorithm
# Allows running the algorithm script or other commands

set -e

# If no arguments provided, run the algorithm script with help
if [ $# -eq 0 ]; then
    exec python /app/run_algorithm.py --help
fi

# If first argument is "python" or other commands, execute them directly
# This allows: docker run image python --version
# Also allows: docker run --entrypoint python image --version
if [ "$1" = "python" ] || [ "$1" = "bash" ] || [ "$1" = "sh" ] || [ "$1" = "/bin/bash" ] || [ "$1" = "/bin/sh" ]; then
    exec "$@"
fi

# Otherwise, run the algorithm script with provided arguments
exec python /app/run_algorithm.py "$@"

