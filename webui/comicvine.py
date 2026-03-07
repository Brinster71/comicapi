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

    def volume_details(self, volume_id):
        vid = str(volume_id)
        if vid.startswith("4050-"):
            vid = vid.split("-", 1)[1]
        data = self._get(f"/volume/4050-{vid}/")
        return data.get("results", {})

    @staticmethod
    def _normalize_volume_id(volume_id):
        text = str(volume_id or "").strip()
        if not text:
            return ""
        if "-" in text:
            text = text.split("-", 1)[1]
        text = text.lstrip("0")
        return text or "0"

    @classmethod
    def _issue_matches_volume(cls, issue_obj, volume_id):
        vol = (issue_obj or {}).get("volume") or {}
        issue_vid = cls._normalize_volume_id(vol.get("id"))
        wanted_vid = cls._normalize_volume_id(volume_id)
        return bool(issue_vid and wanted_vid and issue_vid == wanted_vid)


    def volume_issues(self, volume_id, limit=100):
        # ComicVine volume IDs are 4050-<id>. Query using canonical prefix and
        # still enforce strict post-filtering by returned issue.volume.id.
        vid = self._normalize_volume_id(volume_id)
        data = self._get("/issues/", filter=f"volume:4050-{vid}", sort="issue_number:asc", limit=limit)
        issues = data.get("results", [])
        strict = [i for i in issues if self._issue_matches_volume(i, vid)]
        if strict:
            return strict

        # Fallback for API variance; still return only strict matches.
        data_alt = self._get("/issues/", filter=f"volume:{vid}", sort="issue_number:asc", limit=limit)
        issues_alt = data_alt.get("results", [])
        return [i for i in issues_alt if self._issue_matches_volume(i, vid)]
