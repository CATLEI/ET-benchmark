#!/bin/sh
set -e
# A blank CUDA_VISIBLE_DEVICES hides every GPU from TensorFlow.
if [ -n "${CUDA_VISIBLE_DEVICES+x}" ] && [ -z "${CUDA_VISIBLE_DEVICES}" ]; then
    unset CUDA_VISIBLE_DEVICES
fi
if [ $# -eq 0 ]; then
    exec python /app/run_algorithm.py --help
fi
if [ "$1" = "python" ] || [ "$1" = "bash" ] || [ "$1" = "sh" ] || [ "$1" = "/bin/bash" ] || [ "$1" = "/bin/sh" ]; then
    exec "$@"
fi
exec python /app/run_algorithm.py "$@"
