import os
import pathlib
import re
import shutil
import subprocess
import sys


def probe():
    """Import torch in a fresh interpreter (avoids half-upgraded in-process state)."""
    code = (
        "import torch; "
        "print(torch.__version__ + '|' + str(torch.version.cuda))"
    )
    try:
        out = subprocess.check_output(
            [sys.executable, "-c", code],
            text=True,
            stderr=subprocess.STDOUT,
        ).strip().splitlines()[-1]
        ver, cuda = out.split("|", 1)
        if cuda == "None":
            cuda = None
        return ver, cuda, None
    except subprocess.CalledProcessError as exc:
        return "", None, (exc.output or str(exc))


def is_cpu(ver, cuda):
    return (not ver) or (cuda is None) or ("+cpu" in str(ver))


def base_version(ver):
    ver = (ver or "").strip()
    if not ver:
        return (os.environ.get("TORCH_VERSION") or "2.2.0").strip()
    return re.sub(r"[+].*$", "", ver)


def purge_torch():
    print("TORCH_PURGE uninstalling torch family", flush=True)
    subprocess.call(
        [
            sys.executable,
            "-m",
            "pip",
            "uninstall",
            "-y",
            "torch",
            "torchvision",
            "torchaudio",
            "torchtext",
            "torchdata",
        ]
    )
    site = pathlib.Path(sys.prefix) / "lib" / ("python%d.%d" % sys.version_info[:2]) / "site-packages"
    for pattern in ("torch", "torch-*", "torchvision", "torchvision-*", "torchaudio", "torchaudio-*"):
        for path in site.glob(pattern):
            print("TORCH_PURGE rm", path, flush=True)
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                try:
                    path.unlink()
                except OSError:
                    pass


def install_cuda_torch(index, ver):
    spec = "torch==%s" % ver
    print("TORCH_INSTALL %s from %s" % (spec, index), flush=True)
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-cache-dir",
            "--timeout",
            "300",
            spec,
            "--index-url",
            index,
        ]
    )


pre_raw = pathlib.Path("/tmp/torch_pre.txt").read_text(encoding="utf-8").strip()
parts = pre_raw.split("|", 1)
pre_ver = parts[0]
pre_cuda = None if len(parts) < 2 or parts[1] in ("", "None") else parts[1]

index = (os.environ.get("TORCH_INDEX_URL") or "").strip() or "https://download.pytorch.org/whl/cu121"
want_ver = (os.environ.get("TORCH_VERSION") or "").strip() or base_version(pre_ver)

ver, cuda, err = probe()
print("TORCH_POST version=%s cuda=%s" % (ver, cuda), flush=True)
if err:
    print("TORCH_POST import_error:\n%s" % err, flush=True)

need_repair = is_cpu(ver, cuda) or (err is not None)
if need_repair:
    purge_torch()
    install_cuda_torch(index, want_ver)
    ver, cuda, err = probe()
    print("TORCH_REPAIRED version=%s cuda=%s" % (ver, cuda), flush=True)
    if err:
        print("TORCH_REPAIRED import_error:\n%s" % err, flush=True)
        raise SystemExit("torch import still broken after CUDA reinstall")

if is_cpu(ver, cuda):
    raise SystemExit(
        "Refusing CPU torch version=%s cuda=%s (base %s cuda=%s). "
        "Set TORCH_INDEX_URL / TORCH_VERSION."
        % (ver, cuda, pre_ver, pre_cuda)
    )
print("TORCH_OK version=%s cuda=%s" % (ver, cuda), flush=True)
