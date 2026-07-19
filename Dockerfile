# RepoIntel in a container. Build:  docker build -t repointel .
#
# One-off:   docker run --rm -v /path/to/repo:/repo repointel build /repo
# As an MCP server (note -i for stdio):
#   docker run --rm -i -v /path/to/repo:/repo repointel serve /repo
FROM python:3.12-slim

# git is needed for the knowledge layer's history (commits, contributors).
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv

WORKDIR /app
COPY . /app
RUN uv sync --frozen

# `serve`/`build`/etc. are appended as arguments to this entrypoint.
ENTRYPOINT ["uv", "run", "repointel"]
