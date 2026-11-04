import pathlib, subprocess, sys

ver, cuda = "", None
try:
    import torch
    ver, cuda = torch.__version__, torch.version.cuda
except Exception as exc:
    print("TORCH_PRE unavailable:", exc, file=sys.stderr)

print("TORCH_PRE version=%s cuda=%s" % (ver, cuda), flush=True)
pathlib.Path("/tmp/torch_pre.txt").write_text("%s|%s\n" % (ver, cuda), encoding="utf-8")

family = ("torch", "torchvision", "torchaudio", "torchtext", "torchdata")
lines = []
try:
    out = subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True)
except Exception as exc:
    print("pip freeze failed:", exc, file=sys.stderr)
    out = ""
for line in out.splitlines():
    name = line.split("==", 1)[0].split("@", 1)[0].strip().lower()
    if name in family:
        lines.append(line.strip())
pathlib.Path("/tmp/torch-constraints.txt").write_text(
    "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8"
)
print("TORCH_CONSTRAINTS:", flush=True)
print("\n".join(lines) or "(none)", flush=True)
