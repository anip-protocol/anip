FROM python:3.12-slim

WORKDIR /repo

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/repo/examples/showcase/gtm/generated/language-parity/python/src

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY packages/python /repo/packages/python
COPY examples/showcase/gtm/generated/language-parity/python /repo/examples/showcase/gtm/generated/language-parity/python

RUN pip install --no-cache-dir \
    -e /repo/packages/python/anip-core \
    -e /repo/packages/python/anip-crypto \
    -e /repo/packages/python/anip-server \
    -e /repo/packages/python/anip-service \
    -e /repo/packages/python/anip-fastapi

RUN pip install --no-cache-dir \
    -e /repo/examples/showcase/gtm/generated/language-parity/python \
    --no-deps

RUN pip install --no-cache-dir "psycopg[binary]>=3.2.0" "uvicorn>=0.30.0"

WORKDIR /repo/examples/showcase/gtm/generated/language-parity/python

EXPOSE 4100

CMD ["uvicorn", "gtm_operator_contract_20260512235040.app:app", "--host", "0.0.0.0", "--port", "4100"]
