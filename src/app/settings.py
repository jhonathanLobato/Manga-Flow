import os

def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")

class Settings:
    RATE_LIMIT = os.getenv("RATE_LIMIT", "6/minute")
    MAX_PDF_MB = int(os.getenv("MAX_PDF_MB", "200"))
    MAX_PAGES = int(os.getenv("MAX_PAGES", "1000"))
    CONVERT_TIMEOUT_SEC = int(os.getenv("CONVERT_TIMEOUT_SEC", "240"))
    DEFAULT_WIDTH = int(os.getenv("DEFAULT_WIDTH", "1264"))
    DEFAULT_HEIGHT = int(os.getenv("DEFAULT_HEIGHT", "1680"))
    DEFAULT_JPEG_QUALITY = int(os.getenv("DEFAULT_JPEG_QUALITY", "80"))
    DEFAULT_RTL = _env_bool("DEFAULT_RTL", True)
    RENDER_DPI = int(os.getenv("RENDER_DPI", "300"))
    CORS_ALLOW_ORIGINS = [o.strip() for o in os.getenv("CORS_ALLOW_ORIGINS", "*").split(",") if o.strip()]
    REDIS_URL = os.getenv("REDIS_URL", None)

settings = Settings()
