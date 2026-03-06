# Comic Metadata Web UI (MVP)

This repository now includes a minimal built-in web service to scan/read/write comic metadata and query ComicVine.

## Run

From the parent directory of this repo:

```bash
cd /workspace
python -m comicapi.webui.server
```

Then open `http://127.0.0.1:8080`.

## ComicVine

Set your key before starting:

```bash
export COMICVINE_API_KEY=your_key_here
```

The endpoint `GET /api/comicvine/search?query=...` will return series + issue candidate results.

The ComicVine key can be provided either:

- via environment variable (`COMICVINE_API_KEY`), or
- directly from the web UI input (sent as `api_key` query param).

## API quickstart

- `GET /api/scan?root=/path/to/library`
- `GET /api/read?path=/path/to/file.cbz&style=CIX`
- `POST /api/write`
  ```json
  {
    "path": "/path/to/file.cbz",
    "style": "CIX",
    "metadata": {
      "series": "Batman",
      "issue": "1",
      "year": "2011"
    }
  }
  ```

## Notes

- This is an MVP foundation. The next step is to add a richer UI (search result selection, preview diff, batch actions).
- Bringing in your full ComicTagger fork is strongly recommended for production-grade ComicVine mapping behavior and parity with desktop workflows.
