"""ctypes bridge to the C++ resampling library built from cpp/resize.cpp."""

import ctypes
import sys
from pathlib import Path

_LIB_NAMES = {"darwin": "libresize.dylib", "win32": "resize.dll"}


def _lib_path():
    name = _LIB_NAMES.get(sys.platform, "libresize.so")
    return Path(__file__).resolve().parent.parent / "build" / name


def load():
    """Load the shared library if it has been built (`make`). Returns None otherwise."""
    path = _lib_path()
    if not path.exists():
        return None
    lib = ctypes.CDLL(str(path))
    u8p = ctypes.POINTER(ctypes.c_ubyte)
    for fn in ("resize_nearest", "resize_bilinear"):
        func = getattr(lib, fn)
        func.argtypes = [u8p, ctypes.c_int, ctypes.c_int,
                         u8p, ctypes.c_int, ctypes.c_int, ctypes.c_int]
        func.restype = None
    return lib


def resize(lib, method, src, sw, sh, dw, dh, channels=4):
    """Run one of the C++ kernels over a Python byte buffer, zero-copy where possible."""
    dst = bytearray(dw * dh * channels)
    src_arr = (ctypes.c_ubyte * len(src)).from_buffer_copy(src)
    dst_arr = (ctypes.c_ubyte * len(dst)).from_buffer(dst)
    func = lib.resize_bilinear if method == "bilinear" else lib.resize_nearest
    func(src_arr, sw, sh, dst_arr, dw, dh, channels)
    return dst
