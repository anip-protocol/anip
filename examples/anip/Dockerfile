FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY anip_server/ anip_server/

RUN pip install --no-cache-dir .

# SQLite database lives here — mount as a volume for persistence
VOLUME /app/anip_server/data

EXPOSE 8000

CMD ["uvicorn", "anip_server.main:app", "--host", "0.0.0.0", "--port", "8000"]
