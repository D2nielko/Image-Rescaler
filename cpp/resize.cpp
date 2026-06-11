// Image resampling kernels, exposed with a C ABI so Python can load the
// compiled shared library through ctypes.
#include <cstdint>
#include <cmath>
#include <cstddef>

namespace {

inline int clampi(int v, int lo, int hi) {
    return v < lo ? lo : (v > hi ? hi : v);
}

} // namespace

extern "C" {

// Nearest-neighbor: each destination pixel copies the closest source pixel.
// Source index is computed with 64-bit integer math to avoid overflow and
// floating-point drift.
void resize_nearest(const uint8_t* src, int sw, int sh,
                    uint8_t* dst, int dw, int dh, int channels) {
    for (int y = 0; y < dh; ++y) {
        const int sy = static_cast<int>((static_cast<int64_t>(y) * sh) / dh);
        for (int x = 0; x < dw; ++x) {
            const int sx = static_cast<int>((static_cast<int64_t>(x) * sw) / dw);
            const uint8_t* sp = src + (static_cast<size_t>(sy) * sw + sx) * channels;
            uint8_t* dp = dst + (static_cast<size_t>(y) * dw + x) * channels;
            for (int c = 0; c < channels; ++c) {
                dp[c] = sp[c];
            }
        }
    }
}

// Bilinear: each destination pixel is a weighted blend of the 2x2 source
// neighborhood around its mapped position. Coordinates are mapped through
// pixel centers ((x + 0.5) * scale - 0.5) so the image does not shift, and
// neighbors are clamped at the borders (edge replication).
void resize_bilinear(const uint8_t* src, int sw, int sh,
                     uint8_t* dst, int dw, int dh, int channels) {
    const float x_scale = static_cast<float>(sw) / dw;
    const float y_scale = static_cast<float>(sh) / dh;

    for (int y = 0; y < dh; ++y) {
        float fy = (y + 0.5f) * y_scale - 0.5f;
        if (fy < 0.0f) fy = 0.0f;
        const int y0 = clampi(static_cast<int>(fy), 0, sh - 1);
        const int y1 = clampi(y0 + 1, 0, sh - 1);
        const float wy = fy - y0;

        for (int x = 0; x < dw; ++x) {
            float fx = (x + 0.5f) * x_scale - 0.5f;
            if (fx < 0.0f) fx = 0.0f;
            const int x0 = clampi(static_cast<int>(fx), 0, sw - 1);
            const int x1 = clampi(x0 + 1, 0, sw - 1);
            const float wx = fx - x0;

            const uint8_t* p00 = src + (static_cast<size_t>(y0) * sw + x0) * channels;
            const uint8_t* p01 = src + (static_cast<size_t>(y0) * sw + x1) * channels;
            const uint8_t* p10 = src + (static_cast<size_t>(y1) * sw + x0) * channels;
            const uint8_t* p11 = src + (static_cast<size_t>(y1) * sw + x1) * channels;
            uint8_t* dp = dst + (static_cast<size_t>(y) * dw + x) * channels;

            for (int c = 0; c < channels; ++c) {
                const float top = p00[c] + (p01[c] - p00[c]) * wx;
                const float bottom = p10[c] + (p11[c] - p10[c]) * wx;
                const float value = top + (bottom - top) * wy;
                dp[c] = static_cast<uint8_t>(value + 0.5f);
            }
        }
    }
}

} // extern "C"
