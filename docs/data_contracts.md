OpenF1 has a total of 18 endpoints.

*OpenF1 · Stints*
  
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
  
  *OpenF1 · Laps*
  
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


  OpenF1 · sessions
  
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
