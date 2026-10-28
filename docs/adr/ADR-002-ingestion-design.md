# ADR-002: Ingestion design

**Status:** Accepted · **Ticket:** F1-103

## Context
OpenF1 allows 30 requests/minute. car_data is ~17,000+ rows per driver per race. A full backfill takes many hours, so ingestion must survive crashes and re-runs. Azure isn't ready yet, so files are saved locally first and moved to ADLS later.

## Decisions

**1. Where files are saved**
Path = source / endpoint / year / session / file.
- openf1/laps/2024/9558/laps.json
- openf1/car_data/2024/9558/driver_44.json
- jolpica/results/2024/round_12/results.json

**2. No duplicates**
The same request always saves to the same path. Running twice overwrites the file instead of creating a second copy.

**3. Restarting after a crash**
A checkpoint file records each completed download. On restart, completed downloads are skipped. A file is only marked complete after it has been fully written.

**4. Downloading car_data**
One request per driver per session. If a request fails, retry that driver-session in 10-minute pieces.

**5. Libraries**
- requests: fetching data from the APIs
- pytest: testing

## Consequences
- ✅ Re-running is safe; restarting after a crash is safe
- ✅ Moving to ADLS later only changes where the base folder points
- ❌ Overwriting means an older version of a file isn't kept
