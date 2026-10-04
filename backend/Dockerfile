# Forkbot API image, for Docker-based hosts (Render's native Python runtime doesn't need it; see render.yaml).
#   docker build -t forkbot-api backend
#   docker run -p 8000:8000 --env-file .env forkbot-api
FROM python:3.11-slim

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /home/user/app
COPY --chown=user requirements.txt .
RUN pip install --user -r requirements.txt

# If the local models are switched back on (services/embeddings.py, services/rerank.py), bake them in so
# cold starts download nothing:
# ENV EMBEDDING_CACHE_DIR=/home/user/.cache/fastembed
# RUN python -c "from fastembed import TextEmbedding; from fastembed.rerank.cross_encoder import TextCrossEncoder; c = '/home/user/.cache/fastembed'; TextEmbedding('BAAI/bge-small-en-v1.5', cache_dir=c); TextCrossEncoder('Xenova/ms-marco-MiniLM-L-6-v2', cache_dir=c)"

COPY --chown=user alembic.ini ./
COPY --chown=user migrations ./migrations
COPY --chown=user app ./app

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
