"""Download TTC's surface (bus + streetcar) static GTFS dataset and extract it.

Resolves the current download URL via Toronto's CKAN API rather than
hardcoding one, since CKAN resource IDs rotate when the city republishes
the dataset (TTC updates it roughly every 6 weeks).
"""
import io
import zipfile
from pathlib import Path

import requests

CKAN_PACKAGE_API = "https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/package_show"
DATASET_ID = "ttc-routes-and-schedules"
FALLBACK_URL = (
    "https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/"
    "bd4809dd-e289-4de8-bbde-c5c00dafbf4f/resource/"
    "28514055-d011-4ed7-8bb0-97961dfe2b66/download/SurfaceGTFS.zip"
)
STATIC_DIR = Path(__file__).resolve().parent.parent / "data" / "static"


def resolve_download_url() -> str:
    try:
        resp = requests.get(CKAN_PACKAGE_API, params={"id": DATASET_ID}, timeout=10)
        resp.raise_for_status()
        resources = resp.json()["result"]["resources"]
        for resource in resources:
            name = (resource.get("name") or "").lower()
            url = resource.get("url", "")
            if "surface" in name and url.endswith(".zip"):
                return url
    except (requests.RequestException, KeyError, ValueError):
        pass
    return FALLBACK_URL


def main():
    url = resolve_download_url()
    print(f"Downloading static GTFS from {url}")
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        zf.extractall(STATIC_DIR)
    print(f"Extracted to {STATIC_DIR}")


if __name__ == "__main__":
    main()
