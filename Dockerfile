FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /srv/universal-agentic-ai
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/app backend/app
COPY backend/static backend/static
RUN mkdir -p backend/data/outputs
EXPOSE 8100
# Set OPENAI_API_KEY (optional — local fallback works without it),
# UAA_REQUIRE_AUTH=1 for enforced logins, UAA_MODEL to pick the routed model.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100", "--app-dir", "backend"]
