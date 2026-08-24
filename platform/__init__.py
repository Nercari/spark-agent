"""Bridge package enabling platform/ directory while preserving stdlib platform module attributes."""
import sys
import os
import importlib.util

_stdlib_path = None
for p in sys.path:
    if "c_b490a8c7dd21c813" in p or p == "" or p == ".":
        continue
    candidate = os.path.join(p, "platform.py")
    if os.path.isfile(candidate):
        _stdlib_path = candidate
        break

if _stdlib_path:
    spec = importlib.util.spec_from_file_location("_stdlib_platform", _stdlib_path)
    _mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_mod)
    for attr in dir(_mod):
        if not attr.startswith("__"):
            globals()[attr] = getattr(_mod, attr)
