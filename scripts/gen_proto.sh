#!/usr/bin/env bash
# Regenerates apps/agent-worker/pb/ (gitignored) from proto/ticket.proto. Run this after any
# change to the .proto file, before running agent-worker locally or its tests. `notifier` needs
# no codegen step - it loads the .proto dynamically at runtime via @grpc/proto-loader.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -x apps/agent-worker/.venv/bin/python ]; then
  echo "apps/agent-worker/.venv not found - create it first:" >&2
  echo "  cd apps/agent-worker && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

rm -rf apps/agent-worker/pb
mkdir -p apps/agent-worker/pb
apps/agent-worker/.venv/bin/python -m grpc_tools.protoc \
  -I proto \
  --python_out=apps/agent-worker/pb \
  --grpc_python_out=apps/agent-worker/pb \
  --pyi_out=apps/agent-worker/pb \
  proto/ticket.proto
touch apps/agent-worker/pb/__init__.py

echo "generated apps/agent-worker/pb/ from proto/ticket.proto"
