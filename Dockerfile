FROM python:3.12-slim

# Install FFmpeg and Deno (JS runtime required by yt-dlp on cloud IPs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    unzip \
    ca-certificates \
    && curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Hugging Face Spaces requires non-root UID 1000
RUN useradd -m -u 1000 user

COPY --chown=user:user . .
RUN mkdir -p /app/downloads && chown -R user:user /app/downloads

USER user

ENV HOME=/home/user \
    PATH="/home/user/.local/bin:/usr/local/bin:${PATH}" \
    PORT=7860 \
    DEPLOY_ENV=cloud \
    AUTO_CLEANUP=true \
    MAX_DURATION_SECONDS=3600 \
    PYTHONUNBUFFERED=1

EXPOSE 7860

CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT:-7860} --workers 1 --threads 8 --timeout 300"]
