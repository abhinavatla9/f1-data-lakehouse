#### OpenF1 has a total of 18 endpoints. Jolpi.ca is one nested endpoint

## OpenF1 · Car Data
  
Grain: One row one driver's car telemetry data at one point

Natural Key: session_key + driver_number + date

Fields
| Field | Type received | Target type | Nullable | Notes |
|---|---|---|---|---|
| date | text | timestamp (UTC) | No (none seen) | Time of the sample. e.g. 2024-07-07T14:10:00.301000+00:00 |
| meeting_key | number | integer | No (none seen) | Links to meetings |
| session_key | number | integer | No (none seen) | Links to sessions. Not sequential. |
| driver_number | number | integer | No (none seen) | Car number. Not a stable driver ID across seasons. |
| speed | number | integer | No (none seen) | km/h. 0 when stationary. |
| rpm | number | integer | No (none seen) | Engine revolutions per minute |
| n_gear | number | integer | No (none seen) | 1–8 = gear. 0 = neutral / no gear. |
| throttle | number | integer | No (none seen) | Throttle pedal %, 0–100. Full throttle = 100. 104 = no signal (see Quirks). |
| brake | number | integer | No (none seen) | Effectively on/off: 0 = off, 100 = on. Not a pressure. 104 = no signal (see Quirks). |
| drs | number | integer | No (none seen) | DRS state code. Per docs: 0, 1 = off · 8 = eligible, detected in zone · 10, 12, 14 = on · 2, 3, 9 = unknown. Verify against the docs table. |

- **Ingestion strategy:** request one driver-session at a time (≈17k rows for a race). If a request fails or times out, retry that driver-session in 10-minute date windows. Chunk size is configurable. Reason: one request per driver-session is 7× faster against the 30 requests/min limit, and the fallback limits lost work on failure.

### Volume

- **Rows for #44 (session 9558):** ⬜ TODO (expected above 17–18k because pre-race data is included)
- **Race-time-only estimate for #44:** ≈ 4,950 s × 3.5 samples/s ≈ 17,000–18,000
- **Estimated full grid (× 20), race time only:** ≈ 346,000 rows
- **Scheduled-time estimate (2 h):** ≈ 504,000 rows, overestimating actual race time by ~45%
- **location endpoint:** same sample rate, so roughly the same volume again

### Timestamp format

- ISO-8601, UTC offset +00:00
- 6 fractional digits, effectively millisecond resolution (e.g. .700000)

### Nulls & quirks

- **Irregular sample interval:** gaps of 160–440 ms between samples (avg ≈ 284 ms, ≈ 3.5 Hz) in a 6-second window for #44. Not a fixed 250 ms.
- **104 = no-signal placeholder:** thousands of rows for #44 with throttle = 104 AND brake = 104 AND speed = 0, all before the race (e.g. 13:08 UTC). Not a valid reading.
- **Data starts before the session:** samples exist from ~13:08 UTC; the race started 14:03:12. car_data covers garage and grid time, not just the session.
- **Full throttle = 100:** confirmed by throttle rising to 100 and holding during acceleration.
- **Brake is binary** (0/100), not a pressure reading.

### Ingestion maths (3 seasons, all sessions)

| | Value |
|---|---|
| Sessions: 2023 / 2024 / 2025 | 118 / 123 / 123 |
| Total sessions | 364 (may include pre-season testing; recount excluding testing) |
| Driver-sessions (× 20) | 7,280 |
| 1 chunk per driver-session ÷ 30 req/min | ≈ 243 min ≈ 4.0 h |
| 7 chunks per driver-session ÷ 30 req/min | ≈ 1,699 min ≈ 28.3 h |
| Including location (× 2) | ≈ 8.1 h (1 chunk) / ≈ 56.6 h (7 chunks) |
| Non-telemetry endpoints (~10 × 364 sessions) | ≈ 3,640 requests ≈ 2 h |

| Scope | Requests (car_data + location) | 1 chunk | 7 chunks |
|---|---|---|---|
| Must: 5 races | 200 | ≈ 7 min | ≈ 47 min |
| Stretch: all 2025 races | 960 | ≈ 32 min | ≈ 3.7 h |
| Everything, all sessions | 14,560 | ≈ 8.1 h | ≈ 56.6 h |

### Pipeline impact

- **Natural key** includes date. Without it, MERGE collapses a driver's session into one row.
- **104 → null in silver:** throttle = 104 or brake = 104 is converted to null with a no_signal flag. Not quarantined (it's expected source behaviour) and not capped at 100 (that would turn "no signal" into "full throttle").
- **DQ-01 refinement:** the throttle 0–100 rule applies after 104 is converted to null. Any other value outside 0–100 is quarantined.
- **Trim to the session window:** silver keeps only samples between the session's first lap start and last lap end (from laps), not the scheduled date_start/date_end. Pre- and post-session samples are dropped and counted in ops.
- **No fixed interval:** fact_telemetry_1s aggregates by 1-second time buckets, never by row count.
- **Brake as boolean in silver:** brake_on = brake = 100.
- **Ingestion strategy (ADR-002):** request one driver-session at a time. If a request fails or times out, retry that driver-session in 10-minute date windows. Chunk size is configurable. Reason: one request per driver-session is 7× faster against the 30 requests/min limit, and the fallback limits lost work on failure.
- **Backfill must be resumable:** the full backfill takes ~10 h, so it can't finish in one session. It must run as an unattended job and resume from the last completed driver-session.
- **Scope:** telemetry for 5 races (Must) ≈ 7 min of requests. All of 2025 (Stretch) ≈ 32 min. Full 3 seasons stays out of scope.

## OpenF1 · Pit
  
Grain: One row is one driver's pit information

Natural Key: session_key + driver_number + lap_number

Fields
|Field|Type received|Target type|Nullable|Notes|
|-----|-------------|-----------|--------|-----|
|meeting_key|number|integer|no|Links to race weekend|
|session_key|number|integer|no|Not sequential|
|driver_number|number|integer|no|Represents each driver|
|stop_duration|number|decimal|yes|only available after 2024 US GP|
|lap_number|number|integer|no|Lap number of the pit|
|lane_duration|number|decimal|no|Seconds spent in pit lane|
|pit_duration|number|decimal|no|same as 'lane_duration', will be deprecated from 2027|
|date|text|timestamp|no|timestamp of the pit lane enterance|

### Nulls & quirks

- **Row count (9558):** 45 pit lane passes across 19 drivers. #10 has none (did not start).
- **Stints − 1 check: ✅ matches for every driver.** 65 stints − 20 first stints = 45 pit rows. Per driver: #11, #24, #31 = 4 · #16, #55 = 3 · #63 = 1 · all others = 2.
- **stop_duration is null in all 45 rows.** Consistent with the docs: stationary time is only available from the 2024 US GP onward. All 2023 and most 2024 races will have no stationary time.
- **pit_duration = lane_duration in every row.** pit_duration is a duplicate of lane_duration, scheduled for deprecation.
- **lap_number = the last lap of the old stint (the in-lap).** e.g. #44 pits on lap 27; stint 1 ends lap 27, stint 2 starts lap 28.
- **No driver has two rows on the same lap** in this session.
- **Rows are ordered by time, not by driver.**
- **Durations:** range 28.2–34.7 s, mean ≈ 29.7 s. Longest: #23 lap 27 (34.7 s). A long lane time can mean a slow stop, a queue behind a team-mate, or a penalty, and can't be told apart from this endpoint alone.
- **Timestamp format:** ISO-8601 UTC with fractional seconds; check precision against laps.

### Pipeline impact

- **Pit stop leaderboard (Media Desk):** must use **lane_duration** for 2023–2024 races. Stationary time can only be shown from the 2024 US GP onward. The dashboard must label which metric it shows.
- **Never read pit_duration.** Map lane_duration only, so deprecation doesn't break the pipeline. Schema evolution must tolerate pit_duration disappearing.
- **Proposed DQ-10:** for each driver, pit rows = stints − 1 (excluding non-starters). Mismatch → quarantine and alert.
- **Proposed DQ-11:** lane_duration between 15 and 60 s. Outside → flag as outlier, don't drop (penalties and red flags are real).
- **Natural key risk:** session + driver + lap_number held here, but a drive-through penalty on the same lap as a stop is possible in theory. Consider session + driver + date as a fallback key.
- **Undercut analysis (Day 9):** pit lap = in-lap; the out-lap is lap_number + 1, matching is_pit_out_lap in laps (verify on Day 4).

## OpenF1 · Stints
  
Grain: One row is one driver's stint in one session

Natural Key: session_key + driver_number + stint_number

Fields
|Field|Type received|Target type|Nullable|Notes|
|-----|-------------|-----------|--------|-----|
|meeting_key|number|integer|no|Links to race weekend|
|session_key|number|integer|no|Not sequential|
|driver_number|number|integer|no|Represents each driver
|stint_number|number|integer|no|starts at 1 and increases by 1 at each tyre change|
|lap_start|number|integer|yes| The first lap of the stint|
|lap_end|number|integer|yes| The last lap of the stint|
|compound|string|string|no|Shows the type of tyre of the current stint|
|tyre_age_at_start|number|integer|no|0 means a fresh tire and incremental count represents the number of laps it was used in|

### Nulls & quirks

- **Row count (9558):** 65 stints. Not 20 × 3: 13 drivers had 3 stints, 2 drivers had 4 (#16, #55), 3 drivers had 5 (#11, #24, #31), #63 had 2 (retired), #10 had 1 (did not start).
- **#10 Gasly, phantom stint:** one stint row (MEDIUM, tyre age 0) with null lap_start and null lap_end. Same pattern as his phantom lap 1 row in laps. Only nulls in the session.
- **A stint is a new set of tyres, not a new compound:** #11, #16 and #24 have consecutive INTERMEDIATE stints, so they pitted for fresh tyres of the same compound. Stint changes cannot be detected from compound changes.
- **Weather gamble:** #31 went INTERMEDIATE → MEDIUM → INTERMEDIATE (stints 2–4) as conditions changed.
- **Used tyres:** #4, #24, #27 and #55 each started one stint on a used SOFT set (tyre age 1–3), all late in the race. Likely sets saved from qualifying.
- **Compounds seen:** SOFT, MEDIUM, HARD, INTERMEDIATE (all uppercase). WET not seen in this session.

### Pipeline impact

- **Tyre age on any lap** = tyre_age_at_start + (lap_number − lap_start). fact_lap needs a tyre_age column calculated this way.
- **Degradation:** exclude stints shorter than 5 laps from the regression (too few points to fit a slope).
- **DQ-04 refinement:** before checking lap → stint coverage, exclude phantom laps (null lap_duration where the driver's stint range is null, i.e. did not start). Log them to ops as a known exception. Any other unmapped lap still fails the run.
- **Gaps or overlaps in other races:** quarantine that driver's laps for the session and alert, rather than failing the whole run.
- **Pit stop count check:** stints − 1 should equal pit stops per driver (verified in the pit contract).
  
## OpenF1 · Laps
  
Grain: One row is one driver's lap in one session

Natural Key: session_key + driver_number + lap_number

Fields
|Field|Type received|Target type|Nullable|Notes|
|-----|-------------|-----------|--------|-----|
|meeting_key |number|integer|no|Links to race weekend|
|session_key|number|integer|no|Not sequential|
|driver_number|number|integer|no|Represents each driver
|lap_number|number|integer|no|Incremental|
|duration_sector_n|number|decimal|yes| duration_sector_1, duration_sector_2, duration_sector_3, Measured in seconds, lap is divided into three sections. Has 2 and 3 also|
|date_start|timestamp|timestamp|yes|Can be null, pit lane starts are not recorded, pit flag also does not capture|
|in_speed|number|integer|yes|Speed at a given point on the lap, has 1 and 2|
|is_pit_out_lap|number|boolean|no|says whether the driver pitted in this lap|
|segments_sector_n|array|array|yes| segments_sector_1, segments_sector_2, segments_sector_3, a list of values representing mini-sectors within sectors, displays the colour of the sector for ex. 2048	yellow sector represents average speed|
|st_speed|number|integer|yes|Speed trap reading at the fastest point on the track|
|lap_duration|number|decimal|yes|Lap timing|

Address used: api.openf1.org/v1/laps?session_key=9558

Timestamp format: 2024-07-07T14:15:35.027000+00:00

Nulls & quirks
- Lap 1 date_start is identical for every driver (the race start, not an individual line crossing)
- Gasly (#10): phantom lap 1 row; Jolpica says Did not start
- Pérez (#11): null date_start and sector 1 on lap 1. Cause unconfirmed; Jolpica shows grid 20 (open discrepancy).
- Russell (#63): what did you find for his last lap?

Reconciliation vs Jolpica: total laps from Jolpica + phantom rows = ? vs OpenF1 row count = ?

Pipeline impact
- Exclude lap 1, pit-out laps and null-duration laps from race pace
- "Laps completed" can't be counted as rows (phantom rows)
- Proposed DQ-08: sector 1 + 2 + 3 ≈ lap_duration
- Mini-sector arrays stay in bronze; decision for silver deferred


## OpenF1 · Sessions
  
Grain: One row per session (practice, qualifying, sprint, race) of a race weekend.

Natural key: session_key

 Fields
 | Field              | Type received | Target type     | Nullable | Notes                                                |
 |--------------------|---------------|-----------------|----------|------------------------------------------------------|
 | session_key        | number        | integer         | No       | Not sequential; gaps exist (9554 → 9558)             |
 | meeting_key        | number        | integer         | No       | Links to the race weekend                            |
 | session_name       | text          | string          | No       | e.g. "Practice 1", "Race"                            |
 | session_type       | text          | string          | No       | "Practice", "Qualifying", "Race"                     |
 | date_start         | text          | timestamp (UTC) | ?        | ISO-8601 with +00:00 offset                          |
 | date_end           | text          | timestamp (UTC) | ?        | Appears to be scheduled, not actual. To be verified. |
 | country_name       | text          | string          | No       | "United Kingdom", not "Great Britain"                |
 | circuit_short_name | text          | string          | No       | "Silverstone"                                        |
 | year               | number        | integer         | No       |                                                      |

 Timestamp format: e.g. 2024-07-07T14:00:00+00:00 (UTC)

 Volume: 5 rows for the reference weekend (meeting 1240)

 Nulls & quirks
 - Session keys are not consecutive; always discover them through the API
 - Start and end times look like the schedule; the actual race end must come from laps
 - Country naming may differ from Jolpica

 Filtering / pagination: filter by year, meeting key, session key, country, session name.

A few notes:
- "?" in the Nullable column is fine for now. It means you haven't seen enough data to know yet. Be honest about what you don't know.
- The "Type received" vs. "Target type" columns are the heart of it. Most timestamps arrive as text and must become real timestamps in silver. That's Requirement P1, explicit schemas.
- I've only listed the fields we saw. Open the endpoint yourself and add any I missed. There are a few more, and finding them is part of your job.

How it gets used later in the sprint

- Day 3 (Bronze): your explicit schemas come straight from the Fields table
- Day 4–5 (Silver): your data quality rules come from the Nulls & quirks list
- Day 6: the range join depends on the timestamp format you recorded
- Chaos drill: when a field changes upstream, you compare against the contract to see what broke

## Jolpica · results

**Address used:** api.jolpi.ca/ergast/f1/2024/12/results/
**Date checked:** 27 Oct 2026

**Nesting path:** MRData → RaceTable → Races[] → Results[]
Race-level fields (season, round, raceName, date, time, Circuit) sit on Races[]; driver-level fields sit on Results[], with nested Driver, Constructor, Time and FastestLap objects. Must be flattened (P10).

**One row is (after flattening):** one driver's classified result in one race.

**Natural key:** season + round + Driver.driverId
**Stops being unique when:** season is dropped (round numbers repeat every year). Do not use permanentNumber or code in the key (see Quirks).

**Row count (2024 round 12):** 20
**Pagination (MRData):** limit = "30", offset = "0", total = "20" → fits on one page.

### Fields: race level

| Field | Type received | Target type | Nullable | Notes |
|---|---|---|---|---|
| season | text | integer | No (none seen) | "2024" |
| round | text | integer | No (none seen) | "12". Repeats each season. |
| raceName | text | string | No (none seen) | "British Grand Prix" |
| date | text | date | No (none seen) | "2024-07-07" |
| time | text | time (UTC) | No (none seen) | "14:00:00Z". Scheduled start; matches OpenF1 session date_start. |
| Circuit.circuitId | text | string | No (none seen) | "silverstone". Stable text ID. |
| Circuit.circuitName | text | string | No (none seen) | "Silverstone Circuit" |
| Circuit.Location.locality | text | string | No (none seen) | "Silverstone" |
| Circuit.Location.country | text | string | No (none seen) | "UK" (OpenF1 says "United Kingdom") |
| Circuit.Location.lat / long | text | double | No (none seen) | "52.0786" / "-1.01694" |

### Fields: result level

| Field | Type received | Target type | Nullable | Notes |
|---|---|---|---|---|
| number | text | integer | No (none seen) | Car number in THIS race. Historically correct. |
| position | text | integer | No (none seen) | Always numeric, even for DNS (Gasly = "20") |
| positionText | text | string | No (none seen) | Numeric for classified drivers; "R" = retired, "W" = withdrawn. Other codes per docs. |
| points | text | double | No (none seen) | Can be fractional in some races (half points) |
| grid | text | integer | No (none seen) | Starting position. 0 normally = pit lane start (none seen here). |
| laps | text | integer | No (none seen) | Laps completed |
| status | text | string | No (none seen) | "Finished", "Lapped", "Retired", "Did not start" |
| Driver.driverId | text | string | No (none seen) | Stable text ID, e.g. "hamilton", "max_verstappen" |
| Driver.permanentNumber | text | integer | No (none seen) | ⚠️ CURRENT number, not historical (see Quirks) |
| Driver.code | text | string | No (none seen) | 3-letter code, e.g. "HAM" |
| Driver.givenName / familyName | text | string | No (none seen) | Keeps accents: "Hülkenberg", "Pérez" |
| Driver.dateOfBirth | text | date | No (none seen) | |
| Driver.nationality | text | string | No (none seen) | |
| Constructor.constructorId | text | string | No (none seen) | Stable text ID, e.g. "red_bull", "rb", "sauber" |
| Constructor.name | text | string | No (none seen) | e.g. "Red Bull", "RB F1 Team", "Haas F1 Team" |
| Time.millis | text | long | Yes (object missing) | Race time in ms. Object absent for Retired and DNS. |
| Time.time | text | string | Yes (object missing) | Winner: total time. Others: gap, e.g. "+18.005" |
| FastestLap.rank | text | integer | Yes (object missing) | 1 = fastest lap of the race. Absent for DNS. |
| FastestLap.lap | text | integer | Yes (object missing) | Lap the fastest lap was set on |
| FastestLap.Time.time | text | string | Yes (object missing) | e.g. "1:28.293" (text, needs parsing to seconds) |
| FastestLap.AverageSpeed | text | double | Yes (object missing) | Units given in a separate field |

### Nulls & quirks

- **All values are text**, including every number. Every numeric field must be cast in silver.
- **Missing objects, not nulls:** Time is absent (not null) for #63 Russell (Retired) and #10 Gasly (DNS). FastestLap is absent only for Gasly. Missing ≠ null in JSON; the schema must allow absent objects.
- **⚠️ permanentNumber is not historical:** in 2024 round 12, Verstappen's permanentNumber = 3 and Norris's = 1, but they raced as #1 and #4. Jolpica shows each driver's current number. Use the race-level `number` for historical joins.
- **Time present for lapped drivers:** lapped drivers (e.g. #11 Pérez, 50 laps) still have a Time object with a gap value. Meaning for lapped cars is unclear; do not use Time to compare lapped drivers.
- **position vs positionText:** position is always a number (Gasly = 20) even when the driver didn't start; positionText carries the real classification ("W").
- **Accents preserved:** "Hülkenberg", "Pérez". OpenF1 removes them ("Hulkenberg", "Perez").
- **Fastest lap:** #55 Sainz, rank 1, consistent with the late used-Softs stint (laps 51–52) in OpenF1 stints.
- **Pérez grid = 20** (back of grid, not 0). See the laps contract open discrepancy.

### Laps reconciliation (feeds the laps contract)

| Laps completed | Drivers | Total |
|---|---|---|
| 52 | 12 | 624 |
| 51 | 3 (#3, #16, #77) | 153 |
| 50 | 3 (#11, #24, #31) | 150 |
| 33 | 1 (#63) | 33 |
| 0 | 1 (#10) | 0 |
| **Jolpica total** | **20** | **960** |

Expected OpenF1 laps rows = 960 + 1 (#10 phantom) + 1 if #63 has an incomplete final lap = **961 or 962**.
Stints check: every driver's final stint lap_end matches their Jolpica laps. ✅

### Cross-source comparison (2024 round 12)

| Concept | OpenF1 | Jolpica | Same? |
|---|---|---|---|
| Driver car number | driver_number: 1 (Verstappen) | number: "1" · permanentNumber: "3" | number ✅ · permanentNumber ❌ |
| Driver 3-letter code | name_acronym: VER | code: "VER" | ✅ |
| Driver name | last_name: Hulkenberg | familyName: Hülkenberg | ❌ (accents) |
| Team | team_name: Red Bull Racing | name: "Red Bull" · constructorId: red_bull | ❌ |
| Country | country_name: United Kingdom | country: UK | ❌ |
| Race start | date_start: 2024-07-07T14:00:00+00:00 | date: 2024-07-07 + time: 14:00:00Z | ✅ (after combining) |
| Types | numbers are numbers | numbers are text | ❌ |

### Cross-source mapping strategy

| Link | Proposed key | How it could fail |
|---|---|---|
| **Race** | Year + race date (OpenF1 Race session date_start date = Jolpica date) | 1) A race moved to a different day (weather, rescheduling) after one source updated. 2) Sprint weekends: must match on the OpenF1 session where session_type = Race, not Sprint. |
| **Driver** | Season + race `number` + `code` (both must agree) | 1) A reserve driver uses a number previously used by someone else. 2) Two drivers share a code in one season (rare but possible). Fallback: manual mapping table in config. |
| **Team** | Manual mapping table: Jolpica constructorId ↔ OpenF1 team_name, per season | 1) Team renames (AlphaTauri → RB → Racing Bulls) need new rows each season. 2) Sponsor-name changes mid-season break exact text matching on OpenF1's side. |

**Never join on:** permanentNumber (current, not historical), names (accents differ), country (naming differs).

### Pipeline impact

- **Flatten in bronze → silver:** explode Races[] and Results[]; pull race-level fields onto each result row (P10).
- **Cast every field from text** in silver; casting failures go to quarantine.
- **Schema must allow absent objects** (Time, FastestLap); treat absent as null.
- **DQ-05 compares on positionText, not position**, so DNS/DNF drivers reconcile correctly (Gasly "W" ≠ a classified 20th place).
- **Driver mapping uses race `number` + `code`, scoped by season.** permanentNumber is excluded.
- **Team mapping is a config table** (constructorId ↔ team_name per season); unmapped teams fail the run and alert.
- **Pagination:** total ≤ limit for one race's results, but laps and pitstops for one race exceed one page; the client must follow offset until offset ≥ total.
- **Fastest lap times are text** ("1:28.293"); convert to seconds in silver.

