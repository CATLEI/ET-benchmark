#!/bin/sh
set -e
# Bohrium may inject a *host* GPU index into NVIDIA_VISIBLE_DEVICES (e.g. "1").
# Inside the container the mounted GPU is already remapped to index 0; keeping the
# host index makes CUDA/TF see no device while nvidia-smi still lists GPU 0.
if [ -n "${NVIDIA_VISIBLE_DEVICES}" ] && [ "${NVIDIA_VISIBLE_DEVICES}" != "all" ] \
    && [ "${NVIDIA_VISIBLE_DEVICES}" != "void" ]; then
    echo "ISONET_ENTRYPOINT remap NVIDIA_VISIBLE_DEVICES=${NVIDIA_VISIBLE_DEVICES} -> all" >&2
    export NVIDIA_VISIBLE_DEVICES=all
else
    export NVIDIA_VISIBLE_DEVICES="${NVIDIA_VISIBLE_DEVICES:-all}"
fi
# Always force compute (empty/unset both break TF GPU registration on Bohrium).
export NVIDIA_DRIVER_CAPABILITIES=compute,utility
# A blank CUDA_VISIBLE_DEVICES hides every GPU from TensorFlow.
if [ -n "${CUDA_VISIBLE_DEVICES+x}" ] && [ -z "${CUDA_VISIBLE_DEVICES}" ]; then
    unset CUDA_VISIBLE_DEVICES
fi
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
