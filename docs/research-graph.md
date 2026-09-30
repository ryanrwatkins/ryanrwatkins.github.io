# Research Map workflow

The public Research Map is built locally and deployed as static site content. The workflow is intentionally separate from GitHub Actions:

```text
data/research.csv
  -> Engram semantic build
  -> .engram/graph.json + local Studio
  -> scripts/update-research-graph.sh
  -> research-graph/ + research-summary.md
  -> Quarto render
  -> GitHub Pages
```

## Source data

`data/research.csv` is the authoritative public input. Every record requires a persistent `id`, `title`, `abstract`, and `url`; the additional fields support future bibliography and provenance workflows. Keep the file limited to material suitable for publication. `data/research.example.csv` documents the schema but is not an input.

The graph profile is in `engram/ontology-profile.yaml`. It is deliberately small: `Paper`, `Concept`, `Method`, `Technology`, `Domain`, and `Author`. Its relation types express only paper-to-theme connections and broad, typed relatedness. Revise the profile when the data demands it rather than adding speculative categories.

## One-time setup

Engram requires Node.js 20+ and a configured supported assistant. Install and register it locally; do not add these commands to GitHub Actions:

```bash
npm i -g @sentropic/engram
engram install --platform codex
```

## Regular update

1. Review and update `data/research.csv`.
2. In Codex, run `$engram . --all` for the first build, or `$engram . --all --update` for later changes. `--all` includes the current uncommitted CSV rather than only the repository's committed files.
3. Inspect `.engram/graph.json` and `.engram/studio/` locally. The semantic build may use the model configured for the assistant, so treat it as a review step, not an automatic publication step.
4. Run `./scripts/update-research-graph.sh`. It validates the profile, exports the static Engram Studio into `research-graph/`, and writes the deterministic `research-summary.md` from `.engram/graph.json`.
5. Review the resulting source and output, then commit `data/research.csv`, `.engram/graph.json`, `research-graph/`, and `research-summary.md`.
6. Push normally. The existing Quarto GitHub Pages workflow renders and deploys the committed artifacts only; it does not install or invoke Engram.

The summary script counts incident graph edges for the most connected typed nodes and lists `Paper` nodes by `date_added`, then `date`, then `year`. It uses no model calls and writes no narrative prose.

## Tracked and ignored artifacts

Track `data/research.csv`, `engram.yaml`, the ontology profile, `.engram/graph.json`, the exported `research-graph/` bundle, and `research-summary.md`. The `.gitignore` excludes Engram cache, converted-source workspace, local review state, local Studio source, transcripts, and generated wiki pages because they are either private, large, or recreated from the tracked graph.

`research.qmd` embeds `research-graph/index.html` with a relative path. This works in both a local Quarto render and the GitHub Pages project site without assuming deployment at the domain root.

## Later phases

Do not automate these until the source data and ontology are stable: Zotero synchronization, richer paper metadata, AI-generated narrative interpretation, scheduled refreshes, or any cloud-hosted graph service.
