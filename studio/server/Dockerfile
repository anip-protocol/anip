FROM python:3.12-slim
WORKDIR /app
COPY studio/server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY studio/server/ server/
COPY tooling/ /app/tooling/
ENV PYTHONPATH=/app
EXPOSE 8100
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8100"]
