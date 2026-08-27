#!/usr/bin/env python3
"""Fetch Artificial Analysis model data using the official API v2.

Requires:
    ARTIFICIAL_ANALYSIS_API_KEY

Usage:
    export ARTIFICIAL_ANALYSIS_API_KEY="your-key"
    python3 scripts/fetch_leaderboards.py
    python3 scripts/fetch_leaderboards.py --only llms

The script writes daily snapshots under data/YYYY-MM-DD/.
It exits 0 when at least one configured endpoint succeeds, and exits 1
only when every selected endpoint fails.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

API_BASE_URL = "https://artificialanalysis.ai"
API_KEY_ENV = "ARTIFICIAL_ANALYSIS_API_KEY"
USER_AGENT = "artificial-analysis-leaderboards/2.1"
PARSER_VERSION = "api-v2-2"
DEFAULT_DELAY = 1.0
PAGE_SIZE = 200

SOURCES = [
    {
        "slug": "llms",
        "source_type": "api_v2_free",
        "source_url": f"{API_BASE_URL}/api/v2/language/models/free",
        "description": "Artificial Analysis language models via the Free API",
    },
    {
        "slug": "text-to-image",
        "source_type": "api_v2_free",
        "source_url": f"{API_BASE_URL}/api/v2/media/text-to-image/models/free",
        "description": "Artificial Analysis text-to-image Arena rankings",
    },
    {
        "slug": "image-editing",
        "source_type": "api_v2_free",
        "source_url": f"{API_BASE_URL}/api/v2/media/image-editing/models/free",
        "description": "Artificial Analysis image-editing Arena rankings",
    },
    {
        "slug": "text-to-video",
        "source_type": "api_v2_free",
        "source_url": f"{API_BASE_URL}/api/v2/media/text-to-video/models/free",
        "description": "Artificial Analysis text-to-video Arena rankings",
    },
    {
        "slug": "image-to-video",
        "source_type": "api_v2_free",
        "source_url": f"{API_BASE_URL}/api/v2/media/image-to-video/models/free",
        "description": "Artificial Analysis image-to-video Arena rankings",
    },
    {
        "slug": "text-to-speech",
        "source_type": "api_v2_free",
        "source_url": f"{API_BASE_URL}/api/v2/media/text-to-speech/models/free",
        "description": "Artificial Analysis text-to-speech Arena rankings",
    },
    {
        "slug": "speech-to-speech",
        "source_type": "api_v2_free",
        "source_url": f"{API_BASE_URL}/api/v2/media/speech-to-speech/models/free",
        "description": "Artificial Analysis speech-to-speech model data",
    },
    {
        "slug": "speech-to-text",
        "source_type": "api_v2_free",
        "source_url": f"{API_BASE_URL}/api/v2/media/speech-to-text/models/free",
        "description": "Artificial Analysis speech-to-text model data",
    },
    {
        "slug": "text-to-video-audio",
        "source_type": "api_v2_free",
        "source_url": f"{API_BASE_URL}/api/v2/media/text-to-video-audio/models/free",
        "description": "Artificial Analysis text-to-video-with-audio Arena rankings",
    },
    {
        "slug": "image-to-video-audio",
        "source_type": "api_v2_free",
        "source_url": f"{API_BASE_URL}/api/v2/media/image-to-video-audio/models/free",
        "description": "Artificial Analysis image-to-video-with-audio Arena rankings",
    },
]


class ArtificialAnalysisAPIError(RuntimeError):
    pass


class ArtificialAnalysisClient:
    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("API key cannot be empty")
        self.api_key = api_key

    def get(self, url: str) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            method="GET",
            headers={
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
                "x-api-key": self.api_key,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read().decode("utf-8", "ignore")
                return json.loads(body)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "ignore")
            raise ArtificialAnalysisAPIError(
                f"HTTP {exc.code} from Artificial Analysis API\n"
                f"URL: {url}\n"
                f"Response: {body[:2000]}"
            ) from exc
        except urllib.error.URLError as exc:
            raise ArtificialAnalysisAPIError(
                f"Network error calling {url}: {exc}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise ArtificialAnalysisAPIError(
                f"Invalid JSON returned by Artificial Analysis for {url}"
            ) from exc

    def get_all_models(
        self,
        url: str,
        delay: float = DEFAULT_DELAY,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        all_models: list[dict[str, Any]] = []
        page = 1
        first_pagination: dict[str, Any] = {}

        while True:
            separator = "&" if "?" in url else "?"
            page_url = f"{url}{separator}page={page}&page_size={PAGE_SIZE}"
            print(f"  Requesting page {page}...", flush=True)
            payload = self.get(page_url)

            data = payload.get("data")
            if not isinstance(data, list):
                raise ArtificialAnalysisAPIError(
                    f"Unexpected API response from {page_url}: missing list 'data'"
                )
            if not all(isinstance(item, dict) for item in data):
                raise ArtificialAnalysisAPIError(
                    f"Unexpected API response from {page_url}: 'data' contains non-object values"
                )

            all_models.extend(data)
            pagination = payload.get("pagination")
            if isinstance(pagination, dict) and not first_pagination:
                first_pagination = pagination

            has_more = bool(
                pagination.get("has_more", False)
                if isinstance(pagination, dict)
                else False
            )
            print(f"  Received {len(data)} models (total: {len(all_models)})", flush=True)

            if not has_more:
                break

            page += 1
            if delay > 0:
                time.sleep(delay)

        return all_models, first_pagination


def clean_value(value: Any) -> Any:
    if value == "$undefined":
        return None
    if isinstance(value, dict):
        return {key: clean_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clean_value(item) for item in value]
    return value


def normalize_llm(raw: dict[str, Any]) -> dict[str, Any]:
    raw = clean_value(raw)
    creator = raw.get("model_creator") or {}
    return {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "slug": raw.get("slug"),
        "release_date": raw.get("release_date"),
        "reasoning_model": raw.get("reasoning_model"),
        "creator": creator,
        "evaluations": raw.get("evaluations") or {},
        "pricing": raw.get("pricing") or {},
        "performance": raw.get("performance") or {},
        "context_window_tokens": raw.get("context_window_tokens"),
        "parameters": raw.get("parameters") or {},
        "modalities": raw.get("modalities") or {},
        "licensing": raw.get("licensing") or {},
        "huggingface_url": raw.get("huggingface_url"),
        "openrouter_api_id": raw.get("openrouter_api_id"),
    }


def normalize_media(
    raw: dict[str, Any],
    endpoint_slug: str,
    rank: int | None = None,
) -> dict[str, Any]:
    raw = clean_value(raw)
    return {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "slug": raw.get("slug"),
        "release_date": raw.get("release_date", raw.get("releaseDate")),
        "creator": raw.get("model_creator", raw.get("creator")),
        "elo": raw.get("elo"),
        "ci_95": raw.get("ci_95"),
        "rank": raw.get("rank", rank),
        "raw": raw,
    }


def normalize_model(
    raw: dict[str, Any],
    endpoint_slug: str,
    rank: int,
) -> dict[str, Any]:
    if endpoint_slug == "llms":
        return normalize_llm(raw)
    return normalize_media(raw, endpoint_slug, rank)


def fetch_source(
    client: ArtificialAnalysisClient,
    source: dict[str, str],
    delay: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    slug = source["slug"]
    print(f"Fetching {slug}...", flush=True)
    raw_models, pagination = client.get_all_models(source["source_url"], delay=delay)

    models = [
        normalize_model(model, slug, index)
        for index, model in enumerate(raw_models, start=1)
    ]

    meta = {
        "endpoint": slug,
        "source_type": source["source_type"],
        "source_url": source["source_url"],
        "source_description": source["description"],
        "parser_version": PARSER_VERSION,
        "model_count": len(models),
        "pagination": pagination,
    }
    return models, meta


def load_json(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as file:
        return json.load(file)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)
        file.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch Artificial Analysis model data using API v2"
    )
    parser.add_argument(
        "--only",
        nargs="*",
        help="Only fetch specified endpoint slugs",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help=f"Delay between paginated requests (default: {DEFAULT_DELAY})",
    )
    args = parser.parse_args()

    api_key = os.environ.get(API_KEY_ENV)
    if not api_key:
        print(
            f"ERROR: {API_KEY_ENV} environment variable is not set.",
            file=sys.stderr,
        )
        return 1

    sources = SOURCES
    if args.only:
        wanted = set(args.only)
        sources = [source for source in SOURCES if source["slug"] in wanted]
        if not sources:
            available = ", ".join(source["slug"] for source in SOURCES)
            print(f"ERROR: No matching endpoints. Available: {available}", file=sys.stderr)
            return 1

    repo_root = Path(__file__).resolve().parent.parent
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    fetched_at = now.isoformat()
    day_dir = repo_root / "data" / date_str
    day_dir.mkdir(parents=True, exist_ok=True)
    index_path = day_dir / "_index.json"

    if index_path.exists() and args.only:
        index = load_json(index_path)
        index["fetched_at"] = fetched_at
    else:
        index = {
            "date": date_str,
            "fetched_at": fetched_at,
            "source": API_BASE_URL,
            "source_type": "artificial_analysis_api_v2",
            "parser_version": PARSER_VERSION,
            "endpoints": {},
        }

    client = ArtificialAnalysisClient(api_key)
    success_count = 0
    total = len(sources)

    for position, source in enumerate(sources, start=1):
        slug = source["slug"]
        try:
            models, meta = fetch_source(client, source, args.delay)
            meta["fetched_at"] = fetched_at
            save_json(day_dir / f"{slug}.json", {"meta": meta, "models": models})
            index["endpoints"][slug] = {
                "status": "success",
                "model_count": len(models),
                "source_type": source["source_type"],
                "source_url": source["source_url"],
                "file": f"data/{date_str}/{slug}.json",
            }
            success_count += 1
            print(f"✓ {slug}: {len(models)} models", flush=True)
        except Exception as exc:
            print(f"✗ {slug}: {exc}", file=sys.stderr, flush=True)
            index["endpoints"][slug] = {
                "status": "error",
                "error": str(exc),
                "source_type": source["source_type"],
                "source_url": source["source_url"],
            }
        if position < total and args.delay > 0:
            time.sleep(args.delay)

    save_json(index_path, index)
    save_json(
        repo_root / "data" / "latest.json",
        {"date": date_str, "path": f"data/{date_str}"},
    )

    print(f"\nDone: {success_count}/{total} endpoints")
    print(f"Saved to: data/{date_str}/")

    if success_count == 0:
        print("All Artificial Analysis endpoints failed.", file=sys.stderr)
        return 1

    print(f"Successfully fetched {success_count}/{total} Artificial Analysis endpoints.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
