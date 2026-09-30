# Research data

`research.csv` is the public, authoritative input for the Research Map. It intentionally starts with headers only so every record can be reviewed before it becomes part of the public site.

Each row must have a stable `id`, `title`, `abstract`, and `url`. The remaining columns support future use and may be empty: `authors`, `year`, `venue`, `doi`, `date_added`, `notes`, `citation`, and `zotero_key`.

`research.example.csv` illustrates the expected shape only. Do not include its example row in the published input.

The existing local reading export was not copied here: it is not an authoritative research dataset, has no persistent IDs, and should be curated before any of its contents are published.
