# Artificial Analysis Leaderboards

[![Daily Fetch](https://github.com/antoniovho/artificial-analysis-leaderboards/actions/workflows/fetch.yml/badge.svg)](https://github.com/antoniovho/artificial-analysis-leaderboards/actions/workflows/fetch.yml)

Daily snapshots of [Artificial Analysis](https://artificialanalysis.ai/) model and leaderboard data collected through the **Artificial Analysis API v2**.

The repository is intended to provide a historical, machine-readable dataset of AI model evaluations, rankings, pricing, performance and capabilities.

The data can later be used to build model comparison tools, monitoring systems and **model recommendations by use case**.

---

## Data

The collector currently retrieves the following Artificial Analysis datasets:

| Endpoint | Description | Main data |
|----------|-------------|-----------|
| `llms` | Language models | Intelligence Index, Coding Index, Agentic Index, benchmark evaluations, pricing, performance, context window and capabilities |
| `text-to-image` | Text-to-image Arena | Elo, confidence interval and model metadata |
| `text-to-video` | Text-to-video Arena | Elo, confidence interval and model metadata |
| `image-to-video` | Image-to-video Arena | Elo, confidence interval and model metadata |

The exact fields available depend on the Artificial Analysis API tier.

The Free API provides a subset of the data available through the full Pro/API plans.

See the [Artificial Analysis API documentation](https://artificialanalysis.ai/data-api/docs) for the current schema and access levels.

---

## API

The collector uses the official Artificial Analysis API v2:

```text
https://artificialanalysis.ai/api/v2
```

### Language models

The Free language-model endpoint is:

```text
/api/v2/language/models/free
```

### Media models

Free media endpoints use the corresponding `/free` routes, for example:

```text
https://artificialanalysis.ai/api/v2/media/text-to-image/models/free
https://artificialanalysis.ai/api/v2/media/text-to-video/models/free
https://artificialanalysis.ai/api/v2/media/image-to-video/models/free
```

All requests authenticate using the:

```text
x-api-key
```

HTTP header.

See:

- [Artificial Analysis API documentation](https://artificialanalysis.ai/data-api/docs)
- [Artificial Analysis API reference](https://artificialanalysis.ai/api-reference)

---

## Authentication

The API key is **never stored in the repository**.

### Local execution

Set the API key as an environment variable:

```bash
export ARTIFICIAL_ANALYSIS_API_KEY="YOUR_API_KEY"
```

Then run:

```bash
python3 scripts/fetch_leaderboards.py
```

The script reads the key from:

```text
ARTIFICIAL_ANALYSIS_API_KEY
```

### GitHub Actions

Configure the following repository secret:

```text
ARTIFICIAL_ANALYSIS_API_KEY
```

The workflow injects the secret into the fetch job as an environment variable.

The secret is not written to disk, committed to Git or included in generated JSON files.

**Never commit your API key to Git.**

---

## Repository structure

```text
.
├── .github/
│   └── workflows/
│       └── fetch.yml
│
├── scripts/
│   └── fetch_leaderboards.py
│
└── data/
    ├── latest.json
    │
    ├── 2026-08-27/
    │   ├── _index.json
    │   ├── llms.json
    │   ├── text-to-image.json
    │   ├── text-to-video.json
    │   └── image-to-video.json
    │
    ├── 2026-08-28/
    │   └── ...
    │
    └── ...
```

---

## Daily snapshots

Every successful run creates or updates a directory using the current UTC date:

```text
data/YYYY-MM-DD/
```

For example:

```text
data/2026-08-27/
```

The snapshot contains one JSON file per configured endpoint.

```text
data/2026-08-27/
├── _index.json
├── llms.json
├── text-to-image.json
├── text-to-video.json
└── image-to-video.json
```

The repository also contains:

```text
data/latest.json
```

This is a lightweight pointer to the latest snapshot.

Example:

```json
{
  "date": "2026-08-27",
  "path": "data/2026-08-27"
}
```

This makes it possible for downstream applications to discover the latest dataset without knowing the date in advance.

---

## JSON format

Each endpoint file contains metadata and model data.

Example:

```json
{
  "meta": {
    "endpoint": "llms",
    "source_type": "api_v2",
    "source_url": "https://artificialanalysis.ai/api/v2/language/models/free",
    "source_description": "Artificial Analysis language models via the Free API",
    "parser_version": "api-v2-1",
    "model_count": 621,
    "pagination": {}
  },
  "models": []
}
```

### Metadata

The `meta` object contains:

| Field | Description |
|-------|-------------|
| `endpoint` | Logical dataset name |
| `source_type` | Source type used by the collector |
| `source_url` | Artificial Analysis API endpoint |
| `source_description` | Human-readable source description |
| `parser_version` | Version of the collector/parser |
| `model_count` | Number of models collected |
| `pagination` | Pagination information returned by the API |
| `fetched_at` | UTC timestamp when the data was retrieved |

---

## Language model data

The language-model dataset contains a normalized representation of the API response.

A model can contain information such as:

```text
id
name
slug
release_date
reasoning_model

creator
    id
    name
    country

evaluations
    artificial_analysis_intelligence_index
    artificial_analysis_coding_index
    artificial_analysis_agentic_index
    ...
    
pricing
    ...

performance
    ...

context_window_tokens

parameters
    total
    active

modalities
    input
    output

licensing
    ...

huggingface_url
openrouter_api_id
```

The collector deliberately preserves nested evaluation, pricing and performance objects rather than maintaining a hard-coded list of every benchmark field.

This means that when Artificial Analysis adds new fields to an API response, the snapshot can retain them without requiring an immediate parser update.

---

## Pagination

The API v2 returns paginated datasets.

For example:

```json
{
  "pagination": {
    "page": 1,
    "page_size": 200,
    "total_pages": 4,
    "has_more": true
  }
}
```

The collector automatically requests all pages until:

```text
has_more = false
```

For example:

```text
page 1 → 200 models
page 2 → 200 models
page 3 → 200 models
page 4 → 21 models

total → 621 models
```

All pages are combined into a single daily JSON file.

---

## Partial failures

The collector is intentionally designed to tolerate individual endpoint failures.

For example:

```text
✓ llms: 621 models
✗ text-to-image: 403
✗ text-to-video: 403
✓ image-to-video: 42 models
```

In this situation:

- successful endpoint data is saved;
- failed endpoints are recorded in `_index.json`;
- `latest.json` is updated;
- GitHub Actions continues to the commit step.

The process only exits with an error when **all configured endpoints fail**.

This prevents a temporary API problem or a subscription-specific endpoint restriction from preventing the collection of the remaining datasets.

Failed endpoints are recorded in `_index.json`.

---

## Error reporting

The collector reports the actual API response when an endpoint fails.

For example:

```text
HTTP 403 from Artificial Analysis API
URL: https://artificialanalysis.ai/...
Response: {"error":"Text-to-image models list requires a Pro subscription"}
```

This makes it easier to distinguish between:

- invalid API keys;
- unavailable endpoints;
- subscription restrictions;
- rate limits;
- malformed requests;
- network errors;
- unexpected API changes.

---

## Local usage

### Fetch all configured endpoints

```bash
python3 scripts/fetch_leaderboards.py
```

### Fetch only LLMs

```bash
python3 scripts/fetch_leaderboards.py --only llms
```

### Fetch multiple endpoints

```bash
python3 scripts/fetch_leaderboards.py --only llms text-to-image
```

### Change request delay

```bash
python3 scripts/fetch_leaderboards.py --delay 1
```

The delay is applied between paginated requests and between configured endpoints.

---

## GitHub Actions

The data is collected automatically using GitHub Actions.

The scheduled workflow runs daily at:

```text
05:13 UTC
```

The workflow is also configured with `workflow_dispatch`, which allows a manual run from the GitHub Actions interface.

### Workflow process

Each run performs the following steps:

```text
GitHub Actions
      │
      ▼
Checkout repository
      │
      ▼
Setup Python 3.12
      │
      ▼
Load ARTIFICIAL_ANALYSIS_API_KEY
      │
      ▼
Fetch API data
      │
      ▼
Normalize response
      │
      ▼
Save data/YYYY-MM-DD/
      │
      ▼
Update data/latest.json
      │
      ▼
git add data/
      │
      ▼
Commit changes
      │
      ▼
Push to main
```

The workflow therefore turns the repository itself into a continuously updated historical dataset.

---

## Historical data

Because every daily snapshot is committed to Git, the repository automatically provides historical data.

This makes it possible to answer questions such as:

- Which models were available on a particular date?
- How did a model's benchmark scores change?
- When did a new model first appear?
- How quickly did a model move through a leaderboard?
- Which models disappeared or became deprecated?
- How have model prices changed over time?

Git history can be used alongside the JSON snapshots for change analysis.

---

## Quick access

### Latest snapshot pointer

```bash
curl -s \
  https://raw.githubusercontent.com/oolong-tea-2026/artificial-analysis-leaderboards/main/data/latest.json
```

### Latest LLM snapshot

Replace `YYYY-MM-DD` with the date returned by `latest.json`:

```bash
curl -s \
  https://raw.githubusercontent.com/oolong-tea-2026/artificial-analysis-leaderboards/main/data/YYYY-MM-DD/llms.json
```

### Latest text-to-image snapshot

```bash
curl -s \
  https://raw.githubusercontent.com/oolong-tea-2026/artificial-analysis-leaderboards/main/data/YYYY-MM-DD/text-to-image.json
```

### Latest text-to-video snapshot

```bash
curl -s \
  https://raw.githubusercontent.com/oolong-tea-2026/artificial-analysis-leaderboards/main/data/YYYY-MM-DD/text-to-video.json
```

### Browse the dataset

[Browse `data/` on GitHub](https://github.com/oolong-tea-2026/artificial-analysis-leaderboards/tree/main/data)

---

## Example: loading the dataset in Python

```python
import json
import urllib.request

LATEST_URL = (
    "https://raw.githubusercontent.com/"
    "oolong-tea-2026/"
    "artificial-analysis-leaderboards/"
    "main/data/latest.json"
)

with urllib.request.urlopen(LATEST_URL) as response:
    latest = json.load(response)

date = latest["date"]

llms_url = (
    "https://raw.githubusercontent.com/"
    "oolong-tea-2026/"
    "artificial-analysis-leaderboards/"
    f"main/data/{date}/llms.json"
)

with urllib.request.urlopen(llms_url) as response:
    data = json.load(response)

print("Snapshot date:", date)
print("Models:", len(data["models"]))

for model in data["models"][:10]:
    print(model["name"])
```

---

## Why this repository exists

Artificial Analysis provides a valuable collection of model evaluations, leaderboards and performance measurements.

This repository adds a simple but useful layer:

```text
Artificial Analysis API
        │
        ▼
Daily snapshots
        │
        ▼
Historical machine-readable dataset
        │
        ▼
Downstream analysis
```

The goal is **not** to reproduce the Artificial Analysis website.

The goal is to maintain a continuously updated data layer that can be consumed by other applications.

---

## Future scope

The current repository focuses on collecting Artificial Analysis data.

A future recommendation layer can combine this dataset with independent benchmarks and leaderboards, for example:

```text
Artificial Analysis
        +
Chatbot Arena
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

The long-term objective is to answer questions such as:

```text
"What are the best 3 models for this particular task?"
```

rather than simply:

```text
"What is the #1 model overall?"
```

This distinction is important because the best model for one workload may not be the best model for another when quality, cost, latency, context, modalities and specialized benchmark performance are taken into account.

---

## Attribution

Data is provided by [Artificial Analysis](https://artificialanalysis.ai/).

Please provide visible attribution to Artificial Analysis when displaying or reusing the data, according to the applicable API terms.

Useful references:

- [Artificial Analysis](https://artificialanalysis.ai/)
- [Artificial Analysis API documentation](https://artificialanalysis.ai/data-api/docs)
- [Artificial Analysis API reference](https://artificialanalysis.ai/api-reference)
- [Artificial Analysis methodology](https://artificialanalysis.ai/methodology)
- [Artificial Analysis Terms of Use](https://artificialanalysis.ai/terms)

---

## License

The source code in this repository is licensed under the **MIT License**.

The data collected from Artificial Analysis is third-party data and remains subject to the applicable Artificial Analysis API terms, licenses and usage restrictions.

The MIT license applies to the repository's source code and does not grant additional rights to third-party data.

---

## Disclaimer

This repository is an independent data-collection project.

It is not affiliated with, sponsored by or endorsed by Artificial Analysis unless explicitly stated otherwise.

API availability, endpoint names, schemas, rate limits, subscription requirements and data licensing may change over time.

The collector is therefore versioned and designed to fail explicitly when the upstream API changes rather than silently treating unexpected responses as valid data.
