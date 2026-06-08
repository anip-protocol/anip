from python:3.12-slim

workdir /workspace

copy packages/python /workspace/packages/python
copy examples/showcase/gtm/services/gtm_outreach_mcp_backend /workspace/examples/showcase/gtm/services/gtm_outreach_mcp_backend

run pip install --no-cache-dir \
    fastapi \
    uvicorn \
    mcp

workdir /workspace/examples/showcase/gtm/services/gtm_outreach_mcp_backend

cmd ["python", "app.py"]
