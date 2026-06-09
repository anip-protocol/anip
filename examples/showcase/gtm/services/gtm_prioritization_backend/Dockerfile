from python:3.12-slim

workdir /workspace

copy examples/showcase/gtm/services/gtm_prioritization_backend /workspace/examples/showcase/gtm/services/gtm_prioritization_backend

run pip install --no-cache-dir fastapi uvicorn

workdir /workspace/examples/showcase/gtm/services/gtm_prioritization_backend

cmd ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "9400"]
