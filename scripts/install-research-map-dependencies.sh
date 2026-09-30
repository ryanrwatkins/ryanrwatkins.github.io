#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3.12}"
"${PYTHON_BIN}" -m venv .venv

# BERTopic's optional sentence-transformer/UMAP stack is unnecessary because
# this project supplies Ollama embeddings and uses the explicit PCA reducer.
.venv/bin/pip install --no-deps "bertopic>=0.17,<0.18"
.venv/bin/pip install hdbscan networkx numpy pandas plotly pyyaml requests scikit-learn tqdm
npm install
