#!/usr/bin/env bash
#
# Set up Engram once (the script intentionally never installs it):
#   npm i -g @sentropic/engram
#   engram install --platform codex
#
# Build the first graph from Codex with: $engram . --all
# Update after changing data/research.csv with: $engram . --all --update
# Then run this script to validate, export the reviewed Studio bundle, and
# regenerate the deterministic Research Map summary.

set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repository_root"

if ! command -v engram >/dev/null 2>&1; then
  printf '%s\n' "Engram is not installed. Install it locally with: npm i -g @sentropic/engram" >&2
  printf '%s\n' "Then register the Codex integration with: engram install --platform codex" >&2
  exit 1
fi

engram profile validate --config engram.yaml

if [[ ! -f .engram/graph.json ]]; then
  printf '%s\n' "No graph exists at .engram/graph.json." >&2
  printf '%s\n' 'From Codex, run: $engram . --all' >&2
  printf '%s\n' "After reviewing the local graph and Studio, rerun this script." >&2
  exit 1
fi

engram studio export research-graph --state .engram --profile engram/ontology-profile.yaml
python3 scripts/generate_research_summary.py \
  --graph .engram/graph.json \
  --output research-summary.md

printf '%s\n' "Updated research-graph/ and research-summary.md. Review both, then commit them with .engram/graph.json."
