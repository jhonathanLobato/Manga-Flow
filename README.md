# Manga PDF → Kindle EPUB (RTL, leve)

Conversor web público: PDF (mangá escaneado) → EPUB fixo compatível com Kindle.
- Grayscale 8-bit, resize por perfil, JPEG q=80 (configurável)
- Autocrop leve de bordas escuras
- Split automático de páginas duplas
- EPUB com `pre-paginated`, `dir=rtl`, TOC por página
- Rate limiting por IP, sem persistência de arquivos

## Rodando

```bash
cp .env.example .env
docker compose up --build
