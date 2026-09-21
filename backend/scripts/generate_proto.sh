#!/usr/bin/env bash
# Regenerates Python gRPC stubs from proto/*.proto.
# Never hand-edit app/grpc_server/generated/* — always run this script.
set -euo pipefail

cd "$(dirname "$0")/.."

python -m grpc_tools.protoc \
  -I proto \
  --python_out=app/grpc_server/generated \
  --grpc_python_out=app/grpc_server/generated \
  --pyi_out=app/grpc_server/generated \
  proto/board_stream.proto proto/issue_intake.proto

# grpc_tools generates absolute-style imports (e.g. `import board_stream_pb2`);
# rewrite to package-relative imports so it works under app.grpc_server.generated.
sed -i 's/^import board_stream_pb2/from . import board_stream_pb2/' \
  app/grpc_server/generated/board_stream_pb2_grpc.py
sed -i 's/^import issue_intake_pb2/from . import issue_intake_pb2/' \
  app/grpc_server/generated/issue_intake_pb2_grpc.py

touch app/grpc_server/generated/__init__.py

echo "Generated Python stubs in app/grpc_server/generated/"
echo "Run scripts/generate_proto_web.sh (frontend) separately for the grpc-web JS/TS client."
