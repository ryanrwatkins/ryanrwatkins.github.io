#!/usr/bin/env python3
"""Build a static research-interest graph using local Ollama embeddings only."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np
import requests
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import normalize
from sklearn.decomposition import PCA
from sklearn.feature_extraction.text import CountVectorizer


LOGGER = logging.getLogger(__name__)
REQUIRED_FIELDS = {"title", "abstract", "url"}
DEFAULT_ENDPOINT = "http://127.0.0.1:11435"
DEFAULT_MODEL = "qwen3-embedding:latest"


@dataclass(frozen=True)
class Paper:
    """A validated research-interest record."""

    title: str
    abstract: str
    url: str

    @property
    def semantic_text(self) -> str:
        return f"{self.title}\n\n{self.abstract}"

    @property
    def text_hash(self) -> str:
        return hashlib.sha256(self.semantic_text.encode("utf-8")).hexdigest()


def read_papers(path: Path) -> list[Paper]:
    """Load a clean three-column research CSV, rejecting malformed records."""
    with path.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        fields = set(reader.fieldnames or [])
        if fields != REQUIRED_FIELDS:
            raise ValueError(f"{path} must contain exactly {sorted(REQUIRED_FIELDS)}; found {sorted(fields)}")

        papers: list[Paper] = []
        seen_urls: set[str] = set()
        for row_number, row in enumerate(reader, start=2):
            paper = Paper(*(row[field].strip() for field in ("title", "abstract", "url")))
            if not all((paper.title, paper.abstract, paper.url)):
                raise ValueError(f"{path}:{row_number} has an empty title, abstract, or url")
            if paper.url in seen_urls:
                raise ValueError(f"{path}:{row_number} repeats URL {paper.url}")
            papers.append(paper)
            seen_urls.add(paper.url)
    if not papers:
        raise ValueError(f"{path} contains no papers")
    return papers


def available_models(endpoint: str) -> set[str]:
    """Return local Ollama model names or raise a useful endpoint error."""
    try:
        response = requests.get(f"{endpoint.rstrip('/')}/api/tags", timeout=20)
        response.raise_for_status()
    except requests.RequestException as error:
        raise RuntimeError(f"Ollama endpoint is not reachable at {endpoint}: {error}") from error
    return {model["name"] for model in response.json().get("models", []) if "name" in model}


def require_model(endpoint: str, model: str) -> None:
    """Confirm the requested local embedding model is already installed."""
    models = available_models(endpoint)
    short_name = model.removesuffix(":latest")
    if model not in models and short_name not in {name.removesuffix(":latest") for name in models}:
        raise RuntimeError(f"Model {model!r} is unavailable at {endpoint}; installed models: {sorted(models)}")


def load_embedding_cache(path: Path) -> dict[str, tuple[str, np.ndarray]]:
    """Load cached vectors keyed by stable paper URL."""
    if not path.exists():
        return {}
    with np.load(path, allow_pickle=False) as cache:
        return {
            str(url): (str(text_hash), vector)
            for url, text_hash, vector in zip(cache["urls"], cache["hashes"], cache["embeddings"], strict=True)
        }


def save_embedding_cache(path: Path, papers: list[Paper], embeddings: np.ndarray) -> None:
    """Atomically save the local-only cache for unchanged future builds."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".npz", delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        np.savez_compressed(
            temporary_path,
            urls=np.array([paper.url for paper in papers]),
            hashes=np.array([paper.text_hash for paper in papers]),
            embeddings=embeddings,
        )
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def embed_batch(endpoint: str, model: str, texts: list[str]) -> np.ndarray:
    """Embed a modest batch through the local Ollama API."""
    try:
        response = requests.post(
            f"{endpoint.rstrip('/')}/api/embed",
            json={"model": model, "input": texts},
            timeout=180,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        raise RuntimeError(f"Ollama embedding request failed: {error}") from error
    vectors = np.asarray(response.json().get("embeddings", []), dtype=np.float32)
    if vectors.ndim != 2 or len(vectors) != len(texts):
        raise RuntimeError("Ollama returned an unexpected embedding response")
    return vectors


def embed_papers(
    papers: list[Paper], endpoint: str, model: str, cache_path: Path, batch_size: int
) -> np.ndarray:
    """Reuse unchanged cached embeddings and batch only the remainder."""
    cache = load_embedding_cache(cache_path)
    vectors: list[np.ndarray | None] = [None] * len(papers)
    pending: list[tuple[int, Paper]] = []
    for index, paper in enumerate(papers):
        cached = cache.get(paper.url)
        if cached and cached[0] == paper.text_hash:
            vectors[index] = cached[1]
        else:
            pending.append((index, paper))

    LOGGER.info("Reusing %d cached embeddings; requesting %d", len(papers) - len(pending), len(pending))
    for start in range(0, len(pending), batch_size):
        batch = pending[start : start + batch_size]
        embedded = embed_batch(endpoint, model, [paper.semantic_text for _, paper in batch])
        for (index, _), vector in zip(batch, embedded, strict=True):
            vectors[index] = vector
        completed = min(start + batch_size, len(pending))
        if completed == len(pending) or completed % 60 == 0:
            LOGGER.info("Embedded %d/%d changed papers", completed, len(pending))

    if any(vector is None for vector in vectors):
        raise RuntimeError("Embedding cache did not produce a vector for every paper")
    embeddings = np.vstack([vector for vector in vectors if vector is not None])
    save_embedding_cache(cache_path, papers, embeddings)
    return embeddings


def discover_topics(texts: list[str], embeddings: np.ndarray, min_topic_size: int, min_samples: int) -> tuple[list[int], dict[int, list[tuple[str, float]]], dict[int, float]]:
    """Run BERTopic over precomputed local embeddings without another model provider."""
    from bertopic import BERTopic
    from hdbscan import HDBSCAN
    # PCA avoids a local Numba/UMAP binary dependency while keeping BERTopic's
    # standard reducer-plus-HDBSCAN clustering flow deterministic.
    reducer = PCA(n_components=5, random_state=42)
    cluster_model = HDBSCAN(
        min_cluster_size=min_topic_size,
        min_samples=min_samples,
        metric="euclidean",
        prediction_data=True,
    )
    vectorizer = CountVectorizer(stop_words="english", ngram_range=(1, 2), min_df=2)
    topic_model = BERTopic(
        embedding_model=None,
        umap_model=reducer,
        hdbscan_model=cluster_model,
        calculate_probabilities=True,
        top_n_words=6,
        vectorizer_model=vectorizer,
        verbose=True,
    )
    topics, probabilities = topic_model.fit_transform(texts, embeddings)
    representations = {
        topic_id: [(str(term), float(weight)) for term, weight in topic_model.get_topic(topic_id) or []]
        for topic_id in set(topics)
    }
    confidence: dict[int, float] = {}
    if probabilities is not None:
        for index, topic_id in enumerate(topics):
            value = probabilities[index]
            confidence[index] = float(value.max()) if isinstance(value, np.ndarray) else float(value)
    return list(map(int, topics)), representations, confidence


def topic_label(topic_id: int, terms: list[tuple[str, float]]) -> str:
    """Give each BERTopic cluster an inspectable deterministic label."""
    if topic_id == -1:
        return "Unclustered papers"
    keywords = ", ".join(term for term, _ in terms[:5])
    return keywords or f"Topic {topic_id}"


def similarity_edges(
    embeddings: np.ndarray, top_k: int, threshold: float, max_degree: int
) -> list[tuple[int, int, float]]:
    """Return unique, thresholded nearest-neighbor edges for an undirected graph."""
    similarities = cosine_similarity(normalize(embeddings))
    candidates: dict[tuple[int, int], float] = {}
    for source, row in enumerate(similarities):
        neighbors = np.argsort(row)[::-1]
        kept = 0
        for target in neighbors:
            if source == target or row[target] < threshold:
                continue
            pair = tuple(sorted((source, int(target))))
            candidates[pair] = max(candidates.get(pair, 0.0), float(row[target]))
            kept += 1
            if kept == top_k:
                break
    accepted: list[tuple[int, int, float]] = []
    degrees: dict[int, int] = {}
    for (source, target), score in sorted(candidates.items(), key=lambda item: -item[1]):
        if degrees.get(source, 0) >= max_degree or degrees.get(target, 0) >= max_degree:
            continue
        accepted.append((source, target, score))
        degrees[source] = degrees.get(source, 0) + 1
        degrees[target] = degrees.get(target, 0) + 1
    return sorted(accepted)


def build_graph(
    papers: list[Paper],
    embeddings: np.ndarray,
    topics: list[int],
    representations: dict[int, list[tuple[str, float]]],
    confidence: dict[int, float],
    top_k: int,
    threshold: float,
    max_degree: int,
    model: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Create static graph and summary structures consumed by the browser."""
    paper_edges = similarity_edges(embeddings, top_k, threshold, max_degree)
    topic_ids = sorted(set(topics))
    clustered_topic_ids = [topic_id for topic_id in topic_ids if topic_id != -1]
    labels = {topic_id: topic_label(topic_id, representations.get(topic_id, [])) for topic_id in topic_ids}
    graph = nx.Graph()
    for index, paper in enumerate(papers):
        graph.add_node(paper.url, kind="Paper")
    for topic_id in clustered_topic_ids:
        graph.add_node(f"topic:{topic_id}", kind="Topic")
    for source, target, score in paper_edges:
        graph.add_edge(papers[source].url, papers[target].url, weight=score)
    for index, topic_id in enumerate(topics):
        if topic_id != -1:
            graph.add_edge(papers[index].url, f"topic:{topic_id}", weight=0.2)

    positions = nx.spring_layout(graph, seed=42, weight="weight", iterations=150)
    palette = (
        "#1d5f74",
        "#b45232",
        "#476d48",
        "#7d5e9d",
        "#a87820",
        "#267a76",
        "#a84f6d",
        "#546e91",
        "#8a6a3d",
        "#5d7956",
        "#965d91",
        "#6d6d6d",
    )
    colors = {topic_id: palette[index % len(palette)] for index, topic_id in enumerate(topic_ids)}
    nodes: list[dict[str, Any]] = []
    for index, paper in enumerate(papers):
        topic_id = topics[index]
        nodes.append(
            {
                "id": paper.url,
                "type": "Paper",
                "label": paper.title,
                "title": paper.title,
                "abstract": paper.abstract,
                "url": paper.url,
                "topic_id": topic_id,
                "topic_label": labels[topic_id],
                "topic_confidence": round(confidence.get(index, 0.0), 4),
                "degree": graph.degree(paper.url),
                "x": round(float(positions[paper.url][0]), 6),
                "y": round(float(positions[paper.url][1]), 6),
                "size": 4,
                "color": colors[topic_id],
            }
        )
    topic_summaries: list[dict[str, Any]] = []
    for topic_id in clustered_topic_ids:
        topic_node = f"topic:{topic_id}"
        member_ids = [paper.url for paper, assignment in zip(papers, topics, strict=True) if assignment == topic_id]
        terms = representations.get(topic_id, [])
        keywords = [term for term, _ in terms[:6]]
        nodes.append(
            {
                "id": topic_node,
                "type": "Topic",
                "label": labels[topic_id],
                "topic_id": topic_id,
                "keywords": keywords,
                "paper_ids": member_ids,
                "paper_count": len(member_ids),
                "x": round(float(positions[topic_node][0]), 6),
                "y": round(float(positions[topic_node][1]), 6),
                "size": 10,
                "color": colors[topic_id],
            }
        )
        topic_summaries.append({"id": topic_id, "label": labels[topic_id], "keywords": keywords, "paper_count": len(member_ids), "paper_ids": member_ids})

    edges: list[dict[str, Any]] = [
        {"id": f"similarity:{source}:{target}", "source": papers[source].url, "target": papers[target].url, "relation": "similar_to", "score": round(score, 6), "size": 1, "color": "#b8c6cf"}
        for source, target, score in paper_edges
    ]
    edges.extend(
        {"id": f"topic:{index}", "source": papers[index].url, "target": f"topic:{topic_id}", "relation": "belongs_to", "size": 0.5, "color": "#d7e0e5"}
        for index, topic_id in enumerate(topics)
        if topic_id != -1
    )
    centrality = nx.betweenness_centrality(graph, weight="weight")
    paper_nodes = [node for node in nodes if node["type"] == "Paper"]
    highest_degree = sorted(paper_nodes, key=lambda node: (-node["degree"], node["title"]))[:12]
    bridge_papers = sorted(paper_nodes, key=lambda node: (-centrality[node["id"]], node["title"]))[:12]
    summary = {
        "paper_count": len(papers),
        "topic_count": len(clustered_topic_ids),
        "unclustered_paper_count": sum(topic_id == -1 for topic_id in topics),
        "similarity_edge_count": len(paper_edges),
        "topic_membership_edge_count": sum(topic_id != -1 for topic_id in topics),
        "topics": topic_summaries,
        "highest_degree_papers": [{"title": node["title"], "url": node["url"], "degree": node["degree"], "topic_label": node["topic_label"]} for node in highest_degree],
        "bridge_papers": [{"title": node["title"], "url": node["url"], "betweenness": round(float(centrality[node["id"]]), 6), "topic_label": node["topic_label"]} for node in bridge_papers],
    }
    graph_output = {
        "schema_version": 1,
        "metadata": {"embedding_model": model, "embedding_dimension": int(embeddings.shape[1]), "similarity": {"top_k": top_k, "threshold": threshold, "max_degree": max_degree}, "layout": {"algorithm": "networkx.spring_layout", "seed": 42}},
        "nodes": nodes,
        "edges": edges,
    }
    return graph_output, summary


def write_json(path: Path, value: dict[str, Any]) -> None:
    """Write a stable, readable generated JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/research_interests.csv"))
    parser.add_argument("--graph-output", type=Path, default=Path("research-map/research_graph.json"))
    parser.add_argument("--summary-output", type=Path, default=Path("research-map/research_summary.json"))
    parser.add_argument("--cache", type=Path, default=Path(".cache/research-map/embeddings.npz"))
    parser.add_argument("--ollama-base-url", default=os.environ.get("OLLAMA_BASE_URL", DEFAULT_ENDPOINT))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--batch-size", type=int, default=12)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--max-degree", type=int, default=8)
    parser.add_argument("--similarity-threshold", type=float, default=0.42)
    parser.add_argument("--min-topic-size", type=int, default=8)
    parser.add_argument("--min-samples", type=int, default=1)
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()
    if args.batch_size < 1 or args.top_k < 1 or args.max_degree < 1 or not -1 <= args.similarity_threshold <= 1:
        LOGGER.error("batch size, top-k, and max degree must be positive; similarity threshold must be between -1 and 1")
        return 2
    try:
        papers = read_papers(args.input)
        require_model(args.ollama_base_url, args.model)
        embeddings = embed_papers(papers, args.ollama_base_url, args.model, args.cache, args.batch_size)
        topics, representations, confidence = discover_topics([paper.semantic_text for paper in papers], embeddings, args.min_topic_size, args.min_samples)
        graph, summary = build_graph(papers, embeddings, topics, representations, confidence, args.top_k, args.similarity_threshold, args.max_degree, args.model)
        write_json(args.graph_output, graph)
        write_json(args.summary_output, summary)
    except (OSError, RuntimeError, ValueError) as error:
        LOGGER.error("Research map build failed: %s", error)
        return 1
    LOGGER.info("Built map for %d papers, %d topics, and %d similarity edges", summary["paper_count"], summary["topic_count"], summary["similarity_edge_count"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
