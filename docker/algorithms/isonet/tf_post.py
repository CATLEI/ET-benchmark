"""Fail the image build if pip replaced the CUDA TensorFlow wheel."""

import pathlib
import subprocess
import sys

PROBE = (
    "import tensorflow as tf\n"
    "cuda = bool(tf.test.is_built_with_cuda())\n"
    "print(tf.__version__ + '|' + str(cuda))\n"
)

RESTORE = {"tensorflow", "tensorflow-gpu", "keras"}


def probe():
    try:
        out = subprocess.check_output(
            [sys.executable, "-c", PROBE],
            text=True,
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as exc:
        return "", False, (exc.output or str(exc))
    ver, cuda = out.strip().splitlines()[-1].split("|", 1)
    return ver, cuda == "True", None


def restore(constraints: pathlib.Path) -> None:
    specs = []
    for raw in constraints.read_text(encoding="utf-8").splitlines():
        item = raw.strip()
        if not item:
            continue
        name = item.split("==", 1)[0].split("@", 1)[0].strip().lower()
        if name in RESTORE:
            specs.append(item)
    if not specs:
        raise SystemExit("No tensorflow/keras pin in %s" % constraints)
    print("TF_RESTORE %s" % " ".join(specs), flush=True)
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-cache-dir",
            "--timeout",
            "300",
            *specs,
        ]
    )


pre = pathlib.Path("/tmp/tf_pre.txt").read_text(encoding="utf-8").strip()
pre_ver, pre_cuda = pre.split("|", 1)
ver, cuda, err = probe()
print("TF_POST version=%s built_with_cuda=%s" % (ver, cuda), flush=True)
if err:
    print("TF_POST import_error:\n%s" % err, flush=True)

if pre_cuda != "True":
    raise SystemExit("Base TensorFlow %s was not a CUDA build" % pre_ver)

if (not cuda) or err:
    restore(pathlib.Path("/tmp/tf-constraints.txt"))
    ver, cuda, err = probe()
    print("TF_REPAIRED version=%s built_with_cuda=%s" % (ver, cuda), flush=True)
    if err:
        print("TF_REPAIRED import_error:\n%s" % err, flush=True)

if not cuda:
    raise SystemExit(
        "TensorFlow lost CUDA support (now %s, base %s). "
        "IsoNet refine will report 'No GPU detected'."
        % (ver, pre_ver)
    )
print("TF_OK version=%s built_with_cuda=%s" % (ver, cuda), flush=True)
