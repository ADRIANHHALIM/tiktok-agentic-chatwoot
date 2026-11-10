FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    NODE_ENV=production

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY api ./api
COPY builder ./builder
COPY signing ./signing
COPY reverse/tiktok_shop_bsid/env ./reverse/tiktok_shop_bsid/env
COPY static ./static
COPY utils ./utils
COPY demo.py ./
COPY bridge.py ./
COPY README.md ./

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "bridge:app", "--host", "0.0.0.0", "--port", "8000"]
