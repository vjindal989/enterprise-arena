FROM ghcr.io/meta-pytorch/openenv-base:latest

WORKDIR /app/env

COPY pyproject.toml ./
RUN uv pip install --system -e ".[dev]" || uv sync --active

COPY . .

EXPOSE 8000
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]
