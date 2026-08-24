FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY config /config
ENV APP_CONFIG_PATH=/config/app.yaml
ENV DATABASE_URL=sqlite:////data/impossible_pov.db
RUN mkdir -p /data
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
