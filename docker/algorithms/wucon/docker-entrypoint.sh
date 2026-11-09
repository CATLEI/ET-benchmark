#!/bin/sh
# ET-dflow entrypoint for WUCon layered image
set -e
# Bohrium host GPU index (e.g. "1") must not be kept inside the remapped container.
if [ -n "${NVIDIA_VISIBLE_DEVICES}" ] && [ "${NVIDIA_VISIBLE_DEVICES}" != "all" ] \
    && [ "${NVIDIA_VISIBLE_DEVICES}" != "void" ]; then
    echo "WUCON_ENTRYPOINT remap NVIDIA_VISIBLE_DEVICES=${NVIDIA_VISIBLE_DEVICES} -> all" >&2
    export NVIDIA_VISIBLE_DEVICES=all
else
    export NVIDIA_VISIBLE_DEVICES="${NVIDIA_VISIBLE_DEVICES:-all}"
fi
export NVIDIA_DRIVER_CAPABILITIES=compute,utility
# Empty CUDA_VISIBLE_DEVICES (set-but-blank) can hide all GPUs from CUDA apps.
if [ -n "${CUDA_VISIBLE_DEVICES+x}" ] && [ -z "${CUDA_VISIBLE_DEVICES}" ]; then
    unset CUDA_VISIBLE_DEVICES
fi
for _cuda_lib in /usr/local/nvidia/lib64 /usr/local/nvidia/lib /usr/local/cuda/lib64; do
    if [ -d "${_cuda_lib}" ]; then
        case ":${LD_LIBRARY_PATH:-}:" in
            *":${_cuda_lib}:"*) ;;
            *) LD_LIBRARY_PATH="${_cuda_lib}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" ;;
        esac
    fi
done
export LD_LIBRARY_PATH
if [ $# -eq 0 ]; then
    exec python /app/run_algorithm.py --help
fi
if [ "$1" = "python" ] || [ "$1" = "bash" ] || [ "$1" = "sh" ] || [ "$1" = "/bin/bash" ] || [ "$1" = "/bin/sh" ]; then
    exec "$@"
fi
exec python /app/run_algorithm.py "$@"
