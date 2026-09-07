# Price-history perf gate

Falsifiable check that says **"query-time aggregation is fast enough — don't open R036 (materialized `part_price_summary`)."** If the gate misses, R036 opens per [D004](../../../.gsd/DECISIONS.md). This is the perf bar promised by [R019](../../../.gsd/REQUIREMENTS.md).

## What it tests

Two read endpoints landed in M002/S05:

| Endpoint | Method | p95 budget | Notes |
| --- | --- | --- | --- |
| `/api/parts/{id}/price-history?window=90d` | GET | < 200 ms | Single-part aggregate; sparkline render path |
| `/api/parts/price-history` | POST | < 500 ms | Batch (1–100 IDs); page-load summary. Requires auth — set `PERF_BEARER_TOKEN` |

Plus: error rate must equal **0** across both endpoints.

## How to run

Requires a live uvicorn server on `localhost:8000` and sample data loaded.

`POST /api/parts/price-history` takes `get_current_user`, so the gate needs an
access token for that half of the run. Without `PERF_BEARER_TOKEN` the POST
samples all come back 401 and the run fails on error rate rather than latency.
Mint one against the target environment and export it:

```bash
export PERF_BEARER_TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/token \
  -d "username=<user>&password=<password>" | python -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
```

```bash
# 1. Start the backend in another terminal
cd backend && uvicorn app.main:app --port 8000

# 2. Seed sample data (idempotent; skip if already done)
# seed data through the API or the repositories in app/db/dynamo/ (there is no SQL sample-data script any more)

# 3. Run the gate
bash backend/scripts/perf/run_price_history_loadtest.sh
```

The script:

1. Pings `/health` to confirm the server is up.
2. Queries the DB for the top 500 parts by observation count and writes them to `backend/.perf-runs/part-id-pool.json`.
3. Spawns locust headless: `--users 50 --spawn-rate 10 --run-time 60s` against the two endpoints (4:1 GET:POST weight).
4. Parses the resulting `*_stats.csv` and asserts the p95 budget + zero failures.
5. Writes `backend/.perf-runs/price-history-{PASSED,FAILED}-<iso8601>.json` with the percentile dump.

Tunable via env vars: `PERF_HOST`, `PERF_USERS`, `PERF_SPAWN_RATE`, `PERF_RUN_TIME`, `PERF_WINDOW`, `PERF_BATCH_SIZE`, `PERF_BEARER_TOKEN`.

## What to do on FAIL

The runner exits **1** on a budget miss and writes `price-history-FAILED-<iso>.json` containing:

- the percentile dump for both endpoints
- the failing assertion(s)
- the canonical remediation: **"Open R036 (materialized `part_price_summary`) per D004"**

Open R036 in `.gsd/REQUIREMENTS.md`, file the follow-up slice, and reference the FAILED file as evidence.

## Where evidence lives

`backend/.perf-runs/` is the single canonical location for perf-gate output. The directory is gitignored — files are transient and regenerated each run. The most recent file (`ls -lt backend/.perf-runs/`) is what S13 milestone verification re-reads.

```bash
ls -lt backend/.perf-runs/                                    # most recent first
cat backend/.perf-runs/price-history-PASSED-<latest>.json | jq  # percentile breakdown
```

## Files in this directory

| File | Purpose |
| --- | --- |
| `locustfile_price_history.py` | Locust scenario (weighted GET/POST users) |
| `run_price_history_loadtest.sh` | Orchestrator (preflight → locust → parse → assert) |
| `_parse_locust_csv.py` | CSV parser + p95 assertion + evidence-file writer |
| `README.md` | This file |

## Gate-on-the-gate

`backend/tests/test_perf_gate_script.py` exercises the assertion logic against synthetic CSVs (`backend/tests/fixtures/perf/locust_stats_{passing,failing}.csv`) using `--csv-fixture`. It runs only when `PERF_GATE_TEST=true` is set so the locust install isn't a hard CI dependency.

```bash
PERF_GATE_TEST=true TESTING=true pytest backend/tests/test_perf_gate_script.py
```

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | PASS — all p95 budgets met, zero failures |
| 1 | FAIL — assertion missed (FAILED.json written; open R036) |
| 2 | locust process exited non-zero |
| 3 | CSV malformed |
| 4 | CSV file missing |
| 5 | CSV had zero requests |
| 6 | CSV missing per-endpoint stats row |

## Cross-references

- [D004 — query-time aggregation with explicit perf gate](../../../.gsd/DECISIONS.md)
- [R019 — perf gate requirement](../../../.gsd/REQUIREMENTS.md)
- [R036 — materialized `part_price_summary` follow-up (opens on FAIL)](../../../.gsd/REQUIREMENTS.md)
- Slice plan: `.gsd/milestones/M002/slices/S05/S05-PLAN.md`
