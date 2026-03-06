# comicapi

This repository contains the core comic-archive metadata logic (read/write ComicInfo/CBI/CoMet) plus a minimal web UI/API for trying workflows in a browser.

## Quick start

From the parent directory (`/workspace` in this environment):

```bash
cd /workspace
python -m comicapi.webui.server
```

Then open:

- `http://127.0.0.1:8080/`

If you need external/browser-container access, bind all interfaces:

```bash
cd /workspace
COMIC_WEBUI_HOST=0.0.0.0 python -m comicapi.webui.server
```

## How to test

Run these from the repo root (`/workspace/comicapi`):

### 1) Python syntax/import smoke check

```bash
python -m compileall -q comicarchive.py comicinfoxml.py comicbookinfo.py comet.py genericmetadata.py filenameparser.py issuestring.py utils.py webui
```

### 2) Automated tests

```bash
pytest -q
```

Expected result in minimal environments:

- `tests/test_sanity.py` passes.
- `UnRAR2/test_UnRAR2.py` is skipped when system `rar/unrar` is not installed.

## API smoke tests

Start the server first, then run:

```bash
curl -sS http://127.0.0.1:8080/
curl -sS "http://127.0.0.1:8080/api/comicvine/search?query=Batman&api_key=YOUR_KEY"
```

Without a ComicVine key, the endpoint returns a 400 error. You can either set `COMICVINE_API_KEY` or pass `api_key` directly in the query string.

## ComicVine setup

```bash
export COMICVINE_API_KEY=your_key_here
```

Then restart the server and call:

```bash
curl -sS "http://127.0.0.1:8080/api/comicvine/search?query=Batman&api_key=YOUR_KEY"
```

## Metadata API examples

Read metadata:

```bash
curl -sS "http://127.0.0.1:8080/api/read?path=/path/to/file.cbz&style=CIX"
```

Write metadata:

```bash
curl -sS -X POST http://127.0.0.1:8080/api/write \
  -H "Content-Type: application/json" \
  -d '{
    "path": "/path/to/file.cbz",
    "style": "CIX",
    "metadata": {
      "series": "Batman",
      "issue": "1",
      "year": "2011"
    }
  }'
```

Scan a library directory:

```bash
curl -sS "http://127.0.0.1:8080/api/scan?root=/path/to/comics"
```

## Notes

- The web UI is intentionally minimal (MVP) and focused on API-first workflows.
- For richer ComicVine mapping and production behavior, integrating your full ComicTagger fork is recommended.
