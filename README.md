# 🏁 Project Parc Fermé — Production F1 Data Lakehouse

> A production-grade data platform that ingests, validates, models, and serves Formula 1 timing, strategy, and telemetry data on Azure Databricks — built to the standards of a real data engineering team, with SLAs, data contracts, CI/CD, observability, and incident postmortems.

![Status](https://img.shields.io/badge/status-in%20development-yellow)
![Platform](https://img.shields.io/badge/platform-Azure%20Databricks-red)
![Language](https://img.shields.io/badge/language-PySpark-orange)
![Storage](https://img.shields.io/badge/storage-Delta%20Lake-blue)
![Governance](https://img.shields.io/badge/governance-Unity%20Catalog-green)

---

## 📋 Table of Contents
1. [Business Context](#1-business-context)
2. [Scope](#2-scope)
3. [Data Sources](#3-data-sources)
4. [Architecture](#4-architecture)
5. [Data Model](#5-data-model-gold-layer)
6. [PySpark Competencies](#6-pyspark-competencies)
7. [Data Quality Rules](#7-data-quality-rules)
8. [Non-Functional Requirements](#8-non-functional-requirements)
9. [Engineering Standards](#9-engineering-standards)
10. [Sprint Plan & Progress](#10-sprint-plan--progress)
11. [Incident Log (Chaos Drills)](#11-incident-log-chaos-drills)
12. [Results & Metrics](#12-results--metrics)
13. [Documentation Index](#13-documentation-index)
14. [Setup & Running](#14-setup--running)
15. [Stretch Goals](#15-stretch-goals)
16. [Design Review Questions](#16-design-review-questions)

---

## 1. Business Context

**Sector Three Analytics** (fictional) delivers race strategy insights to two internal customers:

| Customer | Needs | SLA |
|---|---|---|
| **Strategy Desk** (analysts) | Tyre degradation, pit stop effectiveness, undercut/overcut outcomes, clean-air race pace | Gold data available **≤ 30 min** after session data lands |
| **Media Desk** (content team) | Pit stop leaderboards, position-change stories, fastest laps, teammate head-to-heads | Same day, and the numbers must **never contradict official results** |

**Problem:** Analysis is currently done by hand in spreadsheets, and incorrect figures have been published twice.
**Goal:** Replace the manual process with an automated, tested, observable pipeline.
**Guiding principle:** *Trust is the product.* A wrong number costs more than a late one.

---

## 2. Scope

### In Scope
- All sessions (FP, Sprint, Qualifying, Race) for the **2023, 2024 and 2025** seasons: reference and lap-level data
- High-frequency telemetry (car data + location) for **at least 5 races**
- **Replay mode**: stream a historical race through the pipeline as if it were live
- Historical results (1950 onward) for reconciliation and dimensions

### Out of Scope
- Machine learning predictions (Stretch only)
- Paid or commercial F1 data feeds
- A public-facing application

### Priority Levels
| Level | Meaning |
|---|---|
| **Must** | Required for demo day. Never cut. |
| **Should** | Delivered if on schedule |
| **Stretch** | Differentiators |

---

## 3. Data Sources

| Source | Role | Endpoints / Entities | Known Challenges |
|---|---|---|---|
| **OpenF1 API** | Primary | meetings, sessions, drivers, laps, stints, pit, position, intervals, weather, race_control, team_radio, car_data, location | Rate limits, very large telemetry payloads (requires chunking), mixed timestamp precision, null lap durations, live-access terms |
| **Jolpica API** (Ergast successor) | Secondary / reconciliation | seasons, results, standings, constructors, circuits | Pagination, identifiers that differ from OpenF1 (cross-source key mapping required) |

📄 Full grain, keys, volumes and quirks per endpoint: [`docs/data_contracts.md`](docs/data_contracts.md)

---

## 4. Architecture

### Data Flow

    OpenF1 API ──┐
                 ├──► Ingestion Service ──► ADLS Gen2 Landing ──► Bronze ──► Silver ──► Gold ──► Databricks SQL Dashboard
    Jolpica API ─┘    (config-driven,        (immutable raw)       (Auto      (typed,    (star
                       retries, rate-                               Loader)    deduped,   schema)
                       limited, resumable)                                     validated)
                                                                       │          │
                                                                       ▼          ▼
                                                                   Quarantine   Ops (run logs,
                                                                   (rejects)    metrics, freshness)

> Replace this with a proper architecture diagram image on Day 14.

### Platform
| Component | Technology |
|---|---|
| Compute | Azure Databricks |
| Storage | ADLS Gen2 + Delta Lake |
| Governance | Unity Catalog |
| Secrets | Azure Key Vault–backed secret scope |
| Orchestration | Lakeflow Jobs |
| Pipelines | Lakeflow Declarative Pipelines (Python) + Structured Streaming |
| CI/CD | Databricks Asset Bundles + GitHub Actions |
| Infrastructure | Terraform (Should) |
| Serving | Databricks SQL dashboards |

### Unity Catalog Layout
| Catalog | Schemas |
|---|---|
| `dev` | landing · bronze · silver · gold · ops · quarantine |
| `prod` | landing · bronze · silver · gold · ops · quarantine |

**Rules**
- Nothing is deployed to `prod` by hand. CI/CD only.
- Least-privilege access: the `strategy_analysts` group reads **gold only**.

### Layer Responsibilities
| Layer | Contract |
|---|---|
| **Landing** | Raw API responses, written once and never modified. Deterministic paths by source / endpoint / season / session / run ID. |
| **Bronze** | One table per endpoint, loaded incrementally. Explicit schemas. Rescued-data column. Ingestion metadata on every row. |
| **Silver** | Typed, UTC-normalized, deduplicated, validated. Failed rows go to quarantine with a reason code. |
| **Gold** | Business-ready star schema. The only layer analysts may query. |
| **Ops** | Every run logged: status, duration, rows in/out per layer, errors. |
| **Quarantine** | Rejected records with rule ID, reason and run ID, for review and replay. |

### Budget
- Hard ceiling: **US $50** for the sprint
- Budget alert configured **before** any resource is created
- Exceeding the budget counts as a production incident and requires a postmortem

---

## 5. Data Model (Gold Layer)

### Dimensions
| Table | Grain | Notes |
|---|---|---|
| `dim_driver` | Driver version | **SCD Type 2.** Mid-season team changes; car numbers reused across eras. |
| `dim_constructor` | Constructor version | **SCD Type 2.** AlphaTauri → RB → Racing Bulls modeled as one entity with history. |
| `dim_session` | Session | Meeting, circuit, session type, UTC + local time |
| `dim_circuit` | Circuit | Country, timezone |

### Facts & Aggregates
| Table | Grain | Key Measures |
|---|---|---|
| `fact_lap` | Driver × session × lap | Lap time, sectors, compound, tyre age, stint, SC/VSC/red-flag flag, pit in/out flag |
| `fact_stint` | Driver × session × stint | Compound, length, **degradation rate (s/lap)** |
| `fact_pit_stop` | Driver × session × stop | Pit lane duration, positions gained/lost within N laps (undercut/overcut outcome) |
| `fact_position` | Driver × session × lap | End-of-lap position, change vs. previous lap |
| `fact_telemetry_1s` | Driver × session × second | Avg/max speed, throttle %, brake, gear, DRS, lap number |
| `agg_race_pace` | Driver × race | Median clean-air pace excluding SC, pit and outlier laps |

---

## 6. PySpark Competencies

Every item below must appear in the codebase and be explainable at the design review.

| # | Competency | Where | Status |
|---|---|---|---|
| P1 | Explicit schemas (no inference in production) | All bronze tables | ⬜ |
| P2 | Structured Streaming + Auto Loader, checkpoints, available-now & continuous triggers | Bronze, replay mode | ⬜ |
| P3 | Watermarks + streaming deduplication | Silver telemetry | ⬜ |
| P4 | **Range join**: telemetry samples → laps by time window | `fact_telemetry_1s` | ⬜ |
| P5 | **As-of join**: car data → nearest location sample | Silver telemetry | ⬜ |
| P6 | Broadcast joins, verified via query plan | Dimension lookups | ⬜ |
| P7 | Window functions: lag, lead, row_number, rank, running and framed aggregates | `fact_lap`, `fact_position`, `fact_pit_stop` | ⬜ |
| P8 | **Grouped Pandas UDF**: regression per stint | Tyre degradation | ⬜ |
| P9 | Delta MERGE inside foreachBatch | SCD2 dimensions | ⬜ |
| P10 | Complex types & higher-order functions (arrays, structs, explode) | Nested API parsing | ⬜ |
| P11 | Performance: liquid clustering, compaction, AQE, skew handling, before/after plans | `docs/PERFORMANCE.md` | ⬜ |
| P12 | DataFrame unit testing | Test suite | ⬜ |

> **Rule:** Python only, including the declarative pipelines. SQL is permitted only for dashboards and ad-hoc analysis.

---

## 7. Data Quality Rules

| ID | Rule | Action on Failure | Status |
|---|---|---|---|
| DQ-01 | Speed 0–380 km/h; gear 0–8; throttle 0–100 | Quarantine row | ⬜ |
| DQ-02 | No duplicate telemetry on (session, driver, timestamp) | Drop and count | ⬜ |
| DQ-03 | Lap times within justified per-circuit bounds | Flag as outlier (do not drop) | ⬜ |
| DQ-04 | Every lap maps to exactly one stint | **Fail run** | ⬜ |
| DQ-05 | **Final race classification matches official Jolpica results 100%** | **Fail run, block gold publish** | ⬜ |
| DQ-06 | Gold freshness ≤ 30 min after session lands | Alert | ⬜ |
| DQ-07 | Row counts in/out logged per layer; unexplained loss > 0.5% | Alert | ⬜ |

---

## 8. Non-Functional Requirements

| Area | Requirement | Status |
|---|---|---|
| **Idempotency** | Re-running any pipeline produces identical row counts and values | ⬜ |
| **Backfill** | One parameterized job backfills any season/session range, with no code changes | ⬜ |
| **Late / revised data** | Upstream corrections are reflected on the next run; history preserved where relevant | ⬜ |
| **Schema evolution** | New upstream fields never break the pipeline; they're captured, logged and reviewed | ⬜ |
| **Resilience** | Retries with exponential backoff, rate-limit compliance, resume from point of failure | ⬜ |
| **Security** | Zero secrets in Git. All secrets in Key Vault. | ⬜ |
| **Config-driven** | New endpoint = config change, not a new pipeline | ⬜ |
| **Observability** | Ops schema answers what ran, when, how long, how many rows, what failed | ⬜ |
| **Performance SLA** | One race session landing → gold in **< 20 min** | ⬜ |
| **Cost** | Total sprint spend ≤ US $50 | ⬜ |

---

## 9. Engineering Standards

### Git Workflow
- Protected `main` branch. No direct pushes.
- One feature branch per ticket, named after the ticket (e.g. `feature/F1-103-ingestion`)
- Every change goes through a pull request with a description and self-review checklist
- Commit messages reference ticket IDs

### CI/CD
| Trigger | Action |
|---|---|
| Pull request | Run tests + validate bundle |
| Merge to `main` | Deploy to `dev` |
| Tagged release | Deploy to `prod` |

### Definition of Done
A ticket is **done** only when:
- [ ] Acceptance criteria met
- [ ] Tests written and passing
- [ ] Documentation updated
- [ ] Idempotency verified (re-run check)
- [ ] Ops logging in place
- [ ] Merged via pull request with CI green

---

## 10. Sprint Plan & Progress

**Sprint 1:** Thu 22 Oct 2026 → Wed 4 Nov 2026 · 14 sessions × 2 hours = **28 hours**

### Week 1 — Foundations & Silver
- [ ] **Day 1 · F1-101 Environment & Governance**: budget alert, resource group, ADLS, workspace, Unity Catalog (dev/prod + schemas), Key Vault secret scope, repo with branch protection
- [ ] **Day 1 · F1-102 Data Discovery**: profile every endpoint; draft `docs/data_contracts.md`
- [ ] **Day 2 · F1-103 Ingestion Service**: config-driven, chunked telemetry, retries/backoff, rate limiting, resumable, deterministic landing paths, ops logging; one race weekend landed
- [ ] **Day 3 · F1-104 Bronze Layer**: config-driven Auto Loader for all endpoints, explicit schemas, rescued data, ingestion metadata; zero duplicates on re-run
- [ ] **Day 4 · F1-105 Silver Reference Data**: typed, UTC-normalized, deduped, validated, quarantine; OpenF1 ↔ Jolpica key mapping
- [ ] **Day 5 · F1-106 Silver Telemetry**: streaming with watermark dedupe, DQ-01/02, as-of join of car data → location
- [ ] **Day 6 · F1-107 Telemetry → Lap Enrichment**: range join, lap ↔ stint mapping (DQ-04), query plans before/after
- [ ] **Day 7 · F1-108 SCD2 Dimensions**: `dim_driver` and `dim_constructor` via MERGE in foreachBatch; Racing Bulls lineage correct
- [ ] **Day 7 · 🧑‍💼 Midpoint Design Review**: demo Bronze → Silver

### Week 2 — Gold, Quality, Production
- [ ] **Day 8 · F1-109 Gold Facts**: `fact_lap`, `fact_stint`, `fact_pit_stop`, `fact_position`, `fact_telemetry_1s`
- [ ] **Day 9 · F1-110 Strategy Analytics**: tyre degradation (grouped Pandas UDF), undercut/overcut logic, `agg_race_pace` with defensible exclusion rules
- [ ] **Day 10 · F1-111 Data Quality & Observability**: all DQ rules enforced, DQ-05 reconciliation passing for every race, ops dashboard, alerts
- [ ] **Day 11 · F1-112 Testing**: unit tests per transformation module; integration test on a frozen fixture session
- [ ] **Day 11 · F1-113 CI/CD**: Asset Bundles (dev/prod) + GitHub Actions; first prod deploy via pipeline only
- [ ] **Day 12 · F1-114 Orchestration, Backfill & Replay**: job DAG with dependencies, retries and notifications; 2023–2025 backfill; replay mode at accelerated speed
- [ ] **Day 13 · F1-115 Performance & Cost**: liquid clustering, compaction, AQE review; `docs/PERFORMANCE.md`; SLA measured; postmortems finalized
- [ ] **Day 14 · F1-116 Serving, Docs & Demo**: SQL dashboard, final README, runbook, ADRs, retrospective
- [ ] **Day 14 · 🎤 Demo Day**: 15-minute walkthrough

> **Scope rule:** If behind schedule, cut Stretch first, then Should. Never cut Musts, tests or DQ-05.

### Daily Standup Log
| Day | Done | Next | Blockers | Hours | Risks |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |
| 6 | | | | | |
| 7 | | | | | |
| 8 | | | | | |
| 9 | | | | | |
| 10 | | | | | |
| 11 | | | | | |
| 12 | | | | | |
| 13 | | | | | |
| 14 | | | | | |

---

## 11. Incident Log (Chaos Drills)

Five unannounced production incidents are injected during the sprint. Each one requires a fix and a postmortem (timeline, root cause, impact, fix, prevention) in [`docs/postmortems/`](docs/postmortems/).

**Incident categories:** upstream schema change · duplicate/replayed source files · API outage or rate limiting mid-backfill · late-arriving corrections · accidental full reprocess

| # | Date | Incident | Detection Method | Time to Resolve | Postmortem |
|---|---|---|---|---|---|
| INC-001 | | | | | |
| INC-002 | | | | | |
| INC-003 | | | | | |
| INC-004 | | | | | |
| INC-005 | | | | | |

---

## 12. Results & Metrics

*To be completed with measured values only. No estimates.*

| Metric | Target | Actual |
|---|---|---|
| Seasons ingested (reference + laps) | 3 | |
| Races with full telemetry | ≥ 5 | |
| Total rows processed | — | |
| Telemetry rows per race weekend | — | |
| Landing → gold time per race | < 20 min | |
| DQ-05 reconciliation pass rate | 100% | |
| Records quarantined (%) | — | |
| Duplicates removed | — | |
| Test count / pass rate | — | |
| Range join speed-up after optimization | — | |
| Total sprint cost | ≤ $50 | |
| Cost per race processed | — | |

---

## 13. Documentation Index

| Document | Purpose | Status |
|---|---|---|
| [`docs/data_contracts.md`](docs/data_contracts.md) | Grain, keys, volume, quirks per endpoint | ⬜ |
| [`docs/adr/`](docs/adr/) | ≥ 4 Architecture Decision Records | ⬜ |
| [`docs/runbook.md`](docs/runbook.md) | Rerun, backfill, recovery, secret rotation | ⬜ |
| [`docs/postmortems/`](docs/postmortems/) | One per incident | ⬜ |
| [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md) | Benchmarks, query plans, cost analysis | ⬜ |
| [`docs/retro.md`](docs/retro.md) | Sprint retrospective | ⬜ |

**Suggested ADR topics:** Auto Loader vs. direct API-to-Delta writes · SCD2 design · streaming vs. batch per layer · clustering/partitioning strategy · cross-source key mapping approach

---

## 14. Setup & Running

*To be completed by Day 14.*

### Prerequisites
- [ ] Azure subscription with budget alert
- [ ] Azure Databricks workspace (Unity Catalog enabled)
- [ ] ADLS Gen2 storage account
- [ ] Azure Key Vault + Databricks secret scope
- [ ] GitHub repository with Actions enabled
- [ ] Databricks CLI configured locally

### Deployment
*Document how to deploy to dev and prod via Asset Bundles.*

### Running a Session Load
*Document how to ingest and process a single session by parameter.*

### Running a Backfill
*Document how to backfill a season or session range.*

### Running Replay Mode
*Document how to replay a historical race as a stream.*

---

## 15. Stretch Goals
- [ ] Telemetry for the full 2025 season
- [ ] Live session ingestion (subject to OpenF1 access terms)
- [ ] Teammate head-to-head telemetry by corner (location-based corner detection)
- [ ] Tyre-life forecast with tracked accuracy
- [ ] Unity Catalog lineage screenshots in docs
- [ ] Cost per race as a tracked ops metric
- [ ] Full infrastructure in Terraform

---

## 16. Design Review Questions

The project is complete when every question below can be answered with evidence from this repo:

1. Walk through what happens end to end when a new race session lands.
2. The pipeline ran twice by accident. Prove nothing was duplicated.
3. Why a range join for telemetry, and what did the plan look like before optimization?
4. How do you guarantee a driver's 2023 laps are attributed to the correct team?
5. A lap time is corrected upstream three days later. What happens?
6. Which tables are streaming, and why not all of them?
7. Where is the data skew in this dataset and how was it handled?
8. What breaks first at 10× data volume?
9. What did the sprint cost, and where did the money go?
10. Describe the worst incident this sprint and what you'd do differently.

---

## 📜 Data & Licensing
Data comes from [OpenF1](https://openf1.org) and [Jolpica](https://github.com/jolpica/jolpica-f1). This is an independent portfolio project and is not affiliated with Formula 1, the FIA or any team. "Sector Three Analytics" is a fictional company used for project framing.
