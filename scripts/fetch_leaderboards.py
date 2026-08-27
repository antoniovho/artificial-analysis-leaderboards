#!/usr/bin/env python3
"""
Fetch Artificial Analysis model data using the official API v2.

Requires:
    ARTIFICIAL_ANALYSIS_API_KEY

Example:
    export ARTIFICIAL_ANALYSIS_API_KEY="your-key"
    python3 scripts/fetch_leaderboards.py

Only specific endpoints:
    python3 scripts/fetch_leaderboards.py --only llms

Custom delay:
    python3 scripts/fetch_leaderboards.py --delay 1

Data is saved as:

    data/
        2026-08-27/
            _index.json
            llms.json
            text-to-image.json
            text-to-video.json
            image-to-video.json
        latest.json

The API key is NEVER written to disk.
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


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_BASE_URL = "https://artificialanalysis.ai"

API_KEY_ENV = "ARTIFICIAL_ANALYSIS_API_KEY"

USER_AGENT = (
    "artificial-analysis-leaderboards/2.0 "
    "(https://github.com/)"
)

PARSER_VERSION = "api-v2-1"

DEFAULT_DELAY = 1.0

PAGE_SIZE = 200


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------
#
# IMPORTANT:
#
# The language endpoint is the Free API endpoint.
#
# Media endpoints may depend on the API tier available to your key.
# If one of them returns 403/401, remove it from SOURCES or change it
# according to the endpoints available in your Artificial Analysis account.
#
# ---------------------------------------------------------------------------

SOURCES = [
    {
        "slug": "llms",
        "source_type": "api_v2",
        "source_url": (
            f"{API_BASE_URL}/api/v2/language/models/free"
        ),
        "description": (
            "Artificial Analysis language models "
            "via the Free API"
        ),
    },
    {
        "slug": "text-to-image",
        "source_type": "api_v2",
        "source_url": (
            f"{API_BASE_URL}/api/v2/media/text-to-image/models"
        ),
        "description": (
            "Artificial Analysis text-to-image models"
        ),
    },
    {
        "slug": "text-to-video",
        "source_type": "api_v2",
        "source_url": (
            f"{API_BASE_URL}/api/v2/media/text-to-video/models"
        ),
        "description": (
            "Artificial Analysis text-to-video models"
        ),
    },
    {
        "slug": "image-to-video",
        "source_type": "api_v2",
        "source_url": (
            f"{API_BASE_URL}/api/v2/media/image-to-video/models"
        ),
        "description": (
            "Artificial Analysis image-to-video models"
        ),
    },
]


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------


class ArtificialAnalysisAPIError(RuntimeError):
    """Raised when Artificial Analysis API returns an error."""


class ArtificialAnalysisClient:
    def __init__(
        self,
        api_key: str,
        user_agent: str = USER_AGENT,
    ) -> None:
        if not api_key:
            raise ValueError("API key cannot be empty")

        self.api_key = api_key
        self.user_agent = user_agent

    def get(
        self,
        url: str,
    ) -> dict[str, Any]:
        """
        Perform authenticated GET request.

        The API key is sent via:
            x-api-key
        """

        request = urllib.request.Request(
            url,
            method="GET",
            headers={
                "Accept": "application/json",
                "User-Agent": self.user_agent,
                "x-api-key": self.api_key,
            },
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=60,
            ) as response:

                body = response.read().decode(
                    "utf-8",
                    "ignore",
                )

                try:
                    return json.loads(body)
                except json.JSONDecodeError as exc:
                    raise ArtificialAnalysisAPIError(
                        f"Invalid JSON returned by API "
                        f"for {url}"
                    ) from exc

        except urllib.error.HTTPError as exc:

            body = exc.read().decode(
                "utf-8",
                "ignore",
            )

            # Never print the API key.
            safe_url = self._redact_url(url)

            message = (
                f"HTTP {exc.code} from Artificial Analysis API\n"
                f"URL: {safe_url}\n"
                f"Response: {body[:2000]}"
            )

            raise ArtificialAnalysisAPIError(
                message
            ) from exc

        except urllib.error.URLError as exc:

            safe_url = self._redact_url(url)

            raise ArtificialAnalysisAPIError(
                f"Network error calling {safe_url}: {exc}"
            ) from exc

    @staticmethod
    def _redact_url(url: str) -> str:
        """
        Remove potential API key-like query parameters.

        Normally the API key is sent through a header, but this
        makes logging safer if URLs are extended later.
        """

        try:
            parsed = urllib.parse.urlparse(url)

            query = urllib.parse.parse_qsl(
                parsed.query,
                keep_blank_values=True,
            )

            safe_query = []

            for key, value in query:

                if key.lower() in {
                    "api_key",
                    "apikey",
                    "key",
                    "x-api-key",
                }:
                    value = "***REDACTED***"

                safe_query.append(
                    (
                        urllib.parse.quote(key),
                        urllib.parse.quote(value),
                    )
                )

            query_string = "&".join(
                f"{key}={value}"
                for key, value in safe_query
            )

            return urllib.parse.urlunparse(
                (
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path,
                    parsed.params,
                    query_string,
                    parsed.fragment,
                )
            )

        except Exception:
            return url

    def get_all_models(
        self,
        url: str,
        page_size: int = PAGE_SIZE,
        delay: float = DEFAULT_DELAY,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """
        Fetch all pages from an API v2 endpoint.

        Expected structure:

            {
                "pagination": {
                    "page": 1,
                    "page_size": 200,
                    "total_pages": 2,
                    "has_more": true
                },
                "data": [...]
            }

        Returns:

            models
            pagination metadata
        """

        all_models: list[dict[str, Any]] = []

        page = 1

        first_payload: dict[str, Any] | None = None

        while True:

            separator = (
                "&"
                if "?" in url
                else "?"
            )

            page_url = (
                f"{url}"
                f"{separator}"
                f"page={page}"
                f"&page_size={page_size}"
            )

            print(
                f"  Requesting page {page}...",
                flush=True,
            )

            payload = self.get(page_url)

            if first_payload is None:
                first_payload = payload

            data = payload.get("data")

            if data is None:
                raise ArtificialAnalysisAPIError(
                    "Unexpected API response: "
                    f"'data' field is missing from {page_url}"
                )

            if not isinstance(data, list):
                raise ArtificialAnalysisAPIError(
                    "Unexpected API response: "
                    f"'data' is not a list in {page_url}"
                )

            for item in data:

                if not isinstance(item, dict):
                    raise ArtificialAnalysisAPIError(
                        "Unexpected API response: "
                        "an item in 'data' is not an object"
                    )

            all_models.extend(data)

            pagination = payload.get(
                "pagination",
                {},
            )

            if not isinstance(
                pagination,
                dict,
            ):
                pagination = {}

            has_more = pagination.get(
                "has_more",
                False,
            )

            total_pages = pagination.get(
                "total_pages"
            )

            print(
                f"  Received {len(data)} models "
                f"(total: {len(all_models)})",
                flush=True,
            )

            if not has_more:
                break

            if total_pages is not None:

                try:
                    total_pages_int = int(
                        total_pages
                    )
                except (TypeError, ValueError):
                    total_pages_int = None

                if (
                    total_pages_int is not None
                    and page >= total_pages_int
                ):
                    break

            page += 1

            if delay > 0:
                time.sleep(delay)

        pagination_metadata = {}

        if first_payload:
            pagination_metadata = (
                first_payload.get(
                    "pagination",
                    {},
                )
            )

        return (
            all_models,
            pagination_metadata,
        )


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def clean_value(value: Any) -> Any:
    """
    Recursively clean special values returned by some
    web/API surfaces.

    "$undefined" -> None
    """

    if value == "$undefined":
        return None

    if isinstance(value, dict):
        return {
            key: clean_value(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            clean_value(item)
            for item in value
        ]

    return value


def normalize_llm(
    raw: dict[str, Any],
) -> dict[str, Any]:
    """
    Normalize a language model.

    IMPORTANT:
    We deliberately preserve complete nested objects such as
    evaluations/pricing/performance.

    This makes the historical dataset more future-proof if
    Artificial Analysis adds new benchmark fields.
    """

    raw = clean_value(raw)

    creator = raw.get(
        "model_creator"
    ) or {}

    if not isinstance(
        creator,
        dict,
    ):
        creator = {}

    evaluations = raw.get(
        "evaluations"
    ) or {}

    pricing = raw.get(
        "pricing"
    ) or {}

    performance = raw.get(
        "performance"
    ) or {}

    parameters = raw.get(
        "parameters"
    ) or {}

    modalities = raw.get(
        "modalities"
    ) or {}

    licensing = raw.get(
        "licensing"
    ) or {}

    return {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "slug": raw.get("slug"),
        "release_date": raw.get(
            "release_date"
        ),
        "reasoning_model": raw.get(
            "reasoning_model"
        ),

        "creator": {
            "id": creator.get("id"),
            "name": creator.get("name"),
            "country": creator.get("country"),
        },

        "evaluations": evaluations,

        "pricing": pricing,

        "performance": performance,

        "context_window_tokens": raw.get(
            "context_window_tokens"
        ),

        "parameters": parameters,

        "modalities": modalities,

        "licensing": licensing,

        "huggingface_url": raw.get(
            "huggingface_url"
        ),

        "openrouter_api_id": raw.get(
            "openrouter_api_id"
        ),
    }


def normalize_media(
    raw: dict[str, Any],
    endpoint_slug: str,
    rank: int | None = None,
) -> dict[str, Any]:
    """
    Normalize media model.

    Media schemas may differ from language models.

    We therefore preserve the original API payload in
    `raw` while also exposing common fields.
    """

    raw = clean_value(raw)

    result = {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "slug": raw.get("slug"),

        "release_date": raw.get(
            "release_date",
            raw.get("releaseDate"),
        ),

        "creator": raw.get(
            "creator",
        ),

        "family": raw.get(
            "family",
        ),

        "rank": raw.get(
            "overall_rank",
            raw.get(
                "overallRank",
                rank,
            ),
        ),

        "raw": raw,
    }

    return result


def normalize_model(
    raw: dict[str, Any],
    endpoint_slug: str,
    rank: int | None = None,
) -> dict[str, Any]:

    if endpoint_slug == "llms":
        return normalize_llm(raw)

    return normalize_media(
        raw,
        endpoint_slug,
        rank,
    )


# ---------------------------------------------------------------------------
# Fetch source
# ---------------------------------------------------------------------------


def fetch_source(
    client: ArtificialAnalysisClient,
    source: dict[str, str],
    delay: float,
) -> tuple[
    list[dict[str, Any]],
    dict[str, Any],
]:

    slug = source["slug"]

    source_url = source["source_url"]

    print(
        f"Fetching {slug}...",
        flush=True,
    )

    raw_models, pagination = (
        client.get_all_models(
            source_url,
            page_size=PAGE_SIZE,
            delay=delay,
        )
    )

    models = [
        normalize_model(
            raw_model,
            slug,
            rank=index,
        )
        for index, raw_model
        in enumerate(
            raw_models,
            start=1,
        )
    ]

    meta = {
        "endpoint": slug,
        "source_type": source[
            "source_type"
        ],
        "source_url": source[
            "source_url"
        ],
        "source_description": source[
            "description"
        ],
        "parser_version": PARSER_VERSION,
        "model_count": len(models),
        "pagination": pagination,
    }

    return (
        models,
        meta,
    )


# ---------------------------------------------------------------------------
# File handling
# ---------------------------------------------------------------------------


def load_json(
    path: Path,
) -> dict[str, Any]:

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(file)


def save_json(
    path: Path,
    data: Any,
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )

        file.write("\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Fetch Artificial Analysis "
            "model data using API v2"
        )
    )

    parser.add_argument(
        "--only",
        nargs="*",
        help=(
            "Only fetch specified endpoint slugs. "
            "Example: --only llms"
        ),
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help=(
            "Delay between paginated requests "
            f"(default: {DEFAULT_DELAY})"
        ),
    )

    args = parser.parse_args()

    # -----------------------------------------------------------------------
    # API key
    # -----------------------------------------------------------------------

    api_key = os.environ.get(
        API_KEY_ENV
    )

    if not api_key:

        print(
            "ERROR: Missing API key.",
            file=sys.stderr,
        )

        print(
            f"Set the {API_KEY_ENV} "
            "environment variable.",
            file=sys.stderr,
        )

        print(
            "",
            file=sys.stderr,
        )

        print(
            "Example:",
            file=sys.stderr,
        )

        print(
            f"  export {API_KEY_ENV}='YOUR_API_KEY'",
            file=sys.stderr,
        )

        sys.exit(1)

    # -----------------------------------------------------------------------
    # Select sources
    # -----------------------------------------------------------------------

    sources = SOURCES

    if args.only:

        wanted = set(
            args.only
        )

        sources = [
            source
            for source in SOURCES
            if source["slug"] in wanted
        ]

        if not sources:

            available = ", ".join(
                source["slug"]
                for source in SOURCES
            )

            print(
                "ERROR: No matching endpoints.",
                file=sys.stderr,
            )

            print(
                f"Available: {available}",
                file=sys.stderr,
            )

            sys.exit(1)

    # -----------------------------------------------------------------------
    # Client
    # -----------------------------------------------------------------------

    client = ArtificialAnalysisClient(
        api_key=api_key,
    )

    # -----------------------------------------------------------------------
    # Dates / directories
    # -----------------------------------------------------------------------

    script_dir = Path(
        __file__
    ).resolve().parent

    repo_root = script_dir.parent

    now = datetime.now(
        timezone.utc
    )

    date_str = now.strftime(
        "%Y-%m-%d"
    )

    fetched_at = now.isoformat()

    day_dir = (
        repo_root
        / "data"
        / date_str
    )

    day_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    index_path = (
        day_dir
        / "_index.json"
    )

    # -----------------------------------------------------------------------
    # Existing index
    # -----------------------------------------------------------------------

    if (
        index_path.exists()
        and args.only
    ):

        index = load_json(
            index_path
        )

        index[
            "fetched_at"
        ] = fetched_at

    else:

        index = {
            "date": date_str,

            "fetched_at": fetched_at,

            "source": API_BASE_URL,

            "source_type": "artificial_analysis_api_v2",

            "parser_version": PARSER_VERSION,

            "endpoints": {},
        }

    # -----------------------------------------------------------------------
    # Fetch
    # -----------------------------------------------------------------------

    success_count = 0

    total = len(
        sources
    )

    for index_number, source in enumerate(
        sources,
        start=1,
    ):

        slug = source["slug"]

        try:

            models, meta = fetch_source(
                client,
                source,
                delay=args.delay,
            )

            meta[
                "fetched_at"
            ] = fetched_at

            output = {
                "meta": meta,
                "models": models,
            }

            output_path = (
                day_dir
                / f"{slug}.json"
            )

            save_json(
                output_path,
                output,
            )

            index[
                "endpoints"
            ][slug] = {
                "status": "success",

                "model_count": len(
                    models
                ),

                "source_type": source[
                    "source_type"
                ],

                "source_url": source[
                    "source_url"
                ],

                "file": str(
                    output_path.relative_to(
                        repo_root
                    )
                ),
            }

            success_count += 1

            print(
                f"✓ {slug}: "
                f"{len(models)} models",
                flush=True,
            )

        except Exception as exc:

            print(
                f"✗ {slug}: {exc}",
                file=sys.stderr,
                flush=True,
            )

            index[
                "endpoints"
            ][slug] = {
                "status": "error",

                "error": str(
                    exc
                ),

                "source_type": source[
                    "source_type"
                ],

                "source_url": source[
                    "source_url"
                ],
            }

        if index_number < total:

            if args.delay > 0:
                time.sleep(
                    args.delay
                )

    # -----------------------------------------------------------------------
    # Save index
    # -----------------------------------------------------------------------

    save_json(
        index_path,
        index,
    )

    # -----------------------------------------------------------------------
    # latest.json
    # -----------------------------------------------------------------------

    latest_path = (
        repo_root
        / "data"
        / "latest.json"
    )

    save_json(
        latest_path,
        {
            "date": date_str,
            "path": f"data/{date_str}",
        },
    )

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------

    print(
        "",
        flush=True,
    )

    print(
        f"Done: "
        f"{success_count}/{total} endpoints",
        flush=True,
    )

    print(
        f"Saved to: "
        f"data/{date_str}/",
        flush=True,
    )

    # -----------------------------------------------------------------------
    # Exit status
    # -----------------------------------------------------------------------

    if success_count < total:

        print(
            "",
            file=sys.stderr,
        )

        print(
            "One or more endpoints failed.",
            file=sys.stderr,
        )

        sys.exit(1)


if __name__ == "__main__":
    main()
