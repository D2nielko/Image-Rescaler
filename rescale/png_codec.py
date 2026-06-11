"""Pure-Python PNG decoder/encoder using only the standard library.

Supports 8-bit-per-sample, non-interlaced PNGs in grayscale, grayscale+alpha,
RGB, RGBA, and indexed (palette) color. Decoded images are normalized to a
flat interleaved RGBA bytearray.
"""

import struct
import zlib

SIGNATURE = b"\x89PNG\r\n\x1a\n"

# Samples per pixel for each PNG color type.
_CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


def _paeth(a, b, c):
    """Paeth predictor (PNG filter type 4): pick the neighbor closest to a+b-c."""
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _unfilter(raw, width, height, channels):
    """Reverse the per-scanline filters into raw pixel bytes."""
    stride = width * channels
    recon = bytearray(height * stride)
    pos = 0
    for y in range(height):
        ftype = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride
        off = y * stride
        prev = off - stride
        if ftype == 0:  # None
            pass
        elif ftype == 1:  # Sub
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif ftype == 2:  # Up
            if y:
                for i in range(stride):
                    line[i] = (line[i] + recon[prev + i]) & 0xFF
        elif ftype == 3:  # Average
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                up = recon[prev + i] if y else 0
                line[i] = (line[i] + ((left + up) >> 1)) & 0xFF
        elif ftype == 4:  # Paeth
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                b = recon[prev + i] if y else 0
                c = recon[prev + i - channels] if (y and i >= channels) else 0
                line[i] = (line[i] + _paeth(a, b, c)) & 0xFF
        else:
            raise ValueError(f"unknown PNG filter type {ftype}")
        recon[off:off + stride] = line
    return recon


def _to_rgba(recon, width, height, color_type, palette):
    """Expand decoded samples of any supported color type to interleaved RGBA."""
    n = width * height
    rgba = bytearray(n * 4)
    if color_type == 6:  # RGBA: already in target layout
        rgba[:] = recon
    elif color_type == 2:  # RGB
        for i in range(n):
            s, d = i * 3, i * 4
            rgba[d:d + 3] = recon[s:s + 3]
            rgba[d + 3] = 255
    elif color_type == 0:  # grayscale
        for i in range(n):
            d = i * 4
            rgba[d] = rgba[d + 1] = rgba[d + 2] = recon[i]
            rgba[d + 3] = 255
    elif color_type == 4:  # grayscale + alpha
        for i in range(n):
            s, d = i * 2, i * 4
            rgba[d] = rgba[d + 1] = rgba[d + 2] = recon[s]
            rgba[d + 3] = recon[s + 1]
    elif color_type == 3:  # indexed
        if not palette:
            raise ValueError("indexed PNG is missing a PLTE chunk")
        for i in range(n):
            s, d = recon[i] * 3, i * 4
            rgba[d:d + 3] = palette[s:s + 3]
            rgba[d + 3] = 255
    else:
        raise ValueError(f"unsupported PNG color type {color_type}")
    return rgba


def decode(data):
    """Decode PNG bytes. Returns (width, height, rgba_bytearray)."""
    if data[:8] != SIGNATURE:
        raise ValueError("not a PNG file")

    width = height = None
    color_type = None
    palette = b""
    idat = bytearray()
    pos = 8
    while pos + 8 <= len(data):
        length, ctype = struct.unpack_from(">I4s", data, pos)
        chunk = data[pos + 8:pos + 8 + length]
        (crc,) = struct.unpack_from(">I", data, pos + 8 + length)
        if zlib.crc32(ctype + chunk) & 0xFFFFFFFF != crc:
            raise ValueError(f"CRC mismatch in {ctype.decode('ascii', 'replace')} chunk")
        if ctype == b"IHDR":
            width, height, bit_depth, color_type, _comp, _filt, interlace = \
                struct.unpack(">IIBBBBB", chunk)
            if bit_depth != 8:
                raise ValueError(f"only 8-bit PNGs are supported (got {bit_depth}-bit)")
            if interlace != 0:
                raise ValueError("interlaced (Adam7) PNGs are not supported")
        elif ctype == b"PLTE":
            palette = chunk
        elif ctype == b"IDAT":
            idat += chunk
        elif ctype == b"IEND":
            break
        pos += 12 + length

    if width is None:
        raise ValueError("PNG has no IHDR chunk")
    raw = zlib.decompress(bytes(idat))
    recon = _unfilter(raw, width, height, _CHANNELS[color_type])
    return width, height, _to_rgba(recon, width, height, color_type, palette)


def encode(width, height, rgba):
    """Encode interleaved RGBA bytes as an 8-bit RGBA PNG. Returns bytes."""
    stride = width * 4
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter type None for every scanline
        raw += rgba[y * stride:(y + 1) * stride]

    out = bytearray(SIGNATURE)

    def chunk(ctype, payload):
        out.extend(struct.pack(">I", len(payload)))
        out.extend(ctype)
        out.extend(payload)
        out.extend(struct.pack(">I", zlib.crc32(ctype + payload) & 0xFFFFFFFF))

    chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    chunk(b"IEND", b"")
    return bytes(out)
