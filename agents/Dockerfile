# -------------------------------------------------------------------
# Bedrock AgentCore Runtime requires linux/arm64 containers.
# This image uses uv for fast, reproducible dependency installation.
# -------------------------------------------------------------------

FROM --platform=linux/arm64 ghcr.io/astral-sh/uv:python3.11-bookworm-slim

# A small, useful computer: Python comes from the base image; add Git and Node.
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash ca-certificates curl git nodejs npm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first (layer caching via uv.lock)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy agent source code
COPY . .

ENV WORKSPACE_DIR=/mnt/workspace \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

# AgentCore Runtime expects the application on port 8080
EXPOSE 8080

# Run exactly the dependencies installed above; AgentCore captures runtime logs.
CMD ["uv", "run", "--no-sync", "python", "main.py"]
