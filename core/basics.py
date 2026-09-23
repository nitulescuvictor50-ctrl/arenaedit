"""
Operații de bază pe imagini (fără AI) — bazate pe Pillow.
Toate funcțiile sunt pure și testabile independent de interfața grafică.
"""
from __future__ import annotations

import os
import platform
from PIL import Image, ImageEnhance, ImageOps

# Limite de siguranță pentru dimensiuni
MIN_SIDE = 8
MAX_SIDE = 8192

FORMAT_EXT = {
    "PNG": ".png",
    "JPEG": ".jpg",
    "WEBP": ".webp",
    "BMP": ".bmp",
}


# ---------------------------------------------------------------- încărcare / salvare

def load_image(path: str) -> Image.Image:
    """Încarcă o imagine și o convertește în RGB (fără canal transparent)."""
    img = Image.open(path)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    return img


def save_image(img: Image.Image, path: str, fmt: str = "PNG", quality: int = 92) -> str:
    """Salvează imaginea în formatul cerut. Pentru JPEG asigură modul RGB."""
    if fmt.upper() not in FORMAT_EXT:
        raise ValueError(f"Format necunoscut: {fmt}")
    ext = FORMAT_EXT[fmt.upper()]
    if not path.lower().endswith(ext):
        path = path + ext
    if fmt.upper() == "JPEG" and img.mode != "RGB":
        img = img.convert("RGB")
    kwargs = {}
    if fmt.upper() in ("JPEG", "WEBP"):
        kwargs["quality"] = max(1, min(100, int(quality)))
    if fmt.upper() == "PNG":
        kwargs["optimize"] = True
    img.save(path, format=fmt.upper(), **kwargs)
    return path


def image_info(path: str) -> dict:
    """Returnează informații despre fișierul imagine (dimensiuni, mărime)."""
    with Image.open(path) as img:
        w, h = img.size
    size = os.path.getsize(path)
    return {
        "path": path,
        "width": w,
        "height": h,
        "bytes": size,
        "size_text": _human_size(size),
    }


def _human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} TB"


def paste_from_clipboard():
    """
    Citeste o imagine din clipboard-ul Windows.
    Returnează PIL.Image sau None. Poate returna și o cale de fișier copiată
    în Explorer (atunci încarcă primul fișier imagine găsit).
    """
    if platform.system() != "Windows":
        return None
    try:
        from PIL import ImageGrab
        data = ImageGrab.grabclipboard()
    except Exception:
        return None
    if isinstance(data, Image.Image):
        return data.convert("RGB") if data.mode != "RGB" else data
    if isinstance(data, (list, tuple)) and data:
        for p in data:
            if isinstance(p, str) and os.path.isfile(p):
                try:
                    return load_image(p)
                except Exception:
                    continue
    return None


# ---------------------------------------------------------------- transformări

def clamp_side(v: int) -> int:
    return max(MIN_SIDE, min(MAX_SIDE, int(v)))


def resize_image(img: Image.Image, width: int, height: int, keep_ratio: bool = True,
                 reference: str = "width") -> Image.Image:
    """Redimensionează. Dacă keep_ratio, calcul cealaltă dimensiune automat."""
    w, h = img.size
    width = clamp_side(width)
    height = clamp_side(height)
    if keep_ratio:
        if reference == "width":
            height = max(1, round(width * h / w))
        else:
            width = max(1, round(height * w / h))
    return img.resize((width, height), Image.LANCZOS)


def rotate_image(img: Image.Image, degrees: float, expand: bool = True) -> Image.Image:
    """Rotește imaginea. degrees > 0 = sensul acelor de ceasornic."""
    if degrees in (0, 360):
        return img.copy()
    if degrees in (90, -270):
        return img.transpose(Image.ROTATE_270)      # 90° în sensul acelor
    if degrees in (-90, 270):
        return img.transpose(Image.ROTATE_90)       # 90° invers acelor
    if degrees in (180, -180):
        return img.transpose(Image.ROTATE_180)
    return img.rotate(-degrees, expand=expand, resample=Image.BICUBIC)


def flip_image(img: Image.Image, horizontal: bool = True) -> Image.Image:
    return img.transpose(Image.FLIP_LEFT_RIGHT if horizontal else Image.FLIP_TOP_BOTTOM)


def crop_image(img: Image.Image, box) -> Image.Image:
    """Decupează după (x0, y0, x1, y1) în coordonate pixel. Normalizează automat."""
    x0, y0, x1, y1 = box
    x0, x1 = sorted((int(x0), int(x1)))
    y0, y1 = sorted((int(y0), int(y1)))
    w, h = img.size
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(w, x1), min(h, y1)
    if x1 - x0 < 1 or y1 - y0 < 1:
        raise ValueError("Selecția de decupare este prea mică.")
    return img.crop((x0, y0, x1, y1))


def enhance_image(img: Image.Image, brightness: float = 1.0, contrast: float = 1.0,
                  saturation: float = 1.0, sharpness: float = 1.0) -> Image.Image:
    """Aplică ajustări luminozitate/contrast/saturație/claritate (1.0 = nemodificat)."""
    out = img
    if abs(brightness - 1.0) > 1e-3:
        out = ImageEnhance.Brightness(out).enhance(brightness)
    if abs(contrast - 1.0) > 1e-3:
        out = ImageEnhance.Contrast(out).enhance(contrast)
    if abs(saturation - 1.0) > 1e-3:
        out = ImageEnhance.Color(out).enhance(saturation)
    if abs(sharpness - 1.0) > 1e-3:
        out = ImageEnhance.Sharpness(out).enhance(sharpness)
    return out


def auto_orient(img: Image.Image) -> Image.Image:
    """Aplică orientarea EXIF (foto de telefon) și elimină metadatele de rotire."""
    return ImageOps.exif_transpose(img)


def fit_size(img_w: int, img_h: int, box_w: int, box_h: int):
    """Cele mai mari dimensiuni (w, h) care încap în box păstrând raportul."""
    if img_w <= 0 or img_h <= 0 or box_w <= 0 or box_h <= 0:
        return 1, 1
    scale = min(box_w / img_w, box_h / img_h)
    return max(1, round(img_w * scale)), max(1, round(img_h * scale))
