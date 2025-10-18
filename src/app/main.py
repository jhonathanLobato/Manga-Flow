import os, tempfile, asyncio, shutil
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import fitz

from .settings import settings
from .converter import pdf_to_epub

# Rate limiter (Redis recomendado em prod)
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URL
)

app = FastAPI(title="Manga PDF → Kindle EPUB")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOW_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Estáticos (para dev; em produção o Nginx serve /)
# Monte /assets a partir da pasta real de assets
app.mount("/assets", StaticFiles(directory="src/static/assets"), name="static")

@app.exception_handler(RateLimitExceeded)
def ratelimit_handler(request: Request, exc: RateLimitExceeded):
    return PlainTextResponse("Muitas requisições: tente de novo em instantes.", status_code=429)

@app.get("/", response_class=HTMLResponse)
def index():
    # Em prod, Nginx entrega /index.html; isso é útil para dev local
    with open("src/static/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.post("/convert")
@limiter.limit(settings.RATE_LIMIT)
async def convert(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form("My Manga"),
    author: Optional[str] = Form(None),
    width: int = Form(...),
    height: int = Form(...),
    jpeg_quality: int = Form(...),
    rtl: bool = Form(...),
    autocrop: bool = Form(True),
    split_double: bool = Form(True),
):
    fname = (file.filename or "").lower()
    if not fname.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Envie um arquivo .pdf")

    # Verifica Content-Length quando disponível
    cl = request.headers.get("content-length")
    if cl and int(cl) > settings.MAX_PDF_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Arquivo acima de {settings.MAX_PDF_MB} MB.")

    # NÃO use TemporaryDirectory() aqui — ele remove antes do FileResponse ler.
    td = tempfile.mkdtemp()
    pdf_path = os.path.join(td, "input.pdf")
    out_path = os.path.join(td, "output.epub")

    try:
        # Grava em chunks
        size = 0
        with open(pdf_path, "wb") as f:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.MAX_PDF_MB * 1024 * 1024:
                    raise HTTPException(status_code=413, detail=f"Arquivo acima de {settings.MAX_PDF_MB} MB.")
                f.write(chunk)

        # Valida PDF
        try:
            doc = fitz.open(pdf_path)
        except Exception:
            raise HTTPException(status_code=400, detail="PDF inválido ou corrompido.")
        if doc.needs_pass:
            doc.close()
            raise HTTPException(status_code=400, detail="PDF protegido por senha não é suportado.")
        if len(doc) <= 0 or len(doc) > settings.MAX_PAGES:
            n = len(doc)
            doc.close()
            raise HTTPException(status_code=400, detail=f"PDF com {n} páginas. Limite: {settings.MAX_PAGES}.")
        doc.close()

        # Conversão com timeout
        try:
            await asyncio.wait_for(asyncio.to_thread(
                pdf_to_epub,
                pdf_path, out_path,
                title=title, author=author,
                target_resolution=(max(1, int(width)), max(1, int(height))),
                jpeg_quality=min(95, max(40, int(jpeg_quality))),
                dpi=settings.RENDER_DPI,
                right_to_left=bool(rtl),
                enable_autocrop=bool(autocrop),
                enable_double_page_split=bool(split_double),
            ), timeout=settings.CONVERT_TIMEOUT_SEC)
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="Conversão excedeu o tempo máximo.")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Falha na conversão: {e}")

        # Sanity-check: arquivo precisa existir e ter tamanho > 0
        if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
            raise HTTPException(status_code=500, detail="Conversão não gerou arquivo de saída.")

        headers = {"Content-Disposition": f'attachment; filename="{os.path.splitext(file.filename)[0]}.epub"'}

        # Limpeza em background (só depois que a resposta for enviada)
        def _cleanup():
            for p in (pdf_path, out_path):
                try:
                    os.remove(p)
                except FileNotFoundError:
                    pass
            try:
                shutil.rmtree(td)
            except FileNotFoundError:
                pass

        return FileResponse(
            out_path,
            media_type="application/epub+zip",
            headers=headers,
            background=BackgroundTask(_cleanup),
        )

    except Exception:
        # Se algo der errado, tente limpar
        try:
            shutil.rmtree(td)
        except FileNotFoundError:
            pass
        raise
