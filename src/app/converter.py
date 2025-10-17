import io, os
from pathlib import Path
from typing import Tuple, Optional, List
import fitz  # PyMuPDF
from PIL import Image
from ebooklib import epub

from .image_ops import (
    to_grayscale, resize_fit, is_double_page, split_double_page, autocrop_dark_borders
)

class ConvertError(Exception):
    pass

def _img_to_jpeg_bytes(img: Image.Image, quality: int = 80) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()

def _make_css() -> bytes:
    css = """
    html, body { margin:0; padding:0; height:100%; background:#000; }
    img.page { width:100%; height:100%; object-fit:contain; display:block; }
    """
    return css.encode("utf-8")

def pdf_to_epub(
    pdf_path: str,
    out_path: str,
    title: str = "My Manga",
    author: Optional[str] = None,
    target_resolution: Tuple[int, int] = (1264, 1680),
    jpeg_quality: int = 80,
    dpi: int = 300,
    right_to_left: bool = True,
    enable_autocrop: bool = True,
    enable_double_page_split: bool = True,
) -> str:
    """
    Converte PDF -> EPUB fixo de imagens (mangá).
    - Renderização página a página (baixo uso de RAM)
    - Grayscale 8-bit, autocrop leve, resize para o dispositivo alvo
    - Split automático de páginas duplas (opcional)
    - EPUB 3 com layout pre-paginated e RTL
    """
    doc = fitz.open(pdf_path)

    book = epub.EpubBook()
    book.set_identifier(Path(out_path).stem)
    book.set_title(title)
    if author:
        book.add_author(author)

    # Metadados EPUB 3 para layout fixo
    ns = 'http://www.idpf.org/2007/opf'
    book.add_metadata(ns, 'meta', '', {'property': 'rendition:layout', 'content': 'pre-paginated'})
    book.add_metadata(ns, 'meta', '', {'property': 'rendition:orientation', 'content': 'portrait'})
    book.add_metadata(ns, 'meta', '', {'property': 'rendition:spread', 'content': 'auto'})

    if right_to_left:
        book.spine_direction = 'rtl'

    # CSS
    style_item = epub.EpubItem(uid="style", file_name="style/nav.css", media_type="text/css", content=_make_css())
    book.add_item(style_item)

    chapters = []
    images_added = 0
    cover_set = False

    # Processa páginas
    for i in range(len(doc)):
        page = doc[i]
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img = to_grayscale(img)

        # Autocrop
        if enable_autocrop:
            img = autocrop_dark_borders(img, pad=2)

        # Split se página dupla
        imgs: List[Image.Image] = []
        if enable_double_page_split and is_double_page(img):
            imgs = split_double_page(img, rtl=right_to_left)
        else:
            imgs = [img]

        for k, im in enumerate(imgs):
            # Resize para o perfil de dispositivo
            im = resize_fit(im, target_resolution)

            jpeg_bytes = _img_to_jpeg_bytes(im, quality=jpeg_quality)
            images_added += 1
            img_id = f"img_{images_added:05d}.jpg"
            img_item = epub.EpubItem(
                uid=img_id,
                file_name=f"images/{img_id}",
                media_type="image/jpeg",
                content=jpeg_bytes,
            )
            book.add_item(img_item)

            # Capa = primeira imagem
            if not cover_set:
                book.set_cover("cover.jpg", jpeg_bytes)
                cover_set = True

            # Página XHTML
            html = f"""<?xml version="1.0" encoding="utf-8"?>
            <html xmlns="http://www.w3.org/1999/xhtml" dir="rtl" lang="ja">
              <head>
                <meta charset="utf-8"/>
                <title>Page {images_added}</title>
                <link rel="stylesheet" type="text/css" href="../style/nav.css"/>
              </head>
              <body>
                <img class="page" src="../images/{img_id}" alt="Page {images_added}"/>
              </body>
            </html>
            """
            chap = epub.EpubItem(
                uid=f"page_{images_added:05d}",
                file_name=f"text/page_{images_added:05d}.xhtml",
                media_type="application/xhtml+xml",
                content=html.encode("utf-8"),
            )
            book.add_item(chap)
            chapters.append(chap)

    # TOC + Spine
    book.toc = tuple(chapters)
    book.spine = ["nav"] + chapters
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Grava
    epub.write_epub(out_path, book, {})
    doc.close()
    return out_path
