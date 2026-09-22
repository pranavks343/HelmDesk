# Build context is the repo root (see infra/docker-compose.yml) so this can generate its gRPC
# stubs from the shared ../../proto/ticket.proto at build time (pb/ is gitignored - regenerated,
# not committed, same as locally via scripts/gen_proto.sh).
FROM python:3.12-slim
WORKDIR /repo/apps/agent-worker

RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

COPY apps/agent-worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/agent-worker .
COPY proto /repo/proto

RUN mkdir -p pb && python -m grpc_tools.protoc \
    -I /repo/proto \
    --python_out=pb --grpc_python_out=pb --pyi_out=pb \
    /repo/proto/ticket.proto && \
    touch pb/__init__.py

CMD ["python", "main.py"]
