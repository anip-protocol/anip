FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY anip_graphql_adapter/ anip_graphql_adapter/
RUN pip install --no-cache-dir .
EXPOSE 3002
CMD ["anip-graphql-adapter"]
