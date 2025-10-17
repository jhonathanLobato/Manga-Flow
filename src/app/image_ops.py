from typing import Tuple, List
from PIL import Image, ImageOps, ImageStat, ImageChops

def to_grayscale(img: Image.Image) -> Image.Image:
    return ImageOps.exif_transpose(img).convert("L")

def resize_fit(img: Image.Image, max_wh: Tuple[int, int]) -> Image.Image:
    w, h = img.size
    mw, mh = max_wh
    scale = min(mw / w, mh / h)
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    if (nw, nh) == (w, h):
        return img
    return img.resize((nw, nh), Image.LANCZOS)

def is_double_page(img: Image.Image, threshold_ratio: float = 1.3) -> bool:
    w, h = img.size
    return (w / max(h, 1)) >= threshold_ratio

def split_double_page(img: Image.Image, rtl: bool = True) -> List[Image.Image]:
    """
    Divide em duas metades verticais. Para leitura RTL (mangá),
    a ordem de leitura é: direita -> esquerda.
    """
    w, h = img.size
    mid = w // 2
    left = img.crop((0, 0, mid, h))
    right = img.crop((mid, 0, w, h))
    # ordem: direita, depois esquerda (para aparecer "certo" no Kindle em RTL)
    return [right, left] if rtl else [left, right]

def autocrop_dark_borders(img: Image.Image, pad: int = 2) -> Image.Image:
    """
    Autocrop simples focado em bordas escuras (scans).
    Funciona em escala de cinza. Mantém um padding leve.
    """
    if img.mode != "L":
        gray = img.convert("L")
    else:
        gray = img

    # Normaliza levemente para destacar conteúdo
    norm = ImageOps.autocontrast(gray, cutoff=1)

    # Cria uma máscara detectando "conteúdo" (pixels não-pretos)
    # Subtrai do fundo preto para achar bbox
    bg = Image.new("L", norm.size, 0)
    diff = ImageChops.difference(norm, bg)
    bbox = diff.getbbox()

    if not bbox:
        return img

    left, top, right, bottom = bbox
    left = max(left - pad, 0)
    top = max(top - pad, 0)
    right = min(right + pad, img.width)
    bottom = min(bottom + pad, img.height)
    return img.crop((left, top, right, bottom))
