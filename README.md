# Additional Asset

Independent **Azure Functions (Python v2)** service that generates asset fields from two photos, then **fetches** category / subcategory / make-model (and related ids/names) from **Pinecone**. It never invents master-data rows — classification fields come from the best-fit Pinecone candidate (or stay null).

| | |
|---|---|
| **Version** | `2.0.0` (`additional_asset.__version__`) |
| **Runtime** | Python **≥ 3.11**, Azure Functions worker |
| **Models** | Gemini (vision + text + embeddings) via `google-genai` |
| **Vector store** | Pinecone (customer-scoped master data) |
| **Barcode** | `zxing-cpp` (optional; can be disabled) |
| **Sibling UI** | `../AA_Frontend/` (static HTML/CSS/JS client) |

Prompts and behaviour are ported from `validation-ai-backend-preprod-updates-oct21` (vision, blind view, barcode, condition, Pinecone selection).

---

## Pipeline

1. Parse **multipart** (image files) or **JSON** (base64) — auto-detected from `Content-Type` / files
2. Image prepare (resize → JPEG; edges from `ASSET_IMAGE_MAX_EDGE` / `BARCODE_IMAGE_MAX_EDGE`)
3. **Pixel gate** (`BLANK_IMAGE_GATE_ENABLED`; when off → skip)
4. **Phase 1 routing**
   - `PHASE1_CONTENT_ROUTE_ENABLED=true`: skip blind view; **zxing (barcode slot only) ∥ Phase 1** in parallel; content-route prompt (`phase1_unified_content_route.md`)
   - `PHASE1_CONTENT_ROUTE_ENABLED=false` (legacy):
     - `BLIND_VIEW_ENABLED=true` (default): blind view ×2 → slot swap → zxing tag-first → Phase 1 + SLOT NOTE
     - `BLIND_VIEW_ENABLED=false`: skip blind view; upload slot order; same Phase 1 prompts
5. Phase 1 Gemini call: analysis, name, description, condition, tag (vision)
6. Pinecone query when `INCLUDE_PINECONE_LOOKUP=true`:
   - Always filter by `customerid`
   - Add `categoryid` / `assetclassid` metadata filters only when the client sends them
   - Embed search text from name + description + truncated image analysis (`EMBEDDING_MODEL_NAME`)
7. Selection LLM (name + description) → Python joins ids/names from the chosen candidate row
8. HTTP response mapped to **PascalCase** business field names (`to_external_response`)
9. Structured step logs every phase; optional file mirror under `debug/<request_id>.jsonl`

**Timeout:** `host.json` → `functionTimeout` = **2 minutes** (clients should allow ≥ 120 s).

---

## API

Base route prefix: `/api` (`host.json`).

### `POST /api/additional_asset`

Auth level: **anonymous** (protect at the gateway / Function App level in production).

| Field | Required | Notes |
|-------|----------|--------|
| `assetimage` / `AssetImage` | yes | File (multipart) or base64 / data-URL (JSON) |
| `barcodeimage` / `BarcodeImage` | yes | Tag / barcode photo |
| `customerid` / `CustomerId` | yes | Positive integer |
| `categoryid` / `CategoryId` | no | Scoped Pinecone filter when set |
| `assetclassid` / `AssetClassId` | no | Scoped Pinecone filter when set |

**Multipart** — form fields as above (lowercase names recommended).  
**JSON example:**

```json
{
  "AssetImage": "<base64 or data:image/...;base64,...>",
  "BarcodeImage": "<base64>",
  "CustomerId": 123,
  "CategoryId": 456,
  "AssetClassId": 789
}
```

Transport can be hard-disabled with `ADDITIONAL_ASSET_ACCEPT_MULTIPART` / `ADDITIONAL_ASSET_ACCEPT_JSON`.

**Status codes**

| Code | When |
|------|------|
| `200` | Success (including soft failures: null master-data / partial tag) |
| `400` | Payload validation, or pipeline `IMAGE_*` errors |
| `502` | Phase 1 hard failure (`PHASE1_*`) |
| `500` | Unhandled server error |

**Response keys (external):**  
`ImageAnalysis`, `AssetName`, `Description`, `AssetClassName`, `MakeModel`, `CategoryName`, `SubCategoryName`, `MakeModelId`, `CategoryId`, `CustomerId`, `AssetClassId`, `SubCategoryId`, `AssetCondition`, `TagNumber`, plus `request_id`, `llm_provider`, `timings_ms`, `llm_usage`, `error`.

- `AssetCondition` — full condition object (grade, scores, summary, damage_items, …).
- `TagNumber` — `{ decodedtagnumber, detectedtagnumber, tagnumbersource }` (`decoded` | `vision` | `NA`).
- Optional input IDs are **echoed** when provided; otherwise `CategoryId` / `AssetClassId` (and names) come from the best-fit Pinecone subcategory row. If no subcategory is selected, recommended master-data fields are null (user-provided IDs still echo).

### `GET /api/health`

Returns service flags used by the frontend health pill:

```json
{
  "status": "healthy",
  "service": "additional-asset",
  "model_active": "...",
  "text_model": "...",
  "pinecone_lookup": true,
  "pixel_gate": true,
  "phase1_content_route": false,
  "blind_view": true,
  "accept_multipart": true,
  "accept_json": true,
  "timestamp": "..."
}
```

---

## Local setup

