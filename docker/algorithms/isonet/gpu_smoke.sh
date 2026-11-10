#!/bin/sh
# Quick TensorFlow GPU visibility check for IsoNet Bohrium images.
# Run inside the container after entrypoint env remaps:
#   docker run --gpus all --entrypoint /bin/sh IMAGE -c '/app/gpu_smoke.sh'
set -e
. /app/nvidia_ld_path.sh 2>/dev/null || true
export NVIDIA_VISIBLE_DEVICES="${NVIDIA_VISIBLE_DEVICES:-all}"
export NVIDIA_DRIVER_CAPABILITIES=compute,utility
if [ -n "${CUDA_VISIBLE_DEVICES+x}" ] && [ -z "${CUDA_VISIBLE_DEVICES}" ]; then
    unset CUDA_VISIBLE_DEVICES
fi
python - <<'PY'
import os
print("NVIDIA_VISIBLE_DEVICES", os.environ.get("NVIDIA_VISIBLE_DEVICES"))
print("CUDA_VISIBLE_DEVICES", os.environ.get("CUDA_VISIBLE_DEVICES"))
print("LD_LIBRARY_PATH", os.environ.get("LD_LIBRARY_PATH", "")[:200])
import tensorflow as tf
print("TF", tf.__version__)
print("built_with_cuda", tf.test.is_built_with_cuda())
gpus = tf.config.list_physical_devices("GPU")
print("TF_GPU_COUNT", len(gpus))
print("TF_GPUS", gpus)
raise SystemExit(0 if gpus else 2)
PY
