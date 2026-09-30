"""Focused unit tests for the local research-map builder."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "build_research_map.py"
SPEC = importlib.util.spec_from_file_location("build_research_map", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
builder = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = builder
SPEC.loader.exec_module(builder)


class ResearchMapBuilderTests(unittest.TestCase):
    def test_read_papers_requires_exact_public_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "bad.csv"
            path.write_text("title,url\nPaper,https://example.org\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "exactly"):
                builder.read_papers(path)

    def test_similarity_edges_are_unique_and_bounded(self) -> None:
        embeddings = np.array([[1, 0], [0.99, 0.01], [0, 1]], dtype=np.float32)
        edges = builder.similarity_edges(embeddings, top_k=1, threshold=0.8, max_degree=1)
        self.assertEqual(edges, [(0, 1, edges[0][2])])
        self.assertGreater(edges[0][2], 0.9)

    def test_topic_label_uses_bertopic_terms(self) -> None:
        self.assertEqual(builder.topic_label(4, [("trust", 0.9), ("calibration", 0.8)]), "trust, calibration")
        self.assertEqual(builder.topic_label(-1, []), "Unclustered papers")
