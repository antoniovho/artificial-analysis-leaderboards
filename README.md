# Artificial Analysis Leaderboards

[![Daily Fetch](https://github.com/antoniovho/artificial-analysis-leaderboards/actions/workflows/fetch.yml/badge.svg?branch=main)](https://github.com/antoniovho/artificial-analysis-leaderboards/actions/workflows/fetch.yml)

Daily snapshots of AI model benchmark and leaderboard data collected from **Artificial Analysis** and **Arena AI**.

The repository is intended to provide a historical, machine-readable dataset that can later be used for model comparisons, monitoring and **model recommendations by use case**.

---

## Sources

### Artificial Analysis

The collector uses the official Artificial Analysis API v2 with an API key.

The current Free-tier endpoints include:

```text
https://artificialanalysis.ai/api/v2/language/models/free
https://artificialanalysis.ai/api/v2/media/text-to-image/models/free
https://artificialanalysis.ai/api/v2/media/image-editing/models/free
https://artificialanalysis.ai/api/v2/media/text-to-video/models/free
https://artificialanalysis.ai/api/v2/media/image-to-video/models/free
https://artificialanalysis.ai/api/v2/media/text-to-speech/models/free
https://artificialanalysis.ai/api/v2/media/speech-to-speech/models/free
https://artificialanalysis.ai/api/v2/media/speech-to-text/models/free
https://artificialanalysis.ai/api/v2/media/text-to-video-audio/models/free
https://artificialanalysis.ai/api/v2/media/image-to-video-audio/models/free
```

The exact fields returned depend on the API tier and current Artificial Analysis schema.

See the [Artificial Analysis API documentation](https://artificialanalysis.ai/data-api/docs).

### Arena AI

Arena data is imported from the public repository:

[oolong-tea-2026/arena-ai-leaderboards](https://github.com/oolong-tea-2026/arena-ai-leaderboards)

That repository maintains daily structured snapshots of Arena AI leaderboards and exposes a public REST API without authentication. The collector uses that API rather than scraping Arena directly.

Current upstream categories include leaderboards such as:

```text
text
code
vision
document
text-to-image
image-edit
search
text-to-video
image-to-video
video-edit
```

The available categories are discovered dynamically from the upstream API, so this repository does not need to hard-code the complete Arena category list.

See the [Arena source repository](https://github.com/oolong-tea-2026/arena-ai-leaderboards).

---

## Data

| Source | Data | Destination |
|---|---|---|
| Artificial Analysis | LLM benchmarks, pricing, speed, capabilities and media Arena data available to the API tier | `data/YYYY-MM-DD/*.json` |
| Arena AI | Text, code, vision, document, image, video, search and other Arena leaderboards | `data/YYYY-MM-DD/arena/*.json` |

Artificial Analysis language-model data may contain Intelligence Index, Coding Index, Agentic Index, benchmark evaluations, pricing, performance, context window, modalities and licensing information.

Arena leaderboard entries generally contain fields such as rank, model, vendor, license, score/Elo, confidence interval and votes.

---

## Repository structure

```text
.
├── .github/
│   └── workflows/
│       └── fetch.yml
│
├── scripts/
│   ├── fetch_leaderboards.py
│   ├── fetch_arena.py
│   └── fetch_all.py
│
├── requirements.txt
│
└── data/
    ├── latest.json
    │
    ├── 2026-08-27/
    │   ├── _index.json
    │   ├── llms.json
    │   ├── text-to-image.json
    │   ├── image-editing.json
    │   ├── text-to-video.json
    │   ├── image-to-video.json
    │   └── arena/
    │       ├── _index.json
    │       ├── text.json
    │       ├── code.json
    │       ├── vision.json
    │       ├── document.json
    │       └── ...
    │
    └── ...
```

---

## Daily snapshots

Each run writes data under the UTC date on which the collector runs:

```text
data/YYYY-MM-DD/
```

The repository also maintains:

```text
data/latest.json
```

which points to the latest local snapshot.

Example:

```json
{
  "date": "2026-08-27",
  "path": "data/2026-08-27"
}
```

### Arena upstream date

Arena maintains its own `latest.json`. The upstream snapshot date is stored separately in:

```text
data/YYYY-MM-DD/arena/_index.json
```

This is important because the upstream Arena snapshot date and the local collection date are not necessarily identical.

---

## Artificial Analysis JSON format

Each Artificial Analysis endpoint file contains metadata and a `models` list.

Example:

```json
{
  "meta": {
    "endpoint": "llms",
    "source_type": "api_v2_free",
    "source_url": "https://artificialanalysis.ai/api/v2/language/models/free",
    "source_description": "Artificial Analysis language models via the Free API",
    "parser_version": "api-v2-2",
    "model_count": 621,
    "pagination": {},
    "fetched_at": "2026-08-27T05:13:00+00:00"
  },
  "models": []
}
```

The collector preserves nested `evaluations`, `pricing` and `performance` objects so new upstream fields can be retained without requiring a hard-coded parser update for every benchmark field.

---

## Arena JSON format

Arena files preserve the upstream leaderboard schema and add collection provenance to `meta`.

Example:

```json
{
  "meta": {
    "leaderboard": "text",
    "source_url": "https://arena.ai/leaderboard/text",
    "fetched_at": "2026-08-26T02:50:08+00:00",
    "model_count": 50,
    "collector_fetched_at": "2026-08-27T05:13:00+00:00",
    "collector_local_snapshot_date": "2026-08-27",
    "upstream_snapshot_date": "2026-08-26",
    "source_repository": "oolong-tea-2026/arena-ai-leaderboards",
    "source_repository_url": "https://github.com/oolong-tea-2026/arena-ai-leaderboards",
    "source_api_url": "https://api.wulong.dev/arena-ai-leaderboards/v1/leaderboard?name=text"
  },
  "models": [
    {
      "rank": 1,
      "model": "...",
      "vendor": "...",
      "license": "proprietary",
      "score": 1500,
      "ci": 5,
      "votes": 10000
    }
  ]
}
```

---

## Pagination

Artificial Analysis API v2 language and media list endpoints may return paginated responses.

The collector follows the returned pagination metadata until all pages have been fetched.

For example:

```text
page 1 → 200 models
page 2 → 200 models
page 3 → 200 models
page 4 → remaining models
```

All pages are combined into a single daily JSON file.

The Arena API returns each leaderboard as a complete leaderboard response, so Arena pagination is handled by the upstream service rather than by this repository.

---

## Partial failures

The collection process is designed to be resilient to individual endpoint failures.

For example:

```text
Artificial Analysis
✓ llms: 621 models
✗ text-to-image: 403
✗ text-to-video: 403

Arena
✓ text: 50 models
✓ code: 50 models
✓ vision: 50 models
...
```

A collector exits successfully when at least one of its own endpoints succeeds.

The combined `fetch_all.py` workflow exits successfully when **at least one collector produces data**.

Therefore:

```text
AA partially succeeds + Arena succeeds       → commit
AA fails completely + Arena succeeds         → commit
AA succeeds + Arena fails completely         → commit
AA fails completely + Arena fails completely → workflow fails
```

Failed endpoints are recorded in the corresponding `_index.json` file.

---

## Authentication

### Artificial Analysis

The Artificial Analysis API key is not stored in Git.

Set it locally with:

```bash
export ARTIFICIAL_ANALYSIS_API_KEY="YOUR_API_KEY"
```

Then run:

```bash
python3 scripts/fetch_leaderboards.py
```

### GitHub Actions

Configure this repository secret:

```text
ARTIFICIAL_ANALYSIS_API_KEY
```

The workflow injects it as an environment variable.

Never commit the API key to the repository.

### Arena

No API key is required for the public Arena snapshot API used by this collector.

---

## Local usage

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Run all collectors:

```bash
python3 scripts/fetch_all.py
```

Run only Artificial Analysis:

```bash
python3 scripts/fetch_leaderboards.py
```

Run only Arena:

```bash
python3 scripts/fetch_arena.py
```

Fetch specific Artificial Analysis endpoints:

```bash
python3 scripts/fetch_leaderboards.py --only llms text-to-image
```

Fetch specific Arena leaderboards:

```bash
python3 scripts/fetch_arena.py --only text code vision
```

---

## GitHub Actions

The repository is updated automatically every day at:

```text
05:13 UTC
```

The workflow also supports manual execution through `workflow_dispatch`.

The workflow:

1. checks out the repository;
2. installs Python dependencies;
3. fetches Artificial Analysis and Arena data;
4. writes the daily snapshot;
5. updates `data/latest.json`;
6. commits the generated data;
7. pushes the commit to `main`.

The workflow succeeds only when at least one collector produces data.

---

## Quick access

### Latest local snapshot

```bash
curl -s \
  https://raw.githubusercontent.com/antoniovho/artificial-analysis-leaderboards/main/data/latest.json
```

### Latest LLM snapshot

```bash
curl -s \
  https://raw.githubusercontent.com/antoniovho/artificial-analysis-leaderboards/main/data/YYYY-MM-DD/llms.json
```

### Latest Arena text leaderboard

```bash
curl -s \
  https://raw.githubusercontent.com/antoniovho/artificial-analysis-leaderboards/main/data/YYYY-MM-DD/arena/text.json
```

### Browse all collected data

[Browse `data/`](https://github.com/antoniovho/artificial-analysis-leaderboards/tree/main/data)

---

## Example: consuming the latest data

```python
import json
import urllib.request

BASE = (
    "https://raw.githubusercontent.com/"
    "antoniovho/artificial-analysis-leaderboards/main/data/"
)

with urllib.request.urlopen(BASE + "latest.json") as response:
    latest = json.load(response)

date = latest["date"]

with urllib.request.urlopen(BASE + f"{date}/llms.json") as response:
    llms = json.load(response)

print("Snapshot:", date)
print("LLMs:", len(llms["models"]))
```

---

## Future scope

This repository is primarily a **data ingestion and historical snapshot layer**.

A future recommendation layer can normalize models across multiple independent sources:

```text
Artificial Analysis
        +
Arena AI
        +
MTEB
        +
SWE-bench
        +
LiveBench
        +
OCR / Document AI benchmarks
        +
Other specialist benchmarks
        │
        ▼
   Model normalization
        │
        ▼
     Use-case scoring
        │
        ▼
   Top 3 recommendations
```

Potential use cases include:

```text
Chat
Coding
Data analysis
Agents
RAG
OCR
Document understanding
Embeddings
Reranking
Translation
Image generation
Video generation
Speech
```

The long-term objective is to answer:

> **What are the three best models for this particular task?**

rather than only asking which model has the highest overall score.

---

## Attribution

### Artificial Analysis

Data is provided by [Artificial Analysis](https://artificialanalysis.ai/).

Attribution is required when using data from the Artificial Analysis Free API. See the [Artificial Analysis API documentation](https://artificialanalysis.ai/data-api/docs) and applicable terms.

### Arena AI

Arena data is sourced through the public [oolong-tea-2026/arena-ai-leaderboards](https://github.com/oolong-tea-2026/arena-ai-leaderboards) repository, which states that its source code is MIT licensed and its data is sourced from Arena AI.

The collector preserves upstream source and repository information in each Arena snapshot for traceability.

---

## License

The source code in this repository is licensed under the **MIT License**.

Third-party data remains subject to the licensing and usage terms of its respective providers and source repositories.

The MIT license for this repository does not grant additional rights over Artificial Analysis or Arena data.

---

## Disclaimer

This is an independent data-collection project and is not affiliated with, sponsored by or endorsed by Artificial Analysis or Arena AI unless explicitly stated otherwise.

Upstream endpoints, schemas, rate limits, subscription requirements and data terms may change over time.

The collectors are therefore designed to fail explicitly on unexpected responses rather than silently treating invalid data as a successful snapshot.