Prerequisites: Python 3.11+, [Azure Functions Core Tools](https://learn.microsoft.com/azure/azure-functions/functions-run-local), and (optional) Azurite if you use real storage bindings — this app only needs `AzureWebJobsStorage` for the host.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -r dev-requirements.txt
copy local.settings.sample.json local.settings.json
# fill GEMINI_API_KEY, PINECONE_API_KEY, PINECONE_INDEX_NAME
func start
```

For the sibling frontend (`AA_Frontend`) calling from `file://` or another origin, enable CORS:

```bash
func start --cors "*"
```

Or add a `Host` block beside `Values` in `local.settings.json`:

```json
"Host": { "LocalHttpPort": 7071, "CORS": "*" }
```

### Tests & lint

```bash
pytest
ruff check .
```

`pyproject.toml` configures pytest (`testpaths = tests`, `pythonpath = .`) and ruff (line length 119).

---

## Key environment variables

| Variable | Default | Notes |
|----------|---------|-------|
| `GEMINI_API_KEY` | — | **Required** for live calls |
| `GEMINI_USE` | `true` | Master switch for Gemini |
| `GEMINI_MODEL_NAME` | `gemini-3.5-flash-lite` | Vision + unified Phase 1 |
| `GEMINI_TEXT_MODEL_NAME` | `gemini-3.5-flash-lite` | Pinecone selection |
| `GEMINI_CALL_TIMEOUT_SEC` | `30` | Per LLM call |
| `GEMINI_MAX_OUTPUT_TOKENS` | `2000` | Cap for larger prompts |
| `GEMINI_DEFAULT_OUTPUT_TOKENS` | `500` | Default generation budget |
| `ASSET_IMAGE_MAX_EDGE` | `896` | Longest edge after prepare |
| `BARCODE_IMAGE_MAX_EDGE` | `768` | Longest edge after prepare |
| `IMAGE_JPEG_QUALITY` | `80` | Prepare quality |
| `BLANK_IMAGE_GATE_ENABLED` | `true` | Pixel gate on/off |
| `PHASE1_CONTENT_ROUTE_ENABLED` | `false` | `true` = content-route Phase 1; zxing ∥ Phase1 |
| `BLIND_VIEW_ENABLED` | `true` | Legacy only; ignored when content-route is on |
| `CONDITION_DETAIL_LEVEL` | `minimal` | Condition prompt detail |
| `PHASE2_IMAGE_ANALYSIS_MAX_CHARS` | `350` | Truncation into Pinecone search text |
| `PROMPT_HOT_RELOAD` | `false` | Reload `.md` prompts each call (dev) |
| `PROMPT_CACHE_HOIST` | `true` | Hoist `[[VARCTX_*]]` blocks for cache friendliness |
| `EMBEDDING_MODEL_NAME` | `gemini-embedding-001` | Pinecone query embedding |
| `EMBEDDING_DIMENSION` | `768` | Must match index |
| `PINECONE_API_KEY` | — | **Required** when lookup enabled |
| `PINECONE_INDEX_NAME` | — | **Required** when lookup enabled |
| `INCLUDE_PINECONE_LOOKUP` | `true` | If false → classification fields null |
| `PINECONE_TOP_K` | `10` | Candidate count |
| `PINECONE_ASSET_CLASS_SCOPE_ENABLED` | `true` | Apply `AssetClassId` filter when provided |
| `PINECONE_CATEGORY_SCOPE_ENABLED` | `true` | Retained for compatibility |
| `BARCODE_DECODE_ENABLED` | `true` | zxing path on/off |
| `ADDITIONAL_ASSET_ACCEPT_MULTIPART` | `true` | Hard-disable multipart |
| `ADDITIONAL_ASSET_ACCEPT_JSON` | `true` | Hard-disable JSON |
| `ADDITIONAL_ASSET_LOG_CANDIDATES` | `true` | Log Pinecone candidate list |
| `LOG_LEVEL` | `INFO` | Root log level |
| `DEBUG_LOG_TO_FILE` | `true` | Mirror step logs to `debug/<request_id>.jsonl` |
| `DEBUG_LOG_DIR` | `debug` | Directory for per-request debug logs |

Response also includes `timings_ms` (per-phase + total) and `llm_usage` (totals + `by_phase`, including embedding).

See `local.settings.sample.json` for the full template used locally.

---

## Layout

```
function_app.py              # HTTP routes: additional_asset, health
host.json                    # timeout, /api prefix, logging
requirements.txt             # production deps (Azure install)
dev-requirements.txt         # pytest, pytest-asyncio, pytest-cov, ruff
pyproject.toml               # package metadata, ruff, pytest, coverage
local.settings.sample.json   # env template (commit this)
local.settings.json          # secrets (gitignored)
.funcignore                  # publish exclude — must NOT strip prompts/md
.gitignore

additional_asset/
  __init__.py                # version 2.0.0
  core/                      # config, models (request + PascalCase mapping)
  prompts/
    loader.py, builders.py
    md/                      # REQUIRED at runtime — shipped with the Function App
  services/                  # pipeline, gemini, image, view_classifier,
                             # barcode_decode, pinecone, condition, tag_merge
  utils/                     # logging, token usage, helpers, vision_type_filter

tests/                       # unit tests (excluded from Azure publish)
debug/                       # local step-log mirrors (gitignored)
```

### Important ignore rules

| File | Role |
|------|------|
| `.gitignore` | Keeps secrets (`local.settings.json`), `.venv/`, `debug/`, caches out of git |
| `.funcignore` | Keeps the same local/dev noise out of **Azure publish**, while **keeping** `additional_asset/prompts/md/*.md` |

Never add a blanket `*.md` to `.funcignore` — the service loads every Phase 1 / condition / selection prompt from those files.

---

## Deploy notes

1. Set App Settings to match `local.settings.sample.json` (at least `GEMINI_*`, `PINECONE_*`, feature flags you care about).
2. Publish with Azure Functions Core Tools / CI so `requirements.txt` is used for remote build.
3. Confirm the published package contains `additional_asset/prompts/md/`.
4. Enable CORS on the Function App for any browser origin that hosts `AA_Frontend`.
