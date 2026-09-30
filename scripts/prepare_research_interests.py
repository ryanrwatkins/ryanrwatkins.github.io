#!/usr/bin/env python3
"""Create the public research-interest CSV from a local reading-list export."""

from __future__ import annotations

import argparse
import csv
import logging
from collections.abc import Iterable, Mapping
from pathlib import Path


LOGGER = logging.getLogger(__name__)
OUTPUT_FIELDS = ("title", "abstract", "url")
ACCOUNT_URL_PREFIXES = ("https://accounts.google.com/", "https://myaccount.google.com/")


def value(row: Mapping[str, str], *names: str) -> str:
    """Return the first non-empty value among source-column aliases."""
    for name in names:
        candidate = row.get(name, "").strip()
        if candidate:
            return candidate
    return ""


def prepare_rows(rows: Iterable[Mapping[str, str]]) -> tuple[list[dict[str, str]], list[tuple[str, str]]]:
    """Return public research records and a deterministic exclusion report."""
    output: list[dict[str, str]] = []
    excluded: list[tuple[str, str]] = []
    seen_urls: set[str] = set()

    for index, row in enumerate(rows, start=1):
        record_id = value(row, "ID", "id") or f"row-{index}"
        title = value(row, "Title", "title")
        abstract = value(row, "Abstract Note", "abstract", "Abstract")
        url = value(row, "Url", "url", "URL")

        if url.startswith(ACCOUNT_URL_PREFIXES):
            excluded.append((record_id, "account-security URL"))
        elif not title or not abstract or not url:
            excluded.append((record_id, "missing required value"))
        elif url in seen_urls:
            excluded.append((record_id, "duplicate URL"))
        else:
            output.append({"title": title, "abstract": abstract, "url": url})
            seen_urls.add(url)

    return output, excluded


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Original reading-list CSV")
    parser.add_argument("--output", type=Path, required=True, help="Public research-only CSV")
    parser.add_argument("--report", type=Path, required=True, help="Exclusion report path")
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()
    try:
        with args.input.open(encoding="utf-8", newline="") as input_file:
            rows = list(csv.DictReader(input_file))
    except FileNotFoundError:
        LOGGER.error("Input CSV not found: %s", args.input)
        return 1

    output, excluded = prepare_rows(rows)
    if not output:
        LOGGER.error("No research records remained after filtering %s", args.input)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(output)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        "\n".join(f"{record_id}\t{reason}" for record_id, reason in excluded) + "\n",
        encoding="utf-8",
    )
    LOGGER.info("Wrote %d research records to %s", len(output), args.output)
    LOGGER.info("Excluded %d records; report: %s", len(excluded), args.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
