# Embeddable Widget & Lead-Capture Platform

A resilient, multi-tenant backend platform built with Python (FastAPI) and SQLite that allows website owners to configure embeddable lead-capture widgets, distribute them via a single JavaScript snippet, and safely process incoming public submissions.

---

## Key Features

1. **Multi-Tenant Administration**:
   - Tenant-isolated CRUD operations for widgets.
   - API key authentication via `X-API-Key` or `Bearer` tokens.
   - Cross-tenant boundaries strictly enforced.

2. **Public Asset Delivery & Caching**:
   - Versioned JavaScript bundle served at `/static/widget.v1.js` with `Cache-Control: public, max-age=86400, immutable`.
   - Public configuration endpoint at `/api/v1/public/widgets/{widget_id}/config` with `Cache-Control: public, max-age=60`.

3. **Public Submission Endpoint**:
   - Full Cross-Origin Resource Sharing (CORS) and `OPTIONS` preflight support.
   - Boundary validation for malformed JSON and missing required fields (clean 4xx responses).
   - Maximum body size check (rejects payloads over 64 KB with HTTP 413).
   - Honeypot anti-spam protection: invisible fields detect automated bots.
   - Sliding-window rate limiter per client IP returning HTTP 429 when throttled.
   - Idempotency support via `Idempotency-Key` header.

4. **Geolocation Enrichment with Fallback Chain**:
   - Resolves visitor IP address to geographical details (country, city, region).
   - Sequential provider fallback: attempts Primary Provider -> falls back to Secondary Provider on error -> degrades gracefully if all providers fail (submission always succeeds).

5. **Safe Asynchronous Side Effects**:
   - Post-submission operations (such as notification emails and webhook alerts) execute as background tasks.
   - Downstream failures in side effects are logged safely without failing the visitor's submission.

6. **Owner Analytics Dashboard**:
   - Aggregated metrics: total widgets, total submissions, 24-hour and 7-day activity, widget breakdowns, and geographic distributions.
   - Interactive web interface available at `/dashboard`.

---

## Project Structure

```
Widget_Platform/
├── app/
│   ├── api/ & routers/     # API routes (admin, public, dashboard)
│   ├── auth.py             # Tenant API key authentication & scoping
│   ├── config.py           # Application settings and environment variables
│   ├── database.py         # SQLite connection manager, WAL mode, migrations
│   ├── geo_service.py      # IP geolocation provider fallback chain
│   ├── main.py             # FastAPI entrypoint, CORS, exception handlers
│   ├── rate_limiter.py     # Thread-safe sliding-window rate limiter
│   ├── schemas.py          # Pydantic models for validation and responses
│   └── side_effects.py     # Non-blocking post-submission workers
├── customer_site/
│   └── index.html          # Demo website testing cross-origin script embedding
├── static/
│   ├── dashboard.html      # Owner management and analytics UI
│   └── widget.v1.js        # Embeddable client widget bundle
├── tests/
│   └── test_platform.py    # Test suite verifying all operational paths
├── requirements.txt        # Python package dependencies
├── seed.py                 # Seeds initial tenants, widgets, and sample leads
└── run.py                  # Server launcher
```

---

## Quickstart Guide

### 1. Install Dependencies
```bash
python -m pip install -r requirements.txt
```

### 2. Seed Database
```bash
python seed.py
```
This initializes the SQLite database (`widget_platform.db`) and prints demo credentials:
- **Tenant A (Acme Corp)**: API Key `sk_live_demo_12345` (Widget: `wgt_demo_signup`)
- **Tenant B (Globex)**: API Key `sk_live_globex_99999` (Widget: `wgt_globex_contact`)

### 3. Start the Server
```bash
python run.py
```
The server will start at `http://127.0.0.1:8000`.

### 4. Open the Owner Dashboard
Navigate to `http://127.0.0.1:8000/dashboard` in your browser. Enter `sk_live_demo_12345` to view analytics, copy embed snippets, or create new widgets.

### 5. Run the Test Suite
```bash
python -m pytest -v
```
All tests verify boundary validation, throttling, honeypot traps, multi-tenant scoping, fallback geolocation, and CORS headers.
