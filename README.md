# image-rescaler

Batch image rescaler built from **pure Python** (standard library only — no Pillow, no NumPy) and a small **C++** resampling core. Python parses and re-encodes the image files and walks the directory; C++ does the per-pixel resampling math through a shared library loaded with `ctypes`. A pure-Python resampler is included as a fallback, so the tool works even before the C++ library is built.

## Usage

```sh
make                                  # build the C++ library (clang/gcc)
python3 -m rescale <directory> <width> <height> [options]
```

Examples:

```sh
python3 -m rescale ./photos 800 600                       # bilinear, C++ backend
python3 -m rescale ./photos 64 64 --method nearest        # nearest-neighbor
python3 -m rescale ./photos 1920 1080 --backend python    # force pure-Python resampling
python3 -m rescale ./photos 800 600 --output-dir ./out    # default is <directory>/resized
```

Supported formats: **PNG** (8-bit grayscale, grayscale+alpha, RGB, RGBA, indexed; non-interlaced) and **BMP** (uncompressed 24/32-bit). Outputs are written in the same format as the input.

## Layout

| Path | Role |
|---|---|
| [cpp/resize.cpp](cpp/resize.cpp) | C++ nearest-neighbor and bilinear kernels (C ABI) |
| [rescale/png_codec.py](rescale/png_codec.py) | Pure-Python PNG decoder/encoder |
| [rescale/bmp_codec.py](rescale/bmp_codec.py) | Pure-Python BMP decoder/encoder |
| [rescale/resize_py.py](rescale/resize_py.py) | Pure-Python resampling fallback |
| [rescale/native.py](rescale/native.py) | ctypes bridge to the C++ library |
| [rescale/cli.py](rescale/cli.py) | CLI: directory walk, dispatch, reporting |

## Techniques used

### Pure Python (standard library only)

**PNG decoding/encoding** (`rescale/png_codec.py`)
- Magic-byte signature validation (`\x89PNG\r\n\x1a\n`)
- Chunk-stream parsing: length / type / payload / CRC framing of IHDR, PLTE, IDAT, IEND
- Big-endian binary unpacking of headers with `struct.unpack` (`>I4s`, `>IIBBBBB`)
- CRC-32 integrity verification of every chunk via `zlib.crc32`
- DEFLATE decompression of the concatenated IDAT stream, and recompression on encode, via the stdlib `zlib` module
- Reversal of all five PNG scanline filters: None, Sub, Up, Average, and the **Paeth predictor**
- Color-space normalization to interleaved RGBA: grayscale and grayscale+alpha expansion, RGB alpha-padding, and **indexed-color palette lookup** through the PLTE chunk
- PNG encoding: per-scanline filter-byte emission, IHDR/IDAT/IEND chunk assembly with computed CRCs

**BMP decoding/encoding** (`rescale/bmp_codec.py`)
- Little-endian parsing of `BITMAPFILEHEADER` / `BITMAPINFOHEADER` with `struct.unpack_from`
- 4-byte scanline padding (BMP rows align to 32-bit boundaries)
- Bottom-up vs. top-down row order handling (sign of the height field)
- BGR(A) ↔ RGBA channel reordering
- 24-bit BMP encoding with computed row stride, pixel-data offset, and file size

**Pixel handling and resampling fallback** (`rescale/resize_py.py`)
- Flat interleaved `bytearray` pixel buffers indexed with `(y * width + x) * channels` arithmetic (no 2-D structures, no NumPy)
- Pure-Python nearest-neighbor resampling using integer source-index mapping
- Pure-Python bilinear interpolation with pixel-center coordinate mapping, edge clamping, and precomputed per-column sample positions/weights

**Native interop and CLI** (`rescale/native.py`, `rescale/cli.py`)
- `ctypes` foreign-function interface: loading a platform-specific shared library (`.dylib`/`.so`/`.dll`), declaring `argtypes`/`restype`, and passing buffers as `c_ubyte` arrays — including **zero-copy output** via `from_buffer` on a `bytearray`
- Graceful backend selection: auto-detect the compiled library, fall back to pure Python
- `argparse` CLI with choices/validation, `pathlib` directory traversal and case-insensitive extension matching, per-file error isolation (a corrupt file is reported and skipped, not fatal)

### C++ (`cpp/resize.cpp`)

- **Nearest-neighbor resampling**: destination → source index mapping with 64-bit integer math (`(y * sh) / dh`) to avoid overflow and floating-point drift
- **Bilinear interpolation**: pixel-center coordinate mapping (`(x + 0.5) * scale - 0.5`) so the image content doesn't shift, 2×2 neighborhood weighted blending per channel, and border handling by **edge clamping** (neighbor replication)
- Rounding to 8-bit via `+0.5f` truncation
- Channel-count-agnostic kernels operating on raw interleaved `uint8_t` buffers with `size_t` pointer arithmetic (overflow-safe indexing for large images)
- `extern "C"` linkage to disable name mangling, giving a stable C ABI that `ctypes` can call
- Built as a **position-independent shared library** (`-fPIC -shared -O2`), with a `Makefile` that picks `.dylib` vs `.so` per platform

## Limitations

- PNG: 8-bit samples only, no Adam7 interlacing, no `tRNS` transparency chunk
- BMP: no RLE compression, no ≤8-bit palette BMPs
- BMP output discards alpha (24-bit); PNG output preserves it (RGBA)
