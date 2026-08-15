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
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages \
                    /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY app/ app/
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
