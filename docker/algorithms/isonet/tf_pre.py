"""Record the base image TensorFlow build before pip can replace it."""

import pathlib
import subprocess
import sys

PROBE = (
    "import tensorflow as tf\n"
    "cuda = bool(tf.test.is_built_with_cuda())\n"
    "print(tf.__version__ + '|' + str(cuda))\n"
)

try:
    out = subprocess.check_output(
        [sys.executable, "-c", PROBE],
        text=True,
        stderr=subprocess.STDOUT,
    )
except subprocess.CalledProcessError as exc:
    print(exc.output or exc, file=sys.stderr)
    raise SystemExit("Base image cannot import tensorflow")

line = out.strip().splitlines()[-1]
ver, cuda = line.split("|", 1)
print("TF_PRE version=%s built_with_cuda=%s" % (ver, cuda), flush=True)
pathlib.Path("/tmp/tf_pre.txt").write_text(line + "\n", encoding="utf-8")

keep_names = {
    "tensorflow",
    "tensorflow-gpu",
    "tensorflow-cpu",
    "keras",
    "tensorboard",
    "numpy",
    "h5py",
    "protobuf",
    "scipy",
    "absl-py",
}
try:
    freeze = subprocess.check_output(
        [sys.executable, "-m", "pip", "freeze"], text=True
    )
except subprocess.CalledProcessError as exc:
    print("pip freeze failed:", exc, file=sys.stderr)
    freeze = ""

lines = []
for raw in freeze.splitlines():
    item = raw.strip()
    if not item or item.startswith("-"):
        continue
    name = item.split("==", 1)[0].split("@", 1)[0].strip().lower()
    if name in keep_names or name.startswith("nvidia-"):
        lines.append(item)

pathlib.Path("/tmp/tf-constraints.txt").write_text(
    "\n".join(lines) + ("\n" if lines else ""),
    encoding="utf-8",
)
print("TF_CONSTRAINTS:", flush=True)
print("\n".join(lines) or "(none)", flush=True)
if cuda != "True":
    raise SystemExit(
        "Base TensorFlow %s is not built with CUDA. IsoNet refine cannot see a GPU."
        % ver
    )
