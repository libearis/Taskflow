#!/usr/bin/env bash
# Regenerates the grpc-web JS/TS client from ../backend/proto/board_stream.proto.
#
# Requires on PATH:
#   - protoc            (https://github.com/protocolbuffers/protobuf/releases)
#   - protoc-gen-js      (https://github.com/protocolbuffers/protobuf-javascript/releases —
#                          the JS codegen was split out of core protobuf; protoc alone is not enough)
#   - protoc-gen-grpc-web (https://github.com/grpc/grpc-web/releases)
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p src/generated

protoc -I ../backend/proto \
  --js_out=import_style=commonjs,binary:src/generated \
  --grpc-web_out=import_style=typescript,mode=grpcwebtext:src/generated \
  ../backend/proto/board_stream.proto

# protoc-gen-js only emits CommonJS (require/module.exports). Vite's dev
# server serves project source files as-is — it does NOT run these through a
# CJS->ESM interop step the way it does for node_modules dependencies — so a
# raw `require(...)` call reaches the browser and throws "require is not
# defined". Rewrite the two CJS touchpoints into plain ESM instead of
# fighting Vite's transform pipeline for a file this small:
PB_FILE="src/generated/board_stream_pb.js"

sed -i "s/var jspb = require('google-protobuf');/import * as jspb from 'google-protobuf';/" "$PB_FILE"

EXPORTED_SYMBOLS=$(grep "goog.exportSymbol" "$PB_FILE" | grep -oE "proto\.taskflow\.[A-Za-z0-9_]+" | sed 's/proto\.taskflow\.//' | sort -u | paste -sd, -)
sed -i "s/goog.object.extend(exports, proto.taskflow);/export const { ${EXPORTED_SYMBOLS} } = proto.taskflow;/" "$PB_FILE"

echo "Generated grpc-web client in src/generated/"
