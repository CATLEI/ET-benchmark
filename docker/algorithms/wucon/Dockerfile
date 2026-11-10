# Layer ET-dflow adapter on WUCon image (keeps upstream CUDA torch stack).
# Expects WUCON code under /opt/wucon/src.
#
# No local repo? Use ``Dockerfile.bohr`` + ``ET_DFLOW_REPO_URL``.
#
# Build from repository root:
#   docker build -f docker/algorithms/wucon/Dockerfile -t et-dflow/wucon:latest .
#
# Override base / CUDA wheel index:
#   --build-arg BASE_IMAGE=registry.dp.tech/davinci/wucon:20260113160259
#   --build-arg TORCH_INDEX_URL=https://download.pytorch.org/whl/cu121

ARG BASE_IMAGE=registry.dp.tech/davinci/wucon:20260113160259
FROM ${BASE_IMAGE}

USER root
WORKDIR /app

ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cu121

COPY requirements-etdflow-algorithm.txt /tmp/requirements-etdflow-algorithm.txt
COPY et_dflow/ ./et_dflow/
COPY setup.py pyproject.toml ./

# Pin installed torch family before et_dflow deps so PyPI cannot swap in +cpu.
RUN python - <<'PY'
import pathlib
import subprocess
import sys

def torch_state():
    try:
        import torch
        return torch.__version__, torch.version.cuda
    except Exception as exc:
        print("TORCH_PRE unavailable:", exc, file=sys.stderr)
        return "", None

ver, cuda = torch_state()
print("TORCH_PRE version=%s cuda=%s" % (ver, cuda), flush=True)
pathlib.Path("/tmp/torch_pre.txt").write_text("%s|%s\n" % (ver, cuda), encoding="utf-8")

family = ("torch", "torchvision", "torchaudio", "torchtext", "torchdata")
lines = []
try:
    out = subprocess.check_output(
        [sys.executable, "-m", "pip", "freeze"], text=True
    )
except Exception as exc:
    print("pip freeze failed:", exc, file=sys.stderr)
    out = ""
for line in out.splitlines():
    name = line.split("==", 1)[0].split("@", 1)[0].strip().lower()
    if name in family:
        lines.append(line.strip())
pathlib.Path("/tmp/torch-constraints.txt").write_text(
    "\n".join(lines) + ("\n" if lines else ""),
    encoding="utf-8",
)
print("TORCH_CONSTRAINTS:\n%s" % ("\n".join(lines) or "(none)"), flush=True)
PY

RUN pip install --no-cache-dir --upgrade-strategy only-if-needed \
    -c /tmp/torch-constraints.txt \
    -r /tmp/requirements-etdflow-algorithm.txt \
    && pip install --no-cache-dir --no-deps -e .

RUN TORCH_INDEX_URL="${TORCH_INDEX_URL}" python - <<'PY'
import os
import pathlib
import subprocess
import sys

INDEXES = [
    "https://download.pytorch.org/whl/cu121",
    "https://download.pytorch.org/whl/cu124",
    "https://download.pytorch.org/whl/cu126",
    "https://download.pytorch.org/whl/cu128",
    "https://download.pytorch.org/whl/cu118",
]

def state():
    import torch
    return torch.__version__, torch.version.cuda

def is_cpu(ver, cuda):
    return (cuda is None) or ("+cpu" in str(ver))

pre_raw = pathlib.Path("/tmp/torch_pre.txt").read_text(encoding="utf-8").strip()
parts = pre_raw.split("|", 1)
pre_ver = parts[0]
pre_cuda = None if len(parts) < 2 or parts[1] in ("", "None") else parts[1]

ver, cuda = state()
print("TORCH_POST version=%s cuda=%s" % (ver, cuda), flush=True)
preferred = (os.environ.get("TORCH_INDEX_URL") or "").strip()
indexes = ([preferred] if preferred else []) + [i for i in INDEXES if i != preferred]

if is_cpu(ver, cuda):
    ok = False
    for index in indexes:
        print("reinstalling CUDA torch from %s" % index, flush=True)
        rc = subprocess.call(
            [
                sys.executable, "-m", "pip", "install", "--no-cache-dir",
                "--timeout", "300", "--force-reinstall", "torch",
                "--index-url", index,
            ]
        )
        if rc == 0:
            ok = True
            break
    if not ok:
        raise SystemExit("Failed to install CUDA torch from %s" % indexes)
    ver, cuda = state()
    print("TORCH_REPAIRED version=%s cuda=%s" % (ver, cuda), flush=True)

if is_cpu(ver, cuda):
    raise SystemExit(
        "Refusing CPU torch (version=%s cuda=%s); base was %s cuda=%s"
        % (ver, cuda, pre_ver, pre_cuda)
    )
print("TORCH_OK version=%s cuda=%s" % (ver, cuda), flush=True)
PY

# Upstream wucon src imports (proc_freq needs bm3d). Python 3.10 → odl==0.8.3.
# astra-toolbox is required for odl.tomo RayTransform(impl='astra_cuda').
RUN pip install --no-cache-dir --timeout 300 \
    "odl==0.8.3" \
    "astra-toolbox" \
    "scikit-image>=0.19" \
    "matplotlib>=3.5" \
    "tqdm>=4.60" \
    "tensorboard>=2.5" \
    "Pillow>=9.0" \
    "mrcfile>=1.3" \
    "h5py>=3.0" \
    "bm3d>=3.0.0" \
    "PyWavelets>=1.3" \
    "imageio>=2.20" \
    "tifffile>=2021.11.2" \
    "networkx>=2.6" && \
    python -c "import importlib; mods='odl odl.contrib.torch astra skimage matplotlib tqdm tensorboard PIL mrcfile h5py scipy torch torchvision bm3d pywt imageio tifffile networkx'.split(); \
[(importlib.import_module(n), print('WUCON_DEP_OK', n)) for n in mods]"

COPY docker/algorithms/wucon/run_algorithm.py /app/run_algorithm.py
COPY docker/algorithms/wucon/docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD []
