#!/bin/bash
# Layer et_dflow + CUDA torch + wucon deps onto davinci wucon base.
# Called from Dockerfile.bohr after git clone (not curl raw.githubusercontent.com).
set -euxo pipefail

export NVIDIA_VISIBLE_DEVICES="${NVIDIA_VISIBLE_DEVICES:-all}"
export NVIDIA_DRIVER_CAPABILITIES="${NVIDIA_DRIVER_CAPABILITIES:-compute,utility}"

TORCH_INDEX_URL="${TORCH_INDEX_URL:-https://download.pytorch.org/whl/cu121}"
TORCH_VERSION="${TORCH_VERSION:-}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
cd "${REPO_ROOT}"
git rev-parse HEAD
test -f docker/algorithms/wucon/torch_pre.py
test -f docker/algorithms/wucon/torch_post.py
test -f docker/algorithms/wucon/docker-entrypoint.sh

mkdir -p /app /tmp/etdflow-scripts

apt-get update
apt-get install -y --no-install-recommends git ca-certificates
rm -rf /var/lib/apt/lists/*

cp docker/algorithms/wucon/torch_pre.py /tmp/etdflow-scripts/torch_pre.py
cp docker/algorithms/wucon/torch_post.py /tmp/etdflow-scripts/torch_post.py

python /tmp/etdflow-scripts/torch_pre.py

python -m pip install --no-cache-dir --timeout 300 \
  --upgrade-strategy only-if-needed \
  -c /tmp/torch-constraints.txt \
  -i https://pypi.tuna.tsinghua.edu.cn/simple \
  -r requirements-etdflow-algorithm.txt
python -m pip install --no-cache-dir --timeout 300 \
  -i https://pypi.tuna.tsinghua.edu.cn/simple --no-deps .

TORCH_INDEX_URL="${TORCH_INDEX_URL}" TORCH_VERSION="${TORCH_VERSION}" \
  python /tmp/etdflow-scripts/torch_post.py

# Upstream env.yml pip deps + odl (proc_freq imports bm3d at module load).
python -m pip install --no-cache-dir --timeout 300 \
  -i https://pypi.tuna.tsinghua.edu.cn/simple \
  "odl==0.8.3" \
  "scikit-image>=0.19" \
  "matplotlib>=3.5" \
  "tqdm>=4.60" \
  "tensorboard>=2.5" \
  "Pillow>=9.0" \
  "mrcfile>=1.3" \
  "h5py>=3.0" \
  "PyWavelets>=1.3" \
  "imageio>=2.20" \
  "tifffile>=2021.11.2" \
  "networkx>=2.6"

# bm3d alone (hard-fail): tuna first, then PyPI. utils->proc_freq imports it.
if ! python -m pip install --no-cache-dir --timeout 300 \
    -i https://pypi.tuna.tsinghua.edu.cn/simple "bm3d>=3.0.0"; then
  python -m pip install --no-cache-dir --timeout 300 "bm3d>=3.0.0"
fi
python -c "import bm3d; print('BM3D_OK', getattr(bm3d, '__version__', 'unknown'))"

tv_ok=0
for idx in \
  "${TORCH_INDEX_URL}" \
  https://download.pytorch.org/whl/cu126 \
  https://download.pytorch.org/whl/cu124 \
  https://download.pytorch.org/whl/cu121 \
  https://download.pytorch.org/whl/cu128
do
  echo "WUCON_TRY_TORCHVISION index=${idx}"
  if python -m pip install --no-cache-dir --timeout 300 torchvision --index-url "${idx}" \
    && python -c "import torchvision; print('TORCHVISION_OK', torchvision.__version__)"; then
    tv_ok=1
    break
  fi
done
if [ "${tv_ok}" != "1" ]; then
  echo "Failed to install importable torchvision from CUDA indexes" >&2
  exit 1
fi

python -c "import importlib; mods='odl odl.contrib.torch skimage matplotlib tqdm tensorboard PIL mrcfile h5py scipy torch torchvision bm3d pywt imageio tifffile networkx'.split(); \
[(importlib.import_module(n), print('WUCON_DEP_OK', n)) for n in mods]"

cp docker/algorithms/wucon/run_algorithm.py /app/run_algorithm.py
cp docker/algorithms/wucon/docker-entrypoint.sh /app/docker-entrypoint.sh
chmod +x /app/docker-entrypoint.sh
