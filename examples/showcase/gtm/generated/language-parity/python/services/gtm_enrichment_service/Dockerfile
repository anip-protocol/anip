FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src
ENV PORT=4100

WORKDIR /app
COPY . /app
RUN python -m pip install --no-cache-dir --upgrade pip && python -m pip install --no-cache-dir .

EXPOSE 4100
CMD ["python", "-m", "gtm_pipeline_q2_review.services.gtm_enrichment_service.app"]
