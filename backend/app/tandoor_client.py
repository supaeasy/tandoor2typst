import re
from urllib.parse import urlparse

import requests

from fastapi import HTTPException


class TandoorClient:
    def __init__(self, host: str, token: str):
        self.host = host.rstrip("/")
        self.api_url = f"{self.host}/api"
        self.headers = {"Authorization": f"Bearer {token}"}

    def _get(self, url: str, params: dict | None = None) -> dict:
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
        except requests.RequestException as exc:
            raise HTTPException(status_code=502, detail=f"Could not reach Tandoor host: {exc}") from exc
        if response.status_code == 401 or response.status_code == 403:
            raise HTTPException(status_code=401, detail="Tandoor rejected the API token.")
        if response.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Tandoor API error {response.status_code}: {response.text[:300]}")
        return response.json()

    @staticmethod
    def extract_domain(url: str | None) -> str | None:
        if not url:
            return None
        parsed = urlparse(url)
        domain = re.sub(r"^www\.", "", parsed.netloc)
        return domain if domain else url

    def fetch_recipe(self, recipe_id: int) -> dict:
        recipe_data = self._get(f"{self.api_url}/recipe/{recipe_id}/")
        source_url = recipe_data.get("source_url")
        recipe_data["source_domain"] = self.extract_domain(source_url) if source_url else None
        return recipe_data

    def fetch_all_recipe_ids(self) -> list[int]:
        ids: list[int] = []
        url: str | None = f"{self.api_url}/recipe/"
        params = {"page_size": 100}
        while url:
            data = self._get(url, params=params)
            ids.extend(r["id"] for r in data.get("results", []))
            url = data.get("next")
            params = None
        return ids

    def download_image(self, recipe_data: dict) -> tuple[bytes, str] | None:
        image_url = recipe_data.get("image")
        if not image_url:
            return None
        try:
            response = requests.get(image_url, timeout=30)
        except requests.RequestException:
            return None
        if response.status_code != 200:
            return None
        extension = image_url.split("?")[0].rsplit(".", 1)[-1]
        if not extension or len(extension) > 5:
            extension = "jpg"
        return response.content, extension
