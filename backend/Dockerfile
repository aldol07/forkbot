# BotForge API image. Works on Hugging Face Spaces (Docker SDK, port 7860), Render, Koyeb, Cloud Run.
#   docker build -t botforge-api backend
#   docker run -p 7860:7860 --env-file .env botforge-api
FROM python:3.11-slim

# HF Spaces runs containers as uid 1000; a matching user keeps the cache dir writable everywhere.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    EMBEDDING_CACHE_DIR=/home/user/.cache/fastembed

WORKDIR /home/user/app
COPY --chown=user requirements.txt .
RUN pip install --user -r requirements.txt

# Bake the embedding model into the image so cold starts don't re-download ~130 MB.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5', cache_dir='/home/user/.cache/fastembed')"

COPY --chown=user app ./app

EXPOSE 7860
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860} --proxy-headers --forwarded-allow-ips='*'"]
