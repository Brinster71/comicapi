import json
import urllib.parse
import urllib.request

API_BASE = "https://comicvine.gamespot.com/api"


class ComicVineClient:
    def __init__(self, api_key, user_agent="comicapi-webui/0.1"):
        self.api_key = api_key
        self.user_agent = user_agent

    def _get(self, path, **params):
        query = {
            "api_key": self.api_key,
            "format": "json",
        }
        query.update(params)
        url = API_BASE + path + "?" + urllib.parse.urlencode(query)
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = resp.read().decode("utf-8", errors="replace")
        data = json.loads(payload)
        if data.get("status_code") not in (1,):
            raise RuntimeError(data.get("error") or "ComicVine request failed")
        return data

    def search_series(self, query, limit=10):
        data = self._get("/search/", query=query, resources="volume", limit=limit)
        return data.get("results", [])

    def search_issue(self, query, limit=10):
        data = self._get("/search/", query=query, resources="issue", limit=limit)
        return data.get("results", [])

    def issue_details(self, issue_id):
        data = self._get(f"/issue/4000-{issue_id}/")
        return data.get("results", {})
