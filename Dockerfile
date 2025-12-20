# Python base
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Build deps for lxml/carddav/caldav
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libxml2-dev libxslt1-dev libffi-dev libssl-dev \
  && rm -rf /var/lib/apt/lists/*

# Install Python deps first for better layer caching
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy app code
COPY fastapi4nx.py ./fastapi4nx.py
COPY src ./src
COPY static ./static
COPY .env.example ./.env.example
# Don’t bake real secrets; pass your own .env at runtime.

EXPOSE 1265
CMD ["uvicorn", "fastapi4nx:app", "--host", "0.0.0.0", "--port", "1265"]
