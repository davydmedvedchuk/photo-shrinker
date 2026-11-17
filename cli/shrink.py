#!/usr/bin/env python3
"""Photo shrinker, command-line version.

Resize, compress and convert a whole folder of photos with one command.
Same idea as the web app next to it, written in Python (Pillow + pillow-heif).

  python3 shrink.py ./photos                       # 2048 px JPEGs into ./shrunk
  python3 shrink.py ./photos -s 1200 -m 200        # longest side 1200 px, each file under 200 KB
  python3 shrink.py a.heic b.png -f webp --zip     # convert and pack into one ZIP
"""
import argparse, io, shutil, sys, zipfile
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError:
    sys.exit("Pillow is missing. Install it with:  pip install -r requirements.txt")
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass  # HEIC input just won't open

EXT_IN = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff", ".heic", ".heif"}
FORMATS = {"jpg": ("JPEG", ".jpg"), "png": ("PNG", ".png"), "webp": ("WEBP", ".webp"),
           "bmp": ("BMP", ".bmp"), "ico": ("ICO", ".ico")}
LOSSY = {"jpg", "webp"}


def find_files(paths, recursive):
    for p in map(Path, paths):
        if p.is_dir():
            it = p.rglob("*") if recursive else p.glob("*")
            yield from sorted(f for f in it if f.suffix.lower() in EXT_IN and f.is_file())
        elif p.suffix.lower() in EXT_IN and p.is_file():
            yield p
        else:
            print(f"skip: {p}", file=sys.stderr)


def encode(img, fmt, quality):
    buf = io.BytesIO()
    name = FORMATS[fmt][0]
    if fmt == "jpg":
        img.save(buf, name, quality=quality, optimize=True, progressive=True)
    elif fmt == "webp":
        img.save(buf, name, quality=quality, method=6)
    elif fmt == "png":
        img.save(buf, name, optimize=True)
    elif fmt == "ico":
        img.save(buf, name, sizes=[img.size])
    else:
        img.save(buf, name)
    return buf.getvalue()


def prepare(src, size, fmt):
    img = ImageOps.exif_transpose(Image.open(src))      # apply rotation; saving drops EXIF/GPS
    if fmt in ("jpg", "bmp"):                            # no transparency: paint it white
        if img.mode in ("RGBA", "LA", "P"):
            rgba = img.convert("RGBA")
            bg = Image.new("RGB", rgba.size, "white")
            bg.paste(rgba, mask=rgba.split()[3])
            img = bg
        else:
            img = img.convert("RGB")
    elif img.mode not in ("RGB", "RGBA", "L"):
        img = img.convert("RGBA")
    if fmt == "ico":
        size = min(size or 256, 256)
    if size and max(img.size) > size:
        k = size / max(img.size)
        img = img.resize((max(1, round(img.width * k)), max(1, round(img.height * k))), Image.LANCZOS)
    return img


def fit(img, fmt, target):
    """Best quality that stays under `target` bytes; shrink the picture a bit if quality alone can't."""
    for _ in range(12):
        lo, hi, best = 15, 92, None
        if len(encode(img, fmt, lo)) <= target:
            for _ in range(6):
                if len(encode(img, fmt, hi)) <= target:
                    best = encode(img, fmt, hi); break
                mid = (lo + hi) // 2
                data = encode(img, fmt, mid)
                if len(data) <= target: best, lo = data, mid
                else: hi = mid
            return best or encode(img, fmt, lo), img.size
        img = img.resize((max(1, int(img.width * .85)), max(1, int(img.height * .85))), Image.LANCZOS)
    return encode(img, fmt, 15), img.size


def human(n):
    return f"{n/1024/1024:.1f} MB" if n >= 1024 * 1024 else f"{n/1024:.0f} KB"


def main():
    ap = argparse.ArgumentParser(description="Resize, compress and convert photos.")
    ap.add_argument("inputs", nargs="+", help="files or folders")
    ap.add_argument("-o", "--out", default="shrunk", help="output folder (default: shrunk)")
    ap.add_argument("-s", "--size", type=int, default=2048, help="longest side in px, 0 = keep (default: 2048)")
    ap.add_argument("-f", "--format", choices=FORMATS, default="jpg", help="output format (default: jpg)")
    ap.add_argument("-q", "--quality", type=int, default=80, help="1-95, JPEG and WebP only (default: 80)")
    ap.add_argument("-m", "--max-kb", type=int, default=0, help="keep each file under this many KB")
    ap.add_argument("-r", "--recursive", action="store_true", help="look inside subfolders")
    ap.add_argument("--zip", action="store_true", help="pack results into one ZIP")
    ap.add_argument("--pdf", action="store_true", help="also make one PDF, one photo per page")
    a = ap.parse_args()

    files = list(find_files(a.inputs, a.recursive))
    if not files:
        sys.exit("No images found.")
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    fmt, ext = a.format, FORMATS[a.format][1]
    done, before, after, pages, used = 0, 0, 0, [], set()

    for src in files:
        try:
            img = prepare(src, a.size, fmt)
            if a.max_kb and fmt in LOSSY:
                data, dims = fit(img, fmt, a.max_kb * 1024)
            else:
                data, dims = encode(img, fmt, a.quality), img.size
                # already compressed? try lower quality before giving up
                q = a.quality
                orig_same = src.suffix.lower() in (".jpg", ".jpeg") and fmt == "jpg" and dims == Image.open(src).size
                while orig_same and len(data) >= src.stat().st_size and q > 40:
                    q = max(40, q - 15); data = encode(img, fmt, q)
        except Exception as e:
            print(f"fail: {src.name}: {e}", file=sys.stderr); continue

        name, n = src.stem + "-small" + ext, 2
        while name in used: name, n = f"{src.stem}-small-{n}{ext}", n + 1
        used.add(name)
        o, size0 = src.stat().st_size, len(data)
        if size0 >= o and src.suffix.lower() in (".jpg", ".jpeg", ".webp", ".png") and fmt == {".jpg": "jpg", ".jpeg": "jpg", ".webp": "webp", ".png": "png"}[src.suffix.lower()] and dims == Image.open(src).size:
            (out / (src.stem + src.suffix.lower())).write_bytes(src.read_bytes())
            data, size0, name = src.read_bytes(), o, src.stem + src.suffix.lower()
            tag = "kept original"
        else:
            (out / name).write_bytes(data); tag = f"-{100 - size0 * 100 // max(o, 1)}%"
        before += o; after += size0; done += 1
        if a.pdf:
            pages.append(Image.open(io.BytesIO(data)).convert("RGB"))
        print(f"{src.name:<32} {human(o):>8} -> {human(size0):>8}  {dims[0]}x{dims[1]}  {tag}")

    if a.pdf and pages:
        pages[0].save(out / "photos.pdf", save_all=True, append_images=pages[1:], resolution=150)
        print(f"PDF: {out / 'photos.pdf'}")
    if a.zip:
        z = out / "photos.zip"
        with zipfile.ZipFile(z, "w", zipfile.ZIP_STORED) as zf:
            for n in sorted(used):
                if (out / n).exists(): zf.write(out / n, n)
        print(f"ZIP: {z}")
    print(f"\n{done} photo(s): {human(before)} -> {human(after)}" + (f"  (-{100 - after * 100 // before}%)" if before else ""))


if __name__ == "__main__":
    main()
