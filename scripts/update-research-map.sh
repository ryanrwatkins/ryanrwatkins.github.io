#!/usr/bin/env bash
set -euo pipefail

# The SSH tunnel to the GW HPC Ollama host must be running before this command.
export OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://127.0.0.1:11435}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

"${PYTHON_BIN}" scripts/build_research_map.py "$@"
npm run build:research-map-ui
quarto render
