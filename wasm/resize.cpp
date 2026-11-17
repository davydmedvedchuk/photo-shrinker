// Lanczos-3 image resizer for the browser. Plain C++, no libraries, compiled to WebAssembly.
// Input and output are RGBA, 8 bits per channel. Alpha is handled correctly (premultiplied while filtering).
//
// Build: ./build.sh   (clang with the wasm32 target + wasm-ld)

typedef unsigned char u8;
typedef unsigned int u32;
typedef float f32;

extern "C" u8 __heap_base;

// ---- a tiny bump allocator on top of WebAssembly memory ----
static u32 heap_ptr = 0;

static u8* take(u32 n) {
  if (!heap_ptr) heap_ptr = (u32)&__heap_base;
  u32 p = (heap_ptr + 15u) & ~15u;
  u32 end = p + n;
  u32 have = (u32)__builtin_wasm_memory_size(0) * 65536u;
  if (end > have) {
    u32 pages = (end - have + 65535u) / 65536u;
    if (__builtin_wasm_memory_grow(0, pages) == (__SIZE_TYPE__)-1) return 0;
  }
  heap_ptr = end;
  return (u8*)p;
}

// ---- math without libc ----
static f32 sinpi_(f32 x) {                       // sin(pi * x)
  f32 r = x - 2.0f * __builtin_floorf(x * 0.5f + 0.5f);   // -> [-1, 1]
  if (r > 0.5f) r = 1.0f - r; else if (r < -0.5f) r = -1.0f - r;
  f32 t = r * 3.14159265f, t2 = t * t;
  return t * (1.0f - t2 / 6.0f * (1.0f - t2 / 20.0f * (1.0f - t2 / 42.0f * (1.0f - t2 / 72.0f * (1.0f - t2 / 110.0f)))));
}

static f32 lanczos3(f32 x) {
  if (x < 0) x = -x;
  if (x < 1e-6f) return 1.0f;
  if (x >= 3.0f) return 0.0f;
  return 3.0f * sinpi_(x) * sinpi_(x / 3.0f) / (9.8696044f * x * x);
}

static inline f32 clamp255(f32 v) { return v < 0 ? 0 : (v > 255 ? 255 : v); }

// For every destination pixel: which source pixels contribute, and how much.
static void build(int src, int dst, int maxTaps, int* start, int* count, f32* w) {
  f32 scale = (f32)src / (f32)dst;
  f32 fs = scale > 1.0f ? scale : 1.0f, support = 3.0f * fs;
  for (int d = 0; d < dst; d++) {
    f32 c = ((f32)d + 0.5f) * scale;
    int lo = (int)__builtin_ceilf(c - support - 0.5f), hi = (int)__builtin_floorf(c + support - 0.5f);
    if (lo < 0) lo = 0;
    if (hi > src - 1) hi = src - 1;
    f32 sum = 0;
    f32* wd = w + d * maxTaps;
    for (int i = lo; i <= hi; i++) { f32 v = lanczos3(((f32)i + 0.5f - c) / fs); wd[i - lo] = v; sum += v; }
    if (sum != 0) for (int i = 0; i <= hi - lo; i++) wd[i] /= sum;
    start[d] = lo; count[d] = hi - lo + 1;
  }
}

extern "C" {

__attribute__((export_name("reset"))) void reset() { heap_ptr = (u32)&__heap_base; }

__attribute__((export_name("alloc"))) u8* alloc(u32 n) { return take(n); }

// Returns 0 on success, 1 if memory ran out.
// flatten = 1: paint transparent areas white and return opaque pixels (for JPEG and BMP).
__attribute__((export_name("resize")))
int resize(const u8* src, int sw, int sh, u8* dst, int dw, int dh, int flatten) {
  f32 sx = (f32)sw / (f32)dw, sy = (f32)sh / (f32)dh;
  int tapsX = (int)(6.0f * (sx > 1 ? sx : 1.0f)) + 3, tapsY = (int)(6.0f * (sy > 1 ? sy : 1.0f)) + 3;

  int* startX = (int*)take(dw * 4); int* countX = (int*)take(dw * 4); f32* wX = (f32*)take(dw * tapsX * 4);
  int* startY = (int*)take(dh * 4); int* countY = (int*)take(dh * 4); f32* wY = (f32*)take(dh * tapsY * 4);
  u8* mid = take((u32)sh * (u32)dw * 4u);          // after the horizontal pass: dw x sh
  f32* acc = (f32*)take(dw * 16);
  if (!startX || !countX || !wX || !startY || !countY || !wY || !mid || !acc) return 1;

  build(sw, dw, tapsX, startX, countX, wX);
  build(sh, dh, tapsY, startY, countY, wY);

  // pass 1: horizontal, on premultiplied colour
  for (int y = 0; y < sh; y++) {
    const u8* row = src + (u32)y * (u32)sw * 4u;
    u8* out = mid + (u32)y * (u32)dw * 4u;
    for (int x = 0; x < dw; x++) {
      const f32* w = wX + x * tapsX;
      const u8* p = row + startX[x] * 4;
      f32 r = 0, g = 0, b = 0, a = 0;
      for (int k = 0; k < countX[x]; k++, p += 4) {
        f32 wa = w[k] * (f32)p[3];
        a += wa; wa *= (1.0f / 255.0f);
        r += wa * p[0]; g += wa * p[1]; b += wa * p[2];
      }
      out[0] = (u8)(clamp255(r) + 0.5f); out[1] = (u8)(clamp255(g) + 0.5f);
      out[2] = (u8)(clamp255(b) + 0.5f); out[3] = (u8)(clamp255(a) + 0.5f);
      out += 4;
    }
  }

  // pass 2: vertical, one output row at a time
  for (int y = 0; y < dh; y++) {
    for (int i = 0; i < dw * 4; i++) acc[i] = 0;
    const f32* w = wY + y * tapsY;
    for (int k = 0; k < countY[y]; k++) {
      const u8* row = mid + (u32)(startY[y] + k) * (u32)dw * 4u;
      f32 wk = w[k];
      for (int i = 0; i < dw * 4; i++) acc[i] += wk * row[i];
    }
    u8* out = dst + (u32)y * (u32)dw * 4u;
    for (int x = 0; x < dw; x++) {
      f32 a = clamp255(acc[x * 4 + 3]);
      f32 r = acc[x * 4], g = acc[x * 4 + 1], b = acc[x * 4 + 2];
      if (flatten) {
        f32 bg = 255.0f - a;
        r += bg; g += bg; b += bg; a = 255.0f;
      } else if (a > 0.5f) {
        f32 k = 255.0f / a; r *= k; g *= k; b *= k;
      } else { r = g = b = 0; }
      out[0] = (u8)(clamp255(r) + 0.5f); out[1] = (u8)(clamp255(g) + 0.5f);
      out[2] = (u8)(clamp255(b) + 0.5f); out[3] = (u8)(a + 0.5f);
      out += 4;
    }
  }
  return 0;
}

}
