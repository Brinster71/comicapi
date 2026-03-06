import json
import os
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .comicvine import ComicVineClient
from ..comicarchive import ComicArchive, MetaDataStyle


INDEX_HTML = """<!doctype html>
<html>
<head><meta charset='utf-8'><title>Comic Metadata UI</title></head>
<body>
<h2>Comic Metadata UI (MVP)</h2>
<p>Use the API endpoints below. This page is intentionally minimal for now.</p>
<ul>
  <li>GET /api/scan?root=/path/to/library</li>
  <li>GET /api/read?path=/path/to/file.cbz&style=CIX</li>
  <li>POST /api/write {"path":"...","style":"CIX","metadata":{"series":"...","issue":"1"}}</li>
  <li>GET /api/comicvine/search?query=Batman</li>
</ul>
</body>
</html>"""

STYLE_MAP = {
    "CBI": MetaDataStyle.CBI,
    "CIX": MetaDataStyle.CIX,
    "COMET": MetaDataStyle.COMET,
}


@dataclass
class ComicSummary:
    path: str
    pages: int
    has_cix: bool
    has_cbi: bool
    has_comet: bool


def metadata_to_dict(md):
    if md is None:
        return {}
    out = {}
    for k, v in vars(md).items():
        if k.startswith("_"):
            continue
        if callable(v):
            continue
        out[k] = v
    return out


def apply_metadata(md, patch):
    for k, v in patch.items():
        if hasattr(md, k):
            setattr(md, k, v)


class Handler(BaseHTTPRequestHandler):
    server_version = "ComicWebUI/0.1"

    @property
    def cv_client(self):
        api_key = os.environ.get("COMICVINE_API_KEY", "").strip()
        return ComicVineClient(api_key) if api_key else None

    def _json(self, status, payload):
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        n = int(self.headers.get("Content-Length", "0"))
        data = self.rfile.read(n) if n else b"{}"
        return json.loads(data.decode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        if parsed.path == "/":
            body = INDEX_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/scan":
            root = qs.get("root", [""])[0]
            if not root:
                return self._json(400, {"error": "root query param required"})
            exts = {".cbz", ".cbr", ".cbt", ".pdf", ".zip", ".rar"}
            results = []
            for p in Path(root).rglob("*"):
                if p.is_file() and p.suffix.lower() in exts:
                    try:
                        ca = ComicArchive(str(p), default_image_path=str(p))
                        summary = ComicSummary(
                            path=str(p),
                            pages=ca.getNumberOfPages(),
                            has_cix=ca.hasMetadata(MetaDataStyle.CIX),
                            has_cbi=ca.hasMetadata(MetaDataStyle.CBI),
                            has_comet=ca.hasMetadata(MetaDataStyle.COMET),
                        )
                        results.append(asdict(summary))
                    except Exception as exc:
                        results.append({"path": str(p), "error": str(exc)})
            return self._json(200, {"count": len(results), "results": results})

        if parsed.path == "/api/read":
            path = qs.get("path", [""])[0]
            style = qs.get("style", ["CIX"])[0].upper()
            if not path:
                return self._json(400, {"error": "path query param required"})
            if style not in STYLE_MAP:
                return self._json(400, {"error": "style must be one of CIX/CBI/COMET"})
            ca = ComicArchive(path, default_image_path=path)
            md = ca.readMetadata(STYLE_MAP[style])
            return self._json(200, {"path": path, "style": style, "metadata": metadata_to_dict(md)})

        if parsed.path == "/api/comicvine/search":
            query = qs.get("query", [""])[0]
            if not query:
                return self._json(400, {"error": "query required"})
            if self.cv_client is None:
                return self._json(400, {"error": "Set COMICVINE_API_KEY environment variable"})
            series = self.cv_client.search_series(query)
            issues = self.cv_client.search_issue(query)
            return self._json(200, {"query": query, "series": series, "issues": issues})

        return self._json(404, {"error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/write":
            return self._json(404, {"error": "not found"})

        payload = self._read_json()
        path = payload.get("path", "")
        style = str(payload.get("style", "CIX")).upper()
        patch = payload.get("metadata", {})
        if not path or style not in STYLE_MAP:
            return self._json(400, {"error": "path and valid style required"})

        ca = ComicArchive(path, default_image_path=path)
        md = ca.readMetadata(STYLE_MAP[style])
        if getattr(md, "isEmpty", False):
            md = ca.metadataFromFilename(parse_scan_info=True)
        apply_metadata(md, patch)
        ok = ca.writeMetadata(md, STYLE_MAP[style])
        return self._json(200, {"ok": bool(ok), "path": path, "style": style})


def run(host="127.0.0.1", port=8080):
    srv = ThreadingHTTPServer((host, int(port)), Handler)
    print(f"Serving Comic Metadata UI at http://{host}:{port}")
    srv.serve_forever()


if __name__ == "__main__":
    run(host=os.environ.get("COMIC_WEBUI_HOST", "127.0.0.1"), port=os.environ.get("COMIC_WEBUI_PORT", "8080"))
