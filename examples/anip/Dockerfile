FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY anip_flight_demo/ anip_flight_demo/

RUN pip install --no-cache-dir .

# SQLite database lives here — mount as a volume for persistence
VOLUME /app/anip_flight_demo/data

EXPOSE 8000

CMD ["uvicorn", "anip_flight_demo.main:app", "--host", "0.0.0.0", "--port", "8000"]
