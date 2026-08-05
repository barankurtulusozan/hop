# Multi-stage production build for HOP Enterprise AI Platform Core
FROM python:3.13-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.13-slim as runtime

WORKDIR /app

COPY --from=builder /install /usr/local
COPY src/ src/

ENV PYTHONUNBUFFERED=1
ENV PORT=8000

EXPOSE 8000

USER 10001

ENTRYPOINT ["python", "-m", "src.cli.main"]
CMD ["serve", "--port", "8000"]
