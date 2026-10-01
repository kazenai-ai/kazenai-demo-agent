# Vendor directory

This public demo installs dependencies from **PyPI** via `requirements.txt`.

Tracked offline wheels were removed so the standalone clone path cannot drift
behind published package versions or ship unexplained binaries.

```bash
python -m pip install -r requirements.txt
```

If you need a hermetic offline mirror for your own environment, download current
certified public artifacts yourself and record SHA-256 hashes, licenses, and
upstream URLs before redistributing them. Do not commit unreviewed wheels here
without an explicit offline-install workflow and provenance notes.
