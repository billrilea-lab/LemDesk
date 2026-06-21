#!/usr/bin/env bash
# Pull models recommended in Docker Model Runner IDE integrations docs.
set -euo pipefail

MODELS=(
  "ai/qwen3-coder"
  "ai/devstral-small-2"
  "ai/glm-4.7-flash"
  "ai/qwen2.5-coder"
  "ai/llama3.2"
  "ai/smollm2"
  "ai/all-minilm"
)

echo "Pulling recommended DMR models (this may take a while)..."
for m in "${MODELS[@]}"; do
  echo "--- docker model pull ${m} ---"
  docker model pull "${m}" || echo "WARN: failed ${m}"
done

echo "Done. List: docker model list"
