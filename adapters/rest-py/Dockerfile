FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY anip_rest_adapter/ anip_rest_adapter/
RUN pip install --no-cache-dir .
EXPOSE 3001
CMD ["anip-rest-adapter"]
