# RepoIntel in a container. Build:  docker build -t repointel .
#
# One-off:   docker run --rm -v /path/to/repo:/repo repointel build /repo
# As an MCP server (note -i for stdio):
#   docker run --rm -i -v /path/to/repo:/repo repointel serve /repo
FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY . /app
RUN uv sync --frozen

# `serve`/`build`/etc. are appended as arguments to this entrypoint.
ENTRYPOINT ["uv", "run", "repointel"]
