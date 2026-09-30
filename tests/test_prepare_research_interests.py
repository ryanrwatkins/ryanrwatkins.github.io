"""Tests for the public research-interest CSV preparation script."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "prepare_research_interests.py"
SPEC = importlib.util.spec_from_file_location("prepare_research_interests", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
prepare = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prepare)


class PrepareResearchInterestTests(unittest.TestCase):
    def test_prepare_rows_keeps_research_records_and_rewrites_three_columns(self) -> None:
        output, excluded = prepare.prepare_rows([
            {"ID": "r001", "Title": "Security alert", "Abstract Note": "Personal", "Url": "https://accounts.google.com/AccountChooser"},
            {"ID": "r002", "Title": "Research title", "Abstract Note": "Research abstract.", "Url": "https://example.org/paper"},
        ])
        self.assertEqual(output, [{"title": "Research title", "abstract": "Research abstract.", "url": "https://example.org/paper"}])
        self.assertEqual(excluded, [("r001", "account-security URL")])

    def test_prepare_rows_keeps_first_duplicate_url(self) -> None:
        output, excluded = prepare.prepare_rows([
            {"ID": "r004", "Title": "First", "Abstract Note": "One", "Url": "https://example.org/paper"},
            {"ID": "r005", "Title": "Second", "Abstract Note": "Two", "Url": "https://example.org/paper"},
        ])
        self.assertEqual(output[0]["title"], "First")
        self.assertEqual(excluded, [("r005", "duplicate URL")])
