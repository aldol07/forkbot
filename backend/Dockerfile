# Forkbot API image. Works on Hugging Face Spaces (Docker SDK, port 7860), Render, Koyeb, Cloud Run.
#   docker build -t forkbot-api backend
#   docker run -p 7860:7860 --env-file .env forkbot-api
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

# Bake the embedding (~130 MB) and re-ranker (~80 MB) models into the image so cold starts download nothing.
RUN python -c "from fastembed import TextEmbedding; from fastembed.rerank.cross_encoder import TextCrossEncoder; c = '/home/user/.cache/fastembed'; TextEmbedding('BAAI/bge-small-en-v1.5', cache_dir=c); TextCrossEncoder('Xenova/ms-marco-MiniLM-L-6-v2', cache_dir=c)"

COPY --chown=user alembic.ini ./
COPY --chown=user migrations ./migrations
COPY --chown=user app ./app

EXPOSE 7860
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860} --proxy-headers --forwarded-allow-ips='*'"]
