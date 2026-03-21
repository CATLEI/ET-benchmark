#!/bin/sh
# ET-dflow entrypoint for TIGRE layered image
set -e
if [ $# -eq 0 ]; then
    exec python /app/run_algorithm.py --help
fi
if [ "$1" = "python" ] || [ "$1" = "bash" ] || [ "$1" = "sh" ] || [ "$1" = "/bin/bash" ] || [ "$1" = "/bin/sh" ]; then
    exec "$@"
fi
exec python /app/run_algorithm.py "$@"
