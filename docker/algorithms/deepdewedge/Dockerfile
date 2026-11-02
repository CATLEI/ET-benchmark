# Layer ET-dflow adapter on DeepDeWedge image (keeps upstream CUDA torch stack).
#
# No local repo? Use ``Dockerfile.bohr`` + ``ET_DFLOW_REPO_URL``.
#
# Build from repository root:
#   docker build -f docker/algorithms/deepdewedge/Dockerfile -t et-dflow/deepdewedge:latest .
#
# Override base / CUDA wheel index:
#   --build-arg BASE_IMAGE=registry.dp.tech/davinci/deepdewedge:20260113145259
#   --build-arg TORCH_INDEX_URL=https://download.pytorch.org/whl/cu121

ARG BASE_IMAGE=registry.dp.tech/davinci/deepdewedge:20260113145259
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
index = (os.environ.get("TORCH_INDEX_URL") or "").strip() or \
    "https://download.pytorch.org/whl/cu121"

if is_cpu(ver, cuda):
    print("reinstalling CUDA torch from %s" % index, flush=True)
    subprocess.check_call(
        [
            sys.executable, "-m", "pip", "install", "--no-cache-dir",
            "--timeout", "300", "--force-reinstall", "torch",
            "--index-url", index,
        ]
    )
    ver, cuda = state()
    print("TORCH_REPAIRED version=%s cuda=%s" % (ver, cuda), flush=True)

if is_cpu(ver, cuda):
    raise SystemExit(
        "Refusing CPU torch (version=%s cuda=%s); base was %s cuda=%s"
        % (ver, cuda, pre_ver, pre_cuda)
    )
print("TORCH_OK version=%s cuda=%s" % (ver, cuda), flush=True)
PY

COPY docker/algorithms/deepdewedge/run_algorithm.py /app/run_algorithm.py
COPY docker/algorithms/deepdewedge/docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD []
