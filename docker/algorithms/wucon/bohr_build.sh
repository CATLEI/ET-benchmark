#!/bin/bash
# Layer et_dflow + CUDA torch + wucon runtime deps onto davinci wucon base.
# Invoked by the short Dockerfile.bohr (avoids Bohrium long-paste / stale cache).
set -euxo pipefail

export NVIDIA_VISIBLE_DEVICES="${NVIDIA_VISIBLE_DEVICES:-all}"
export NVIDIA_DRIVER_CAPABILITIES="${NVIDIA_DRIVER_CAPABILITIES:-compute,utility}"

ET_DFLOW_REPO_URL="${ET_DFLOW_REPO_URL:-https://github.com/CATLEI/ET-benchmark.git}"
ET_DFLOW_REPO_REF="${ET_DFLOW_REPO_REF:-main}"
TORCH_INDEX_URL="${TORCH_INDEX_URL:-https://download.pytorch.org/whl/cu121}"
TORCH_VERSION="${TORCH_VERSION:-}"

mkdir -p /app /tmp/etdflow-scripts /tmp/etdflow-build
cd /tmp/etdflow-build

apt-get update
apt-get install -y --no-install-recommends git ca-certificates curl
rm -rf /var/lib/apt/lists/*

git clone "${ET_DFLOW_REPO_URL}" repo
cd repo
git checkout "${ET_DFLOW_REPO_REF}"
git rev-parse HEAD
test -f docker/algorithms/wucon/torch_pre.py
test -f docker/algorithms/wucon/torch_post.py
test -f docker/algorithms/wucon/docker-entrypoint.sh

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

# Python 3.10 -> odl 0.8.3. torchvision must come from a CUDA torch index
# (tuna/PyPI CPU wheel breaks or is absent after torch_post purge).
python -m pip install --no-cache-dir --timeout 300 \
  -i https://pypi.tuna.tsinghua.edu.cn/simple \
  "odl==0.8.3" \
  "scikit-image>=0.19" \
  "matplotlib>=3.5" \
  "tqdm>=4.60" \
  "tensorboard>=2.5" \
  "Pillow>=9.0" \
  "mrcfile>=1.3" \
  "h5py>=3.0"

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

python -c "import importlib; mods='odl odl.contrib.torch skimage matplotlib tqdm tensorboard PIL mrcfile h5py scipy torch torchvision'.split(); \
[(importlib.import_module(n), print('WUCON_DEP_OK', n)) for n in mods]"

cp docker/algorithms/wucon/run_algorithm.py /app/run_algorithm.py
cp docker/algorithms/wucon/docker-entrypoint.sh /app/docker-entrypoint.sh
chmod +x /app/docker-entrypoint.sh
