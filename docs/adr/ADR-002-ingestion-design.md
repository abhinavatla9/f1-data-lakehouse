# ADR-002: Ingestion design

**Status:** Proposed
**Date:**
**Ticket:** F1-103

---

## Context

*The facts that force these decisions. You already know all of these from your data contracts. List them as bullets.*

- *Rate limits (OpenF1, Jolpica)*
- *Volumes: car_data per driver-session, full grid, 3 seasons*
- *Backfill time estimates (from the car_data maths)*
- *API behaviours: 404 means "no data", session keys not sequential, Jolpica pagination*
- *Constraint: Azure not available yet; must run locally first, ADLS later*
- *Requirements this must satisfy: idempotent, resumable, config-driven, traceable*

---

## 2.1 Landing path convention

**Options considered**

| Option | Pros | Cons |
|---|---|---|
| *Option A: e.g. path includes run ID* | | |
| *Option B: e.g. path without run ID* | | |

**Decision:** *Your chosen path pattern, written out with placeholders like {source}/{endpoint}/... and one real example for session 9558.*

**Consequences:** *What this makes easy, what it makes hard. How you still get traceability.*

---

## 2.2 Resumability

**Options considered**

| Option | Pros | Cons |
|---|---|---|
| *e.g. check whether the file exists* | | |
| *e.g. keep a progress record* | | |

**Decision:** *How the program knows what's done.*

**Half-written files:** *What happens if it crashes mid-write, and how you avoid treating a broken file as complete.*

**Consequences:**

---

## 2.3 Unit of work

**Decision:** *Define one unit for reference endpoints and one for telemetry.*

**Why:** *What gets retried, skipped and logged at this level.*

---

## 2.4 File contents & metadata

**Options considered**

| Option | Pros | Cons |
|---|---|---|
| *Raw response only* | | |
| *Response + metadata in the same file* | | |
| *Response + separate metadata file / run log* | | |

**Decision:**

**Metadata captured:** *List the fields: request address, fetched at, run ID, record count...*

---

## 2.5 Telemetry strategy

**Decision:** *Copy the reasoning from your car_data contract: one request per driver-session, chunk fallback, configurable window.*

**Non-starters:** *What car_data returns for #10 Gasly (check in the browser), and how the client handles it.*

---

## 2.6 Libraries

| Purpose | Library | Why |
|---|---|---|
| HTTP requests | | |
| Testing | | |
| *(anything else)* | | |

---

## Consequences (overall)

- ✅ *What this design makes easier*
- ❌ *What it makes harder*
- ⚠️ *Risks accepted*
