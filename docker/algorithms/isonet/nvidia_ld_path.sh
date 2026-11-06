# shellcheck shell=sh
# Prepend CUDA driver + pip nvidia-* lib dirs so TensorFlow can dlopen GPU libs.
# Source from docker-entrypoint.sh (Bohrium often has nvidia-smi without
# /usr/local/nvidia mounts; TF still needs site-packages/nvidia/*/lib).

_nv_prepend=""

for _cuda_lib in \
    /usr/local/nvidia/lib64 \
    /usr/local/nvidia/lib \
    /usr/local/cuda/lib64 \
    /usr/local/cuda/compat \
    /usr/lib/x86_64-linux-gnu \
    /usr/lib64; do
    if [ -d "${_cuda_lib}" ]; then
        case ":${_nv_prepend}:${LD_LIBRARY_PATH:-}:" in
            *":${_cuda_lib}:"*) ;;
            *) _nv_prepend="${_nv_prepend}${_nv_prepend:+:}${_cuda_lib}" ;;
        esac
    fi
done

# libcuda.so* may live outside the usual nvidia mount (find once, cheap).
_libcuda_file="$(
    find /usr/lib /usr/lib64 /usr/local /lib /lib64 \
        -name 'libcuda.so*' 2>/dev/null \
        | head -n 1
)"
_libcuda_dir=""
if [ -n "${_libcuda_file}" ]; then
    _libcuda_dir="$(dirname "${_libcuda_file}")"
fi
if [ -n "${_libcuda_dir}" ] && [ -d "${_libcuda_dir}" ]; then
    case ":${_nv_prepend}:${LD_LIBRARY_PATH:-}:" in
        *":${_libcuda_dir}:"*) ;;
        *) _nv_prepend="${_libcuda_dir}${_nv_prepend:+:}${_nv_prepend}" ;;
    esac
fi

_pip_nv="$(
    python - <<'PY'
import glob
import os
import sysconfig

roots = []
for key in ("purelib", "platlib"):
    p = sysconfig.get_paths().get(key)
    if p:
        roots.append(p)
try:
    import site

    roots.extend(site.getsitepackages())
except Exception:
    pass
seen = []
for root in roots:
    if not root or not os.path.isdir(root):
        continue
    for lib in sorted(glob.glob(os.path.join(root, "nvidia", "*", "lib"))):
        if os.path.isdir(lib) and lib not in seen:
            seen.append(lib)
print(":".join(seen))
PY
)"
if [ -n "${_pip_nv}" ]; then
    _nv_prepend="${_pip_nv}${_nv_prepend:+:}${_nv_prepend}"
fi

if [ -n "${_nv_prepend}" ]; then
    LD_LIBRARY_PATH="${_nv_prepend}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi
export LD_LIBRARY_PATH
unset _nv_prepend _cuda_lib _libcuda_file _libcuda_dir _pip_nv
