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
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>Comic Metadata UI</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 1rem; }
    .row { display: flex; gap: .5rem; flex-wrap: wrap; align-items: center; margin-bottom: .5rem; }
    input, select, button, textarea { padding: .4rem; }
    input[type=text] { min-width: 20rem; }
    textarea { width: 100%; min-height: 12rem; font-family: ui-monospace, monospace; }
    table { border-collapse: collapse; width: 100%; margin-top: .5rem; }
    th, td { border: 1px solid #ddd; padding: .35rem; text-align: left; }
    tr:hover { background: #f6f6f6; }
    .muted { color: #666; font-size: .9rem; }
    .pill { border-radius: 999px; padding: .1rem .5rem; font-size: .8rem; }
    .good { background: #d7f6dd; color: #145a2a; }
    .warn { background: #fff3cd; color: #7a5b00; }
  </style>
</head>
<body>
  <h2>Comic Metadata UI</h2>
  <p class='muted'>Scan comics, read/edit metadata, and query ComicVine (API key can be entered below).</p>

  <div class='row'>
    <label>Library path:</label>
    <input id='rootPath' type='text' placeholder='/path/to/comics'>
    <button onclick='scanLibrary()'>Scan</button>
  </div>

  <div class='row'>
    <label>Selected file:</label>
    <input id='comicPath' type='text' placeholder='/path/to/file.cbz'>
    <label>Style:</label>
    <select id='style'>
      <option value='AUTO' selected>AUTO</option>
      <option value='CIX'>CIX</option>
      <option value='CBI'>CBI</option>
      <option value='COMET'>COMET</option>
    </select>
    <button onclick='readMetadata()'>Read metadata</button>
    <span id='styleInfo' class='muted'></span>
  </div>

  <div class='row'>
    <label>ComicVine API key:</label>
    <input id='apiKey' type='text' placeholder='paste API key here (or use COMICVINE_API_KEY env var)'>
    <label>Search:</label>
    <input id='cvQuery' type='text' placeholder='Batman 2011 1'>
    <button onclick='searchComicVine()'>Search ComicVine</button>
  </div>

  <div class='row'>
    <button onclick='writeMetadata()'>Write metadata patch to selected file</button>
  </div>

  <h3>Scan results</h3>
  <div class='muted'>Click a row to select a comic file.</div>
  <table id='scanTable'>
    <thead><tr><th>Path</th><th>Pages</th><th>CIX</th><th>CBI</th><th>COMET</th><th>Error</th></tr></thead>
    <tbody></tbody>
  </table>

  <h3>Metadata (JSON)</h3>
  <textarea id='metadataJson' placeholder='Read metadata first, then edit JSON fields...'></textarea>

  <h3>ComicVine issue candidates</h3>
  <div class='muted'>Match hint compares your loaded metadata (series/issue/year/volume) against returned issue rows.</div>
  <table id='issueTable'>
    <thead><tr><th>Match hint</th><th>Issue #</th><th>Series</th><th>Volume start</th><th>Cover date</th><th>Issue ID</th></tr></thead>
    <tbody></tbody>
  </table>

  <h3>ComicVine series candidates</h3>
  <table id='seriesTable'>
    <thead><tr><th>Name</th><th>Start year</th><th>Issue count</th><th>ID</th></tr></thead>
    <tbody></tbody>
  </table>

  <details>
    <summary>Raw ComicVine JSON</summary>
    <textarea id='comicvineJson' placeholder='ComicVine search results appear here...'></textarea>
  </details>

  <script>
    function showJson(id, obj) {
      document.getElementById(id).value = JSON.stringify(obj, null, 2);
    }

    function normalizeIssue(val) {
      const s = String(val || '').trim();
      if (!s) return '';
      const m = s.match(/^(\\d+)(.*)$/);
      if (!m) return s.toLowerCase();
      const n = String(parseInt(m[1], 10));
      return (Number.isNaN(parseInt(m[1], 10)) ? m[1] : n) + (m[2] || '').toLowerCase();
    }

    function parseLoadedMetadata() {
      try {
        const raw = JSON.parse(document.getElementById('metadataJson').value || '{}');
        return raw.metadata && typeof raw.metadata === 'object' ? raw.metadata : raw;
      } catch (_) {
        return {};
      }
    }

    function looksLikeMatch(md, issue) {
      const mdSeries = String(md.series || '').toLowerCase();
      const mdIssue = normalizeIssue(md.issue || '');
      const mdYear = String(md.year || '').trim();
      const mdVolume = String(md.volume || '').trim();

      const issueNum = normalizeIssue(issue.issue_number || '');
      const volume = issue.volume || {};
      const volumeName = String(volume.name || '').toLowerCase();
      const volumeYear = String(volume.start_year || '').trim();

      const issueMatch = mdIssue && issueNum && mdIssue === issueNum;
      const seriesMatch = mdSeries && volumeName && (mdSeries === volumeName || volumeName.includes(mdSeries));
      const yearMatch = mdYear && volumeYear && mdYear === volumeYear;
      const volumeMatch = mdVolume && volumeYear && mdVolume === volumeYear;

      const score = [issueMatch, seriesMatch, yearMatch || volumeMatch].filter(Boolean).length;
      if (score >= 2) return {label: 'Likely', cls: 'good'};
      if (score === 1) return {label: 'Possible', cls: 'warn'};
      return {label: 'Unclear', cls: 'warn'};
    }

    function renderComicVine(data) {
      const md = parseLoadedMetadata();

      const issueBody = document.querySelector('#issueTable tbody');
      issueBody.innerHTML = '';
      (data.issues || []).forEach(i => {
        const volume = i.volume || {};
        const hint = looksLikeMatch(md, i);
        const tr = document.createElement('tr');
        tr.innerHTML =
          `<td><span class='pill ${hint.cls}'>${hint.label}</span></td>` +
          `<td>${i.issue_number || ''}</td>` +
          `<td>${volume.name || ''}</td>` +
          `<td>${volume.start_year || ''}</td>` +
          `<td>${i.cover_date || ''}</td>` +
          `<td>${i.id || ''}</td>`;
        issueBody.appendChild(tr);
      });

      const seriesBody = document.querySelector('#seriesTable tbody');
      seriesBody.innerHTML = '';
      (data.series || []).forEach(s => {
        const tr = document.createElement('tr');
        tr.innerHTML =
          `<td>${s.name || ''}</td>` +
          `<td>${s.start_year || ''}</td>` +
          `<td>${s.count_of_issues || ''}</td>` +
          `<td>${s.id || ''}</td>`;
        seriesBody.appendChild(tr);
      });
    }

    async function scanLibrary() {
      const root = document.getElementById('rootPath').value.trim();
      if (!root) return alert('Enter a library path first.');
      const res = await fetch('/api/scan?root=' + encodeURIComponent(root));
      const data = await res.json();
      const tbody = document.querySelector('#scanTable tbody');
      tbody.innerHTML = '';
      (data.results || []).forEach(r => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${r.path || ''}</td><td>${r.pages ?? ''}</td><td>${r.has_cix ?? ''}</td><td>${r.has_cbi ?? ''}</td><td>${r.has_comet ?? ''}</td><td>${r.error || ''}</td>`;
        tr.onclick = () => { if (r.path) document.getElementById('comicPath').value = r.path; };
        tbody.appendChild(tr);
      });
    }

    async function readMetadata() {
      const path = document.getElementById('comicPath').value.trim();
      const style = document.getElementById('style').value;
      if (!path) return alert('Select or enter a comic file path first.');
      const res = await fetch('/api/read?path=' + encodeURIComponent(path) + '&style=' + encodeURIComponent(style));
      const data = await res.json();
      showJson('metadataJson', data);
      if (data.style) {
        document.getElementById('style').value = data.style;
      }
      document.getElementById('styleInfo').textContent = data.detected_style ? `Detected: ${data.detected_style}` : '';
    }

    async function writeMetadata() {
      const path = document.getElementById('comicPath').value.trim();
      const style = document.getElementById('style').value;
      if (!path) return alert('Select or enter a comic file path first.');
      let obj;
      try { obj = JSON.parse(document.getElementById('metadataJson').value || '{}'); }
      catch (e) { return alert('Metadata JSON is invalid: ' + e); }

      const patch = obj.metadata && typeof obj.metadata === 'object' ? obj.metadata : obj;
      const res = await fetch('/api/write', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ path, style, metadata: patch })
      });
      showJson('metadataJson', await res.json());
    }

    async function searchComicVine() {
      const query = document.getElementById('cvQuery').value.trim();
      const apiKey = document.getElementById('apiKey').value.trim();
      if (!query) return alert('Enter a ComicVine search query first.');
      const qp = '/api/comicvine/search?query=' + encodeURIComponent(query)
        + (apiKey ? '&api_key=' + encodeURIComponent(apiKey) : '');
      const res = await fetch(qp);
      const data = await res.json();
      showJson('comicvineJson', data);
      renderComicVine(data);
    }
  </script>
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


def detect_style(ca):
    for style_name in ("CIX", "CBI", "COMET"):
        if ca.hasMetadata(STYLE_MAP[style_name]):
            return style_name
    return "CIX"


class Handler(BaseHTTPRequestHandler):
    server_version = "ComicWebUI/0.3"

    def _comicvine_client(self, qs):
        user_key = qs.get("api_key", [""])[0].strip()
        env_key = os.environ.get("COMICVINE_API_KEY", "").strip()
        key = user_key or env_key
        return ComicVineClient(key) if key else None

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
            style = qs.get("style", ["AUTO"])[0].upper()
            if not path:
                return self._json(400, {"error": "path query param required"})
            if style != "AUTO" and style not in STYLE_MAP:
                return self._json(400, {"error": "style must be AUTO, CIX, CBI, or COMET"})
            ca = ComicArchive(path, default_image_path=path)
            detected_style = detect_style(ca)
            use_style = detected_style if style == "AUTO" else style
            md = ca.readMetadata(STYLE_MAP[use_style])
            return self._json(
                200,
                {
                    "path": path,
                    "style": use_style,
                    "detected_style": detected_style,
                    "metadata": metadata_to_dict(md),
                },
            )

        if parsed.path == "/api/comicvine/search":
            query = qs.get("query", [""])[0]
            if not query:
                return self._json(400, {"error": "query required"})
            client = self._comicvine_client(qs)
            if client is None:
                return self._json(400, {"error": "Provide api_key query param or set COMICVINE_API_KEY environment variable"})
            series = client.search_series(query)
            issues = client.search_issue(query)
            return self._json(200, {"query": query, "series": series, "issues": issues})

        return self._json(404, {"error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/write":
            return self._json(404, {"error": "not found"})

        payload = self._read_json()
        path = payload.get("path", "")
        style = str(payload.get("style", "AUTO")).upper()
        patch = payload.get("metadata", {})
        if not path:
            return self._json(400, {"error": "path is required"})
        if style != "AUTO" and style not in STYLE_MAP:
            return self._json(400, {"error": "style must be AUTO, CIX, CBI, or COMET"})

        ca = ComicArchive(path, default_image_path=path)
        detected_style = detect_style(ca)
        use_style = detected_style if style == "AUTO" else style
        md = ca.readMetadata(STYLE_MAP[use_style])
        if getattr(md, "isEmpty", False):
            md = ca.metadataFromFilename(parse_scan_info=True)
        apply_metadata(md, patch)
        ok = ca.writeMetadata(md, STYLE_MAP[use_style])
        return self._json(200, {"ok": bool(ok), "path": path, "style": use_style, "detected_style": detected_style})


def run(host="127.0.0.1", port=8080):
    srv = ThreadingHTTPServer((host, int(port)), Handler)
    print(f"Serving Comic Metadata UI at http://{host}:{port}")
    srv.serve_forever()


if __name__ == "__main__":
    run(host=os.environ.get("COMIC_WEBUI_HOST", "127.0.0.1"), port=os.environ.get("COMIC_WEBUI_PORT", "8080"))
