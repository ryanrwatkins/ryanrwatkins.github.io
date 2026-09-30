# Research map maintenance

The interactive research map is a static GitHub Pages asset built locally. It uses the title and abstract of each public research record, sends them only through the local Ollama tunnel, clusters the returned vectors with BERTopic, and exports a bounded semantic-neighbor graph.

## One-time setup

Use Python 3.12 or later and Node.js 20 or later:

```bash
PYTHON_BIN=python3.12 scripts/install-research-map-dependencies.sh
```

The local embedding cache at `.cache/research-map/embeddings.npz` is intentionally ignored by Git. `research-map/research_graph.json`, `research-map/research_summary.json`, and the bundled `research-map/graph.js` are generated artifacts that are committed for GitHub Pages.

## Update flow

Open the SSH tunnel to the GW HPC Ollama host, then verify the local endpoint and model:

```bash
curl http://127.0.0.1:11435/api/tags
OLLAMA_BASE_URL=http://127.0.0.1:11435 .venv/bin/python scripts/build_research_map.py
npm run build:research-map-ui
quarto render
```

Or use the wrapper:

```bash
PYTHON_BIN=.venv/bin/python scripts/update-research-map.sh
```

The builder requires `qwen3-embedding:latest` to already be installed. It uses no hosted APIs and does not pull models. It defaults to batches of 12, BERTopic topic clusters of at least 8 papers, `min_samples=1`, five cosine-similarity neighbors per paper, a similarity threshold of `0.42`, and a hard cap of eight semantic links per paper. The cached vector is invalidated only when a paper's title or abstract changes. BERTopic receives the precomputed Ollama vectors and uses deterministic PCA plus HDBSCAN; PCA keeps the local setup portable where a Numba-compatible UMAP wheel is unavailable.

The graph layout is a fixed-seed NetworkX spring layout that is saved in JSON; the browser does not recompute it. Topic labels are deterministic BERTopic keyword lists. They are useful discovery labels rather than editorially authored research claims.
