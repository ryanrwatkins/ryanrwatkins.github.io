"""Tests for the deterministic Research Map summary generator."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "generate_research_summary.py"
SPEC = importlib.util.spec_from_file_location("generate_research_summary", SCRIPT_PATH)
assert SPEC is not None
assert SPEC.loader is not None
summary = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(summary)


class GenerateResearchSummaryTests(unittest.TestCase):
    def test_build_summary_ranks_typed_nodes_by_connection_count(self) -> None:
        graph = {
            "nodes": [
                {
                    "id": "paper-1",
                    "label": "First paper",
                    "node_type": "Paper",
                    "url": "https://example.com/1",
                    "year": 2025,
                },
                {
                    "id": "paper-2",
                    "label": "Second paper",
                    "node_type": "Paper",
                    "date_added": "2026-03-05",
                },
                {"id": "concept-a", "label": "Trust", "node_type": "Concept"},
                {"id": "concept-b", "label": "Governance", "node_type": "Concept"},
                {"id": "method-a", "label": "Case study", "node_type": "Method"},
                {"id": "technology-a", "label": "LLM", "node_type": "Technology"},
                {"id": "domain-a", "label": "Higher education", "node_type": "Domain"},
            ],
            "edges": [
                {"source": "paper-1", "target": "concept-a"},
                {"source": "paper-2", "target": "concept-a"},
                {"source": "paper-1", "target": "concept-b"},
                {"source": "paper-1", "target": "method-a"},
                {"source": "paper-1", "target": "technology-a"},
                {"source": "paper-1", "target": "domain-a"},
            ],
        }

        result = summary.build_summary(graph, limit=5)

        self.assertIn("- Trust (2 connections)", result)
        self.assertIn("- Governance (1 connection)", result)
        self.assertIn("- [Second paper](#) (2026-03-05)", result)
        self.assertIn("- [First paper](https://example.com/1) (2025)", result)

    def test_build_summary_supports_graphology_serialized_nodes_and_edges(self) -> None:
        graph = {
            "nodes": [
                {
                    "key": "paper-1",
                    "attributes": {
                        "label": "A paper",
                        "type": "Paper",
                        "year": "2024",
                    },
                },
                {
                    "key": "concept-1",
                    "attributes": {"label": "AI ethics", "type": "Concept"},
                },
            ],
            "edges": [{"source": "paper-1", "target": "concept-1"}],
        }

        result = summary.build_summary(graph, limit=5)

        self.assertIn("- AI ethics (1 connection)", result)
        self.assertIn("- [A paper](#) (2024)", result)

    def test_build_summary_handles_an_empty_graph(self) -> None:
        result = summary.build_summary({"nodes": [], "edges": []}, limit=5)

        self.assertIn("No typed nodes are available yet.", result)
