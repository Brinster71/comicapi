# Comic Metadata Web UI (MVP)

This repository now includes a minimal built-in web service to scan/read/write comic metadata and query ComicVine.

## Run

From the parent directory of this repo:

```bash
cd /workspace
python -m comicapi.webui.server
```

Then open `http://127.0.0.1:8080`.

In the UI, **Library Browse…** now helps choose/enter a folder path without uploading folder contents. Scanning still uses the server-side path you provide in `Library path`.

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
- `GET /api/read?path=/path/to/file.cbz&style=AUTO`
- `GET /api/assess?path=/path/to/file.cbz&style=AUTO`
- `GET /api/version`
- `POST /api/write`
  ```json
  {
    "path": "/path/to/file.cbz",
    "style": "AUTO",
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


- `AUTO` detects the existing metadata format (CIX/CBI/CoMet) and uses that style for read/write operations.
- `GET /api/assess` returns a merged recommendation using existing embedded metadata plus filename-derived hints.
- The **Write to** field controls output location; when set to a different path, the server copies the source file and writes metadata to that destination.
- ComicVine search now reports API errors in the status area and can build series options from issue results when direct series results are sparse.
- The UI shows a runtime diagnostics banner (server version, git commit, module path, features) from `GET /api/version` to verify which build is running.
- ComicVine results are shown as readable tables with match hints (issue/series/year alignment) in the UI.
