"""Image validation and variant generation.

Uploaded bytes are decoded with Pillow regardless of the claimed extension or content type, then
re-encoded. Re-encoding strips EXIF/GPS metadata and neutralises malformed or polyglot files.
"""

import io
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG": ("image/jpeg", "jpg"), "PNG": ("image/png", "png"), "WEBP": ("image/webp", "webp")}
MAX_PIXELS = 40_000_000
VARIANT_WIDTHS = {"sm": 480, "lg": 1280}

Image.MAX_IMAGE_PIXELS = MAX_PIXELS


class ImageRejected(ValueError):
    pass


@dataclass
class Encoded:
    data: bytes
    content_type: str
    ext: str
    width: int
    height: int


@dataclass
class ProcessedImage:
    original: Encoded
    variants: dict[str, Encoded]


def process_image(data: bytes) -> ProcessedImage:
    try:
        with Image.open(io.BytesIO(data)) as probe:
            fmt = probe.format
            probe.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, SyntaxError) as e:
        raise ImageRejected("Dosya geçerli bir görsel değil. JPEG, PNG veya WebP yükleyin.") from e
    if fmt not in ALLOWED_FORMATS:
        raise ImageRejected("Desteklenmeyen görsel biçimi. JPEG, PNG veya WebP yükleyin.")

    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (OSError, Image.DecompressionBombError) as e:
        raise ImageRejected("Görsel okunamadı veya çok büyük.") from e
    if img.width * img.height > MAX_PIXELS:
        raise ImageRejected("Görselin çözünürlüğü çok yüksek.")

    img = ImageOps.exif_transpose(img)
    icc = img.info.get("icc_profile")
    content_type, ext = ALLOWED_FORMATS[fmt]
    original = Encoded(_encode(img, fmt, icc), content_type, ext, img.width, img.height)

    variants: dict[str, Encoded] = {}
    for name, target_w in VARIANT_WIDTHS.items():
        if img.width > target_w:
            h = round(img.height * target_w / img.width)
            v = img.resize((target_w, h), Image.Resampling.LANCZOS)
        else:
            v = img
        variants[name] = Encoded(_encode(v, "WEBP", icc), "image/webp", "webp", v.width, v.height)
    return ProcessedImage(original, variants)


def _encode(img: Image.Image, fmt: str, icc) -> bytes:
    out = io.BytesIO()
    kwargs = {"icc_profile": icc} if icc else {}
    if fmt == "JPEG":
        img.convert("RGB").save(out, "JPEG", quality=90, optimize=True, progressive=True, **kwargs)
    elif fmt == "PNG":
        img.save(out, "PNG", optimize=True, **kwargs)
    else:
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
        img.save(out, "WEBP", quality=82, method=5, **kwargs)
    return out.getvalue()
