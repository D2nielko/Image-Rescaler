"""Pure-Python BMP decoder/encoder using only the standard library.

Supports uncompressed (BI_RGB) 24- and 32-bit BMPs. Decoded images are
normalized to a flat interleaved RGBA bytearray; encoding writes 24-bit
bottom-up BMPs.
"""

import struct


def decode(data):
    """Decode BMP bytes. Returns (width, height, rgba_bytearray)."""
    if data[:2] != b"BM":
        raise ValueError("not a BMP file")
    (pixel_offset,) = struct.unpack_from("<I", data, 10)
    width, height = struct.unpack_from("<ii", data, 18)
    _planes, bpp = struct.unpack_from("<HH", data, 26)
    (compression,) = struct.unpack_from("<I", data, 30)
    if compression != 0:
        raise ValueError(f"only uncompressed (BI_RGB) BMPs are supported")
    if bpp not in (24, 32):
        raise ValueError(f"only 24/32-bit BMPs are supported (got {bpp}-bit)")

    bottom_up = height > 0  # positive height means rows are stored bottom-to-top
    height = abs(height)
    bytes_pp = bpp // 8
    row_size = ((width * bytes_pp + 3) // 4) * 4  # rows pad to 4-byte boundaries

    rgba = bytearray(width * height * 4)
    for y in range(height):
        src_y = height - 1 - y if bottom_up else y
        base = pixel_offset + src_y * row_size
        for x in range(width):
            i = base + x * bytes_pp
            d = (y * width + x) * 4
            # BMP stores channels as BGR(A)
            rgba[d] = data[i + 2]
            rgba[d + 1] = data[i + 1]
            rgba[d + 2] = data[i]
            rgba[d + 3] = data[i + 3] if bytes_pp == 4 else 255
    return width, height, rgba


def encode(width, height, rgba):
    """Encode interleaved RGBA bytes as a 24-bit bottom-up BMP. Returns bytes."""
    row_size = ((width * 3 + 3) // 4) * 4
    pixel_bytes = row_size * height
    pixel_offset = 14 + 40
    file_size = pixel_offset + pixel_bytes

    out = bytearray()
    out += struct.pack("<2sIHHI", b"BM", file_size, 0, 0, pixel_offset)
    out += struct.pack("<IiiHHIIiiII", 40, width, height, 1, 24, 0,
                       pixel_bytes, 2835, 2835, 0, 0)

    pad = b"\x00" * (row_size - width * 3)
    for y in range(height - 1, -1, -1):  # bottom-up row order
        for x in range(width):
            s = (y * width + x) * 4
            out += bytes((rgba[s + 2], rgba[s + 1], rgba[s]))  # RGB -> BGR
        out += pad
    return bytes(out)
