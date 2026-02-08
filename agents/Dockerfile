# -------------------------------------------------------------------
# Bedrock AgentCore Runtime requires linux/arm64 containers.
# This image uses uv for fast, reproducible dependency installation.
# -------------------------------------------------------------------

FROM --platform=linux/arm64 ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app

# Install dependencies first (layer caching via uv.lock)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy agent source code
COPY . .

# AgentCore Runtime expects the application on port 8080
EXPOSE 8080

# opentelemetry-instrument enables automatic CloudWatch observability
# without any code changes in the agent itself.
CMD ["uv", "run", "opentelemetry-instrument", "python", "main.py"]
