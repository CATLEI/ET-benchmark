#!/bin/sh
set -e
# A blank CUDA_VISIBLE_DEVICES hides every GPU from TensorFlow.
if [ -n "${CUDA_VISIBLE_DEVICES+x}" ] && [ -z "${CUDA_VISIBLE_DEVICES}" ]; then
    unset CUDA_VISIBLE_DEVICES
fi
# Prefer image-local helper; fall back to inline if an old layer omitted the file.
if [ -f /tmp/etdflow-scripts/nvidia_ld_path.sh ]; then
    # shellcheck disable=SC1091
    . /tmp/etdflow-scripts/nvidia_ld_path.sh
elif [ -f /app/nvidia_ld_path.sh ]; then
    # shellcheck disable=SC1091
    . /app/nvidia_ld_path.sh
else
    for _cuda_lib in /usr/local/nvidia/lib64 /usr/local/nvidia/lib /usr/local/cuda/lib64; do
        if [ -d "${_cuda_lib}" ]; then
            case ":${LD_LIBRARY_PATH:-}:" in
                *":${_cuda_lib}:"*) ;;
                *) LD_LIBRARY_PATH="${_cuda_lib}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" ;;
            esac
        fi
    done
    export LD_LIBRARY_PATH
fi
if [ $# -eq 0 ]; then
    exec python /app/run_algorithm.py --help
fi
if [ "$1" = "python" ] || [ "$1" = "bash" ] || [ "$1" = "sh" ] || [ "$1" = "/bin/bash" ] || [ "$1" = "/bin/sh" ]; then
    exec "$@"
fi
exec python /app/run_algorithm.py "$@"
