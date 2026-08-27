#!/usr/bin/env python3

"""
Fetch the latest Arena AI leaderboard snapshot directly from GitHub.

Source repository:
    https://github.com/oolong-tea-2026/arena-ai-leaderboards

This collector does NOT use the api.wulong.dev API.

It:
    1. Reads the upstream data/latest.json from GitHub.
    2. Resolves the latest snapshot directory.
    3. Downloads the available leaderboard JSON files directly from
       raw.githubusercontent.com.
    4. Saves them under:
           data/YYYY-MM-DD/arena/
    5. Writes metadata describing the source.
    6. Returns exit code 0 if at least one leaderboard is collected.

Usage:
    python3 scripts/fetch_arena.py

Only selected leaderboards:
    python3 scripts/fetch_arena.py --only text code vision
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

UPSTREAM_OWNER = "oolong-tea-2026"
UPSTREAM_REPO = "arena-ai-leaderboards"
UPSTREAM_BRANCH = "main"

RAW_BASE_URL = (
    f"https://raw.githubusercontent.com/"
    f"{UPSTREAM_OWNER}/"
    f"{UPSTREAM_REPO}/"
    f"{UPSTREAM_BRANCH}"
)

LATEST_URL = f"{RAW_BASE_URL}/data/latest.json"

USER_AGENT = (
    "artificial-analysis-leaderboards/2.0 "
    "(Arena snapshot collector)"
)

PARSER_VERSION = "arena-github-v2"


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


class ArenaFetchError(RuntimeError):
    """Raised when Arena upstream data cannot be fetched."""


def http_get(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=60,
        ) as response:
            return response.read()

    except urllib.error.HTTPError as exc:
        body = exc.read().decode(
            "utf-8",
            "ignore",
        )

        raise ArenaFetchError(
            f"HTTP {exc.code} from Arena GitHub source\n"
            f"URL: {url}\n"
            f"Response: {body[:2000]}"
        ) from exc

    except urllib.error.URLError as exc:
        raise ArenaFetchError(
            f"Network error fetching Arena source\n"
            f"URL: {url}\n"
            f"Error: {exc}"
        ) from exc


def fetch_json(url: str) -> dict[str, Any]:
    body = http_get(url)

    try:
        data = json.loads(
            body.decode(
                "utf-8",
                "ignore",
            )
        )
    except json.JSONDecodeError as exc:
        raise ArenaFetchError(
            f"Invalid JSON returned by Arena source\n"
            f"URL: {url}"
        ) from exc

    if not isinstance(data, dict):
        raise ArenaFetchError(
            f"Unexpected JSON structure from Arena source\n"
            f"URL: {url}"
        )

    return data


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def load_json(
    path: Path,
) -> dict[str, Any]:

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


# ---------------------------------------------------------------------------
# Latest snapshot
# ---------------------------------------------------------------------------


def get_latest_snapshot() -> tuple[str, str]:
    latest = fetch_json(LATEST_URL)

    date = latest.get("date")
    path = latest.get("path")

    if not isinstance(date, str):
        raise ArenaFetchError(
            "Arena latest.json does not contain a valid 'date'"
        )

    if not isinstance(path, str) or not path:
        raise ArenaFetchError(
            "Arena latest.json does not contain a valid 'path'"
        )

    # Arena latest.json exposes the snapshot folder name,
    # e.g. "2026-08-26". The actual repository path is:
    # data/2026-08-26/
    snapshot_path = f"data/{path}"

    return date, snapshot_path


# ---------------------------------------------------------------------------
# Leaderboard discovery
# ---------------------------------------------------------------------------


def get_available_leaderboards(
    snapshot_path: str,
) -> list[str]:
    """
    Discover JSON files in the upstream snapshot directory.

    Uses the GitHub Contents API only for directory listing.

    This is NOT api.wulong.dev and does not consume their Cloudflare
    Workers quota.
    """

    api_url = (
        "https://api.github.com/repos/"
        f"{UPSTREAM_OWNER}/"
        f"{UPSTREAM_REPO}/contents/"
        f"{snapshot_path}"
        f"?ref={UPSTREAM_BRANCH}"
    )

    request = urllib.request.Request(
        api_url,
        method="GET",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
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

    except urllib.error.HTTPError as exc:
        body = exc.read().decode(
            "utf-8",
            "ignore",
        )

        raise ArenaFetchError(
            f"HTTP {exc.code} while listing Arena snapshot\n"
            f"URL: {api_url}\n"
            f"Response: {body[:2000]}"
        ) from exc

    except urllib.error.URLError as exc:
        raise ArenaFetchError(
            f"Network error listing Arena snapshot\n"
            f"URL: {api_url}\n"
            f"Error: {exc}"
        ) from exc

    try:
        entries = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ArenaFetchError(
            "GitHub Contents API returned invalid JSON"
        ) from exc

    if not isinstance(entries, list):
        raise ArenaFetchError(
            "Unexpected GitHub Contents API response"
        )

    leaderboard_names: list[str] = []

    for entry in entries:

        if not isinstance(entry, dict):
            continue

        if entry.get("type") != "file":
            continue

        name = entry.get("name")

        if not isinstance(name, str):
            continue

        if not name.endswith(".json"):
            continue

        if name in {
            "latest.json",
            "_index.json",
        }:
            continue

        leaderboard_names.append(
            name[:-5]
        )

    return sorted(
        leaderboard_names
    )


# ---------------------------------------------------------------------------
# Download leaderboard
# ---------------------------------------------------------------------------


def fetch_leaderboard(
    snapshot_path: str,
    leaderboard: str,
) -> dict[str, Any]:

    filename = f"{leaderboard}.json"

    url = (
        f"{RAW_BASE_URL}/"
        f"{snapshot_path}/"
        f"{filename}"
    )

    print(
        f"  Fetching {leaderboard}...",
        flush=True,
    )

    data = fetch_json(url)

    if not isinstance(data, dict):
        raise ArenaFetchError(
            f"Unexpected leaderboard format: {leaderboard}"
        )

    return data


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Fetch latest Arena AI leaderboard "
            "snapshot directly from GitHub"
        )
    )

    parser.add_argument(
        "--only",
        nargs="*",
        help=(
            "Only fetch selected leaderboard names. "
            "Example: --only text code vision"
        ),
    )

    args = parser.parse_args()

    script_dir = Path(
        __file__
    ).resolve().parent

    repo_root = script_dir.parent

    # -----------------------------------------------------------------------
    # Resolve latest upstream snapshot
    # -----------------------------------------------------------------------

    print(
        "Reading Arena upstream latest.json...",
        flush=True,
    )

    upstream_date, snapshot_path = (
        get_latest_snapshot()
    )

    print(
        f"Arena upstream latest snapshot: "
        f"{upstream_date}",
        flush=True,
    )

    # -----------------------------------------------------------------------
    # Discover available leaderboards
    # -----------------------------------------------------------------------

    print(
        "Discovering available Arena leaderboards...",
        flush=True,
    )

    try:
        available = get_available_leaderboards(
            snapshot_path
        )
    except Exception as exc:
        print(
            f"✗ Arena leaderboard listing: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    if not available:
        print(
            "✗ No Arena leaderboard JSON files found.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(
        f"Found {len(available)} leaderboards.",
        flush=True,
    )

    # -----------------------------------------------------------------------
    # Filter requested leaderboards
    # -----------------------------------------------------------------------

    if args.only:

        requested = set(
            args.only
        )

        unknown = sorted(
            requested - set(available)
        )

        if unknown:
            print(
                "WARNING: requested leaderboards "
                "were not found upstream:",
                ", ".join(unknown),
                file=sys.stderr,
            )

        leaderboards = [
            name
            for name in available
            if name in requested
        ]

    else:
        leaderboards = available

    if not leaderboards:
        print(
            "✗ No requested Arena leaderboards are available.",
            file=sys.stderr,
        )
        sys.exit(1)

    # -----------------------------------------------------------------------
    # Local snapshot date
    # -----------------------------------------------------------------------

    now = datetime.now(
        timezone.utc
    )

    local_date = now.strftime(
        "%Y-%m-%d"
    )

    fetched_at = now.isoformat()

    # We use the date of the upstream snapshot for the directory so that
    # local data corresponds exactly to the Arena source snapshot.
    day_dir = (
        repo_root
        / "data"
        / upstream_date
        / "arena"
    )

    day_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # -----------------------------------------------------------------------
    # Collect
    # -----------------------------------------------------------------------

    successful = 0
    failed = 0

    endpoint_status: dict[str, Any] = {}

    for leaderboard in leaderboards:

        print(
            f"Fetching {leaderboard}...",
            flush=True,
        )

        try:

            data = fetch_leaderboard(
                snapshot_path,
                leaderboard,
            )

            output = {
                "meta": {
                    "endpoint": leaderboard,

                    "source_type": (
                        "github_upstream_snapshot"
                    ),

                    "source_repository": (
                        f"{UPSTREAM_OWNER}/"
                        f"{UPSTREAM_REPO}"
                    ),

                    "source_snapshot_date": (
                        upstream_date
                    ),

                    "source_snapshot_path": (
                        snapshot_path
                    ),

                    "source_url": (
                        f"{RAW_BASE_URL}/"
                        f"{snapshot_path}/"
                        f"{leaderboard}.json"
                    ),

                    "fetched_at": fetched_at,

                    "collector_date": local_date,

                    "parser_version": (
                        PARSER_VERSION
                    ),
                },

                "data": data,
            }

            output_path = (
                day_dir
                / f"{leaderboard}.json"
            )

            save_json(
                output_path,
                output,
            )

            model_count = None

            if isinstance(
                data.get("models"),
                list,
            ):
                model_count = len(
                    data["models"]
                )

            elif isinstance(
                data.get("data"),
                list,
            ):
                model_count = len(
                    data["data"]
                )

            endpoint_status[
                leaderboard
            ] = {
                "status": "success",
                "model_count": model_count,
                "file": str(
                    output_path.relative_to(
                        repo_root
                    )
                ),
            }

            successful += 1

            if model_count is None:
                print(
                    f"  ✓ {leaderboard}",
                    flush=True,
                )
            else:
                print(
                    f"  ✓ {leaderboard}: "
                    f"{model_count} models",
                    flush=True,
                )

        except Exception as exc:

            failed += 1

            endpoint_status[
                leaderboard
            ] = {
                "status": "error",
                "error": str(exc),
            }

            print(
                f"  ✗ {leaderboard}: {exc}",
                file=sys.stderr,
                flush=True,
            )

    # -----------------------------------------------------------------------
    # Save Arena index
    # -----------------------------------------------------------------------

    index = {
        "source_repository": (
            f"{UPSTREAM_OWNER}/{UPSTREAM_REPO}"
        ),

        "source_repository_url": (
            f"https://github.com/"
            f"{UPSTREAM_OWNER}/"
            f"{UPSTREAM_REPO}"
        ),

        "source_snapshot_date": upstream_date,

        "source_snapshot_path": snapshot_path,

        "collector_date": local_date,

        "fetched_at": fetched_at,

        "parser_version": PARSER_VERSION,

        "available_leaderboards": available,

        "requested_leaderboards": (
            leaderboards
        ),

        "successful_count": successful,

        "failed_count": failed,

        "endpoints": endpoint_status,
    }

    index_path = (
        day_dir
        / "_index.json"
    )

    save_json(
        index_path,
        index,
    )

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------

    print()
    print(
        "Arena collection complete.",
        flush=True,
    )

    print(
        f"Successful: {successful}/{len(leaderboards)}",
        flush=True,
    )

    print(
        f"Failed:     {failed}/{len(leaderboards)}",
        flush=True,
    )

    print(
        f"Saved to:   {day_dir.relative_to(repo_root)}",
        flush=True,
    )

    # Important:
    # At least one successful leaderboard means success.
    if successful == 0:
        print(
            "",
            file=sys.stderr,
        )

        print(
            "All Arena leaderboards failed.",
            file=sys.stderr,
        )

        sys.exit(1)

    print(
        "At least one Arena leaderboard succeeded.",
        flush=True,
    )

    sys.exit(0)


if __name__ == "__main__":
    main()
