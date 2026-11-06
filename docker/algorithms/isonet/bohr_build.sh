#!/bin/bash
# Layer et_dflow + TF pin helpers onto the davinci IsoNet base.
# Called from Dockerfile.bohr after: git clone ... && bash .../bohr_build.sh
# (Bohrium cannot curl raw.githubusercontent.com — TLS eof.)
set -euxo pipefail

export NVIDIA_VISIBLE_DEVICES="${NVIDIA_VISIBLE_DEVICES:-all}"
export NVIDIA_DRIVER_CAPABILITIES="${NVIDIA_DRIVER_CAPABILITIES:-compute,utility}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
cd "${REPO_ROOT}"
git rev-parse HEAD
test -f docker/algorithms/isonet/tf_pre.py
test -f docker/algorithms/isonet/tf_post.py
test -f docker/algorithms/isonet/nvidia_ld_path.sh

mkdir -p /app /tmp/etdflow-scripts

apt-get update
apt-get install -y --no-install-recommends git ca-certificates
rm -rf /var/lib/apt/lists/*

cp docker/algorithms/isonet/tf_pre.py /tmp/etdflow-scripts/tf_pre.py
cp docker/algorithms/isonet/tf_post.py /tmp/etdflow-scripts/tf_post.py
cp docker/algorithms/isonet/nvidia_ld_path.sh /tmp/etdflow-scripts/nvidia_ld_path.sh
python /tmp/etdflow-scripts/tf_pre.py

python -m pip install --no-cache-dir --timeout 300 \
  --upgrade-strategy only-if-needed \
  -c /tmp/tf-constraints.txt \
  -i https://pypi.tuna.tsinghua.edu.cn/simple \
  -r requirements-etdflow-algorithm.txt
python -m pip install --no-cache-dir --timeout 300 \
  -i https://pypi.tuna.tsinghua.edu.cn/simple --no-deps .
python /tmp/etdflow-scripts/tf_post.py

cp docker/algorithms/isonet/run_algorithm.py /app/run_algorithm.py
cp docker/algorithms/isonet/docker-entrypoint.sh /app/docker-entrypoint.sh
cp docker/algorithms/isonet/nvidia_ld_path.sh /app/nvidia_ld_path.sh
chmod +x /app/docker-entrypoint.sh
