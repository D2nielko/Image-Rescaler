"""Command-line interface: rescale every PNG/BMP in a directory to a target size.

Usage:
    python3 -m rescale <directory> <width> <height> [--method bilinear|nearest]
                       [--backend auto|cpp|python] [--output-dir DIR]
"""

import argparse
import sys
from pathlib import Path

from . import bmp_codec, native, png_codec, resize_py

_CODECS = {".png": png_codec, ".bmp": bmp_codec}


def _parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="rescale",
        description="Rescale all PNG/BMP images in a directory to the given size.",
    )
    parser.add_argument("directory", type=Path, help="directory containing images")
    parser.add_argument("width", type=int, help="target width in pixels")
    parser.add_argument("height", type=int, help="target height in pixels")
    parser.add_argument("--method", choices=("bilinear", "nearest"), default="bilinear",
                        help="resampling method (default: bilinear)")
    parser.add_argument("--backend", choices=("auto", "cpp", "python"), default="auto",
                        help="auto uses the C++ library when built, "
                             "falling back to pure Python (default: auto)")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="where to write results (default: <directory>/resized)")
    return parser.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv)
    if args.width <= 0 or args.height <= 0:
        sys.exit("error: width and height must be positive")
    if not args.directory.is_dir():
        sys.exit(f"error: {args.directory} is not a directory")

    lib = native.load() if args.backend in ("auto", "cpp") else None
    if args.backend == "cpp" and lib is None:
        sys.exit("error: C++ library not built — run `make` first")
    backend = "cpp" if lib is not None else "python"

    out_dir = args.output_dir or args.directory / "resized"
    files = sorted(p for p in args.directory.iterdir()
                   if p.is_file() and p.suffix.lower() in _CODECS)
    if not files:
        sys.exit(f"error: no PNG or BMP files found in {args.directory}")

    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"backend: {backend}, method: {args.method}, "
          f"target: {args.width}x{args.height}")

    ok = failed = 0
    for path in files:
        codec = _CODECS[path.suffix.lower()]
        try:
            data = path.read_bytes()
            sw, sh, rgba = codec.decode(data)
            if lib is not None:
                resized = native.resize(lib, args.method, rgba, sw, sh,
                                        args.width, args.height)
            elif args.method == "bilinear":
                resized = resize_py.resize_bilinear(rgba, sw, sh,
                                                    args.width, args.height)
            else:
                resized = resize_py.resize_nearest(rgba, sw, sh,
                                                   args.width, args.height)
            out_path = out_dir / path.name
            out_path.write_bytes(codec.encode(args.width, args.height, resized))
            print(f"  {path.name}: {sw}x{sh} -> {args.width}x{args.height}")
            ok += 1
        except (ValueError, OSError) as exc:
            print(f"  {path.name}: skipped ({exc})", file=sys.stderr)
            failed += 1

    print(f"done: {ok} rescaled, {failed} skipped -> {out_dir}")
    return 0 if failed == 0 else 1
