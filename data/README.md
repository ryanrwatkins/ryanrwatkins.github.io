# Research-map data

`research_interests.csv` is the public, authoritative input for the research map. It has exactly three columns: `title`, `abstract`, and `url`; the URL is the stable paper identifier. It contains 486 unique records.

`research_interests.exclusions.tsv` records the deterministic duplicate-URL exclusions made while producing this public dataset. To refresh it from a private reading-list export, run `scripts/prepare_research_interests.py` with explicit `--input`, `--output`, and `--report` paths.
