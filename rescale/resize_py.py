"""Pure-Python resampling fallbacks, mirroring the C++ kernels in cpp/resize.cpp."""


def resize_nearest(src, sw, sh, dw, dh, channels=4):
    """Nearest-neighbor resampling over a flat interleaved byte buffer."""
    dst = bytearray(dw * dh * channels)
    for y in range(dh):
        sy = (y * sh) // dh
        src_row = sy * sw
        dst_row = y * dw
        for x in range(dw):
            sx = (x * sw) // dw
            s = (src_row + sx) * channels
            d = (dst_row + x) * channels
            dst[d:d + channels] = src[s:s + channels]
    return dst


def resize_bilinear(src, sw, sh, dw, dh, channels=4):
    """Bilinear resampling with pixel-center mapping and edge clamping."""
    dst = bytearray(dw * dh * channels)
    x_scale = sw / dw
    y_scale = sh / dh
    max_x = sw - 1
    max_y = sh - 1

    # Precompute horizontal sample positions and weights once per image.
    xs = []
    for x in range(dw):
        fx = (x + 0.5) * x_scale - 0.5
        if fx < 0.0:
            fx = 0.0
        x0 = min(int(fx), max_x)
        xs.append((x0, min(x0 + 1, max_x), fx - x0))

    for y in range(dh):
        fy = (y + 0.5) * y_scale - 0.5
        if fy < 0.0:
            fy = 0.0
        y0 = min(int(fy), max_y)
        y1 = min(y0 + 1, max_y)
        wy = fy - y0
        row0 = y0 * sw
        row1 = y1 * sw
        dst_row = y * dw
        for x in range(dw):
            x0, x1, wx = xs[x]
            p00 = (row0 + x0) * channels
            p01 = (row0 + x1) * channels
            p10 = (row1 + x0) * channels
            p11 = (row1 + x1) * channels
            d = (dst_row + x) * channels
            for c in range(channels):
                top = src[p00 + c] + (src[p01 + c] - src[p00 + c]) * wx
                bottom = src[p10 + c] + (src[p11 + c] - src[p10 + c]) * wx
                dst[d + c] = int(top + (bottom - top) * wy + 0.5)
    return dst
