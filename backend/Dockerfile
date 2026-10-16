# Build context: raiz del repositorio (ver docker-compose.yml -> build.context: .)
FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY backend/generate_cert.py ./generate_cert.py
COPY frontend ./frontend

RUN mkdir -p /app/data

ENV RTLLM_FRONTEND_DIR=/app/frontend
ENV RTLLM_DATABASE_URL=sqlite+aiosqlite:////app/data/redteam.db

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
