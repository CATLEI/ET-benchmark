"""Fail the image build if pip replaced the CUDA TensorFlow wheel."""

import glob
import os
import pathlib
import subprocess
import sys
import sysconfig

PROBE = (
    "import tensorflow as tf\n"
    "cuda = bool(tf.test.is_built_with_cuda())\n"
    "print(tf.__version__ + '|' + str(cuda))\n"
)

RESTORE = {"tensorflow", "tensorflow-gpu", "keras"}

# TF 2.15 needs CUDA 12.2 + cuDNN 8.9. Unpinned nvidia-cudnn-cu12 resolves to
# cuDNN 9.x → TF "Cannot dlopen some GPU libraries" / TF_GPU_COUNT 0 on Bohrium.
_NVIDIA_CU12_PACKAGES = (
    "nvidia-cublas-cu12==12.2.5.6",
    "nvidia-cuda-cupti-cu12==12.2.142",
    "nvidia-cuda-nvcc-cu12==12.2.140",
    "nvidia-cuda-nvrtc-cu12==12.2.140",
    "nvidia-cuda-runtime-cu12==12.2.140",
    "nvidia-cudnn-cu12==8.9.7.29",
    "nvidia-cufft-cu12==11.0.8.103",
    "nvidia-curand-cu12==10.3.3.141",
    "nvidia-cusolver-cu12==11.5.2.141",
    "nvidia-cusparse-cu12==12.1.2.141",
    "nvidia-nccl-cu12==2.16.5",
    "nvidia-nvjitlink-cu12==12.2.140",
)


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
        if name in RESTORE or name.startswith("nvidia-"):
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


def nvidia_pip_lib_dirs():
    roots = []
    for key in ("purelib", "platlib"):
        path = sysconfig.get_paths().get(key)
        if path:
            roots.append(path)
    try:
        import site

        roots.extend(site.getsitepackages())
    except Exception:
        pass
    dirs = []
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for lib in sorted(glob.glob(os.path.join(root, "nvidia", "*", "lib"))):
            if os.path.isdir(lib) and lib not in dirs:
                dirs.append(lib)
    return dirs


def _pip_install(*specs: str) -> int:
    print("TF_PIP_INSTALL %s" % " ".join(specs), flush=True)
    return subprocess.call(
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


def _cudnn_major_from_dir(lib_dir: str) -> str:
    """Return '8' / '9' / '?' from libcudnn.so.* next to a pip nvidia lib dir."""
    matches = sorted(glob.glob(os.path.join(lib_dir, "libcudnn.so.*")))
    for path in matches:
        name = os.path.basename(path)
        # libcudnn.so.8.9.7 / libcudnn.so.9.1.0
        parts = name.split(".")
        if len(parts) >= 3 and parts[2].isdigit():
            return parts[2]
    return "?"


def ensure_nvidia_pip_libs(tf_ver: str) -> list:
    """Install/repair pip CUDA libs for TF 2.15 (cuDNN 8.9, not 9.x)."""
    dirs = nvidia_pip_lib_dirs()
    cudnn_dirs = [d for d in dirs if d.rstrip("/").endswith("/cudnn/lib")]
    cudnn_major = (
        _cudnn_major_from_dir(cudnn_dirs[0]) if cudnn_dirs else "missing"
    )
    print("TF_CUDNN_MAJOR %s" % cudnn_major, flush=True)

    # Always re-pin when cuDNN is missing or too new for TF 2.15.
    need_pin = (not dirs) or (cudnn_major not in ("8",))
    if need_pin:
        rc = _pip_install(*_NVIDIA_CU12_PACKAGES)
        dirs = nvidia_pip_lib_dirs()
        cudnn_dirs = [d for d in dirs if d.rstrip("/").endswith("/cudnn/lib")]
        cudnn_major = (
            _cudnn_major_from_dir(cudnn_dirs[0]) if cudnn_dirs else "missing"
        )
        print(
            "TF_NVIDIA_PIP_LIBS_CU12 rc=%s cudnn=%s dirs=%s"
            % (rc, cudnn_major, " ".join(dirs) or "(none)"),
            flush=True,
        )
        if dirs and cudnn_major == "8":
            return dirs

    if dirs and cudnn_major == "8":
        return dirs

    constraints = pathlib.Path("/tmp/tf-constraints.txt")
    if constraints.is_file():
        restore(constraints)
        dirs = nvidia_pip_lib_dirs()
        print(
            "TF_NVIDIA_PIP_LIBS_RESTORED %s" % (" ".join(dirs) or "(none)"),
            flush=True,
        )
        if dirs:
            return dirs

    # Last resort: tensorflow[and-cuda] extra (may re-resolve tensorflow).
    ver = (tf_ver or "").strip()
    if ver:
        _pip_install("tensorflow[and-cuda]==%s" % ver)
        # Re-pin CUDA build if the extra swapped in a CPU wheel.
        if constraints.is_file():
            restore(constraints)
        # and-cuda may pull cuDNN 9; force TF 2.15 pins again.
        _pip_install(*_NVIDIA_CU12_PACKAGES)
        dirs = nvidia_pip_lib_dirs()
        print(
            "TF_NVIDIA_PIP_LIBS_AND_CUDA %s" % (" ".join(dirs) or "(none)"),
            flush=True,
        )
    return dirs


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

nv_dirs = ensure_nvidia_pip_libs(ver)
print("TF_NVIDIA_PIP_LIBS %s" % (" ".join(nv_dirs) or "(none)"), flush=True)
if not nv_dirs:
    # Davinci IsoNet often ships system CUDA TF without pip nvidia-* wheels.
    # Runtime still needs host libcuda (Bohrium GPU mount) + entrypoint LD path.
    print(
        "TF_NVIDIA_PIP_LIBS_WARN no site-packages/nvidia/*/lib; "
        "relying on system CUDA + nvidia_ld_path.sh at runtime",
        flush=True,
    )
print("TF_OK version=%s built_with_cuda=%s" % (ver, cuda), flush=True)
