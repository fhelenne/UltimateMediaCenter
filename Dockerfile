# Stage 1 — install dependencies
FROM python:3.11-alpine AS builder
WORKDIR /build
COPY pyproject.toml .
# Stub app package so pip install . resolves the project metadata
RUN mkdir app && touch app/__init__.py
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Stage 2 — runtime image
FROM python:3.11-alpine
RUN adduser -D app
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages \
                    /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY app/ app/
RUN mkdir -p /app/data && chown -R app:app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
    CMD wget -qO- http://127.0.0.1:8000/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
