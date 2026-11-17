# Photo shrinker

![Photo shrinker: PNG goes in, JPG comes out](docs/banner.jpg)

Resize, compress and convert photos in your browser. Nothing is uploaded.

**[Open the app](https://davydmedvedchuk.github.io/photo-shrinker/)**

Pick photos, choose a size and a format, save. One photo or a ZIP. It runs entirely in the page, so your pictures never leave your device. No account, no ads, no install.

## What it does

- **Resize.** Longest side: original, 3000, 2048, 1600, 1200, 800, 400 px or any number you type.
- **Compress.** A quality slider for JPEG and WebP.
- **Max file size.** Say "under 200 KB" and it finds the best quality that fits. If quality alone is not enough, it shrinks the picture a little.
- **Convert.** Save as JPEG, PNG, WebP, BMP or ICO.
- **Many photos at once.** Download one by one, as a ZIP, or as a single PDF (one photo per A4 page).
- **HEIC.** iPhone photos open on any browser. The decoder loads only when you add a HEIC file.
- **Privacy.** Saving a photo again removes EXIF data, including GPS location.
- **Already small?** If a photo can't get smaller, you get the original back, not a bigger file.

## Formats

| In | Out |
| --- | --- |
| JPEG, PNG, WebP, GIF (first frame), BMP, HEIC. What else works depends on your browser. | JPEG, PNG, WebP\*, BMP, ICO, PDF, ZIP |

\*Safari can't encode WebP, so the option is hidden there.

## Run it yourself

It is a static page. Open `index.html`, or serve the folder:

```
python3 -m http.server
```

Then go to `http://localhost:8000`.

## How it works

Each photo is decoded by the browser, drawn on a canvas at the new size and encoded again. "Max file size" is a binary search over the quality value. The ZIP and PDF writers are small and live in `index.html`, so there is nothing to build.

## Not included

No AVIF, GIF or TIFF output. No option to keep EXIF. Very large photos can be slow on old phones.

## Credits

Made by Davyd Medvedchuk. HEIC decoding uses [heic2any](https://github.com/alexcorvi/heic2any) (MIT, see `vendor/LICENSE-heic2any.md`).

MIT licence.
