# NASA data: decisions and change record

This is the record of every decision made while replacing ASTRA's invented mission values with
real NASA data, as described in `docs/plan/nasa-data-implementation.md`.

The rule the whole project follows: **a number only goes in ASTRA if it can be traced to a
fixture file and a source with a real URL.** Where a value could not be confirmed it is left
as `TODO(verify)` and the affected feature is switched off rather than guessed. Nothing in this
file quotes a number that is not in the code.

**Status:** WP1 to WP7 done, including the DONKI solar replay (fetched on 9 Nov 2026 from CCMC's
current API). WP8 (official 13 Nov resources) is done: slots A, B and C hold the five official
resources (see §13).

**Engine tests: 100.** `npm run test`, `npm run lint` and `npm run typecheck` all pass, and
`npm run build` succeeds with the `/data` and `/data/inspiration4` routes in it.

---

## 1. Where the data lives

| Path | What it holds |
| --- | --- |
| `engine/app/sources.py` | The citation catalogue. 30 NASA documents keyed by id, each with a real URL, plus the metric / hazard / organ / environment → source maps. |
| `engine/data/nasa/manifest.json` | The source registry. Every source, its role, its files, when it was fetched, and how it was obtained. |
| `engine/data/nasa/horizons/` | JPL Horizons Earth–Mars light time, range and Sun–Mars angle (real, 541 days to 2028-05-05, past the spring-2028 solar conjunction). |
| `engine/data/nasa/osdr_eda/` | Real ISS cabin CO₂/temperature/humidity and crew dose (EDA mission RR-7). |
| `engine/data/nasa/osdr_i4/` | Real Inspiration4 blood and urine measurements from four real astronauts. |
| `engine/data/nasa/donki/` | DONKI solar particle events (`sep.json`, 11), flares (`flr.json`, 23) and the replay model (`replay.json`). See §4.1. |
| `scripts/fetch/` | The downloader scripts. Standard library only, run by a developer on Earth. |

**Offline rule.** The engine never makes a network call. `engine/app/nasa.py` opens the manifest,
resolves a file path inside the data directory and refuses anything not listed in the manifest.
`scripts/fetch/*.py` are the only things that touch the network, and they are run manually:

```
uv run --no-project python -I scripts/fetch/horizons.py
uv run --no-project python -I scripts/fetch/osdr_eda.py
uv run --no-project python -I scripts/fetch/osdr_i4.py
uv run --no-project python -I scripts/fetch/donki.py
```

**Decision: the manifest is the single source of truth for "is this data real".**
The alternative was a per-module constant in the engine. That spreads the answer across four
files and makes it impossible to answer "is this number real?" from one place. The manifest is
listed on `/data` and is checked by `engine/tests/test_nasa.py`, which fails if a source is marked
`ready` but its file is missing.

---

## 2. Thresholds verified against the primary document

Every threshold below was read out of the NASA document itself, not taken from the plan or from
memory. Where the plan's number and the document's number disagreed, **the document won**.

| Value ASTRA shows | Source | Where in the document |
| --- | --- | --- |
| Career dose limit 600 mSv | NASA-STD-3001 Vol 1 (Rev C) | Requirement `[V1 4030]`, §4.8.2, p.39: "total career effective radiation dose due to spaceflight radiation exposure shall be less than 600 mSv" |
| Cabin CO₂ Act at 3.0 mmHg (1-hour) | NASA-STD-3001 Vol 2 | Requirement `[V2 6004]`, §6.2.1.3, p.53: "limit the average one-hour CO2 partial pressure (ppCO2) in the habitable volume to no more than 3 mmHg" |
| Cabin CO₂ Watch at 2.5 mmHg (7-day) | OCHMO-TB-004 | p.5: "To keep the risk of headache below 1%, average 7-day CO2 needs to be maintained below 2.5 mmHg (current ISS range: 1 to 9 mmHg; 3001 standard requires <3 mmHg)" |
| Headache appears at 2.8–4.5 mmHg | OCHMO-TB-004 | p.4 |
| Transit dose 1.84 mSv/day | Zeitlin et al. 2013, *Science* 340(6136):1080–1084 | `doi 10.1126/science.1235989` |
| Mars surface dose 0.64 mSv/day | Hassler et al. 2014, *Science* 343(6176) | `doi 10.1126/science.1244797` |

**Decision: the 2.5 mmHg Watch threshold is a headache-risk threshold, not an air-quality
threshold.** It is applied against the **7-day average**, not the instantaneous reading. The
instantaneous reading is compared against the 3.0 mmHg Act threshold from the standard. The two
limits measure different things over different windows, so `rules.cabin_status` takes both and
takes the worse of the two. The boundary table is pinned by a parametrised test in
`engine/tests/test_nasa.py`.

**Decision: the MSL/RAD dose rates are used directly and not scaled.** The plan proposed
scaling transit and surface rates by habitat shielding. MSL/RAD measured dose rates *inside the
Curiosity rover*, which is already shielded, so they are the right numbers for a crewed habitat
and no further factor is applied. The UI says "About 0.64 mSv/day on the surface."

**Decision: the DOIs were checked against Crossref before being written into the source
catalogue.** A plausible-looking DOI is worse than no DOI, because it looks verified.

---

## 3. Values that were invented before and are now real

| Value | Before | After | Source |
| --- | --- | --- | --- |
| Signal delay (Mars) | fixed 760 s | 338.3 s → 1203.4 s across the 541-day window, resolved per date | JPL Horizons, real |
| Signal delay (transit) | fixed 760 s | scaled by outbound progress over the 180-day leg, **labelled "approximate"** | Horizons Mars value × progress |
| ISS dose rate | 0.5 mSv/day (invented) | 0.287 mSv/day | EDA RR-7 daily dose, real |
| Cabin CO₂ | none | real ISS series, 1720 hourly readings | EDA RR-7, real |
| Blood reference ranges | invented | the Inspiration4 dataset's own Quest Diagnostics ranges | OSDR OSD-575 / OSD-569, real |
| Career limit | 600 mSv (from the plan) | 600 mSv (verified in the standard) | NASA-STD-3001 V1 |
| Transit / Mars dose | 1.5 / 0.3 mSv/day (invented) | 1.84 / 0.64 mSv/day | MSL/RAD, real |

**Decision: the transit delay is scaled, and says so.** There is no Horizons product for an
interplanetary cruise at arbitrary geometry, so the transit delay is the Earth–Mars light time
multiplied by the mission's outbound progress. `Engine.env()` returns
`light_time_source: "horizons-scaled"` for it and the UI prints "approximate, scaled from
Earth–Mars distance". It is labelled as an estimate rather than presented as a measurement.

**Decision: the station dose rate comes from the EDA daily dose, not from a constant.**
`0.287 mSv/day` is the average of the real crew daily dose series in the EDA fixture. The
response carries `rate_source` so the UI can say where the number came from.

---

## 4. Things that did not work, and what was done about them

### 4.1 DONKI solar particle events — **fetched** (resolved 9 Nov 2026)

The first attempt failed: `api.nasa.gov` returned HTTP 503 then 429 (the shared `DEMO_KEY` is
rate-limited), and the old CCMC host `kauai.ccmc.gsfc.nasa.gov/DONKI/WS/` timed out.

**What fixed it.** CCMC now serves DONKI at `https://ccmc.gsfc.nasa.gov/DONKI-API/get/{SEP|FLR}`
with no key. Two more things had to change:

- CCMC answers **HTTP 403** to a User-Agent that contains an e-mail address, so
  `scripts/fetch/_common.py` now sends a plain `astra-fetch/1.0`.
- The event ID guessed earlier (`2021-10-28T145142Z_00`) does not exist in DONKI. The real ID of
  the 28 Oct 2021 event, as GOES-P detected it above 100 MeV, is
  **`2021-10-28T16:35:00-SEP-001`**.

`scripts/fetch/donki.py` tries CCMC first and falls back to `api.nasa.gov`, which reads a personal
key from `NASA_API_KEY` (set it in the git-ignored `scripts/.env`, see `scripts/.env.example`). It
writes `sep.json` (11 particle events, Oct–Nov 2021), `flr.json` (23 flares, including the X1.0
flare of 28 Oct) and `replay.json`, which is what the engine reads.

**Note on the replay model.** The replay is explicitly
`illustrative: true`. A recorded SEP tells us when and how big the particle event was; it does
not tell us what the dose was inside a specific shield on a specific day. The engine applies the
recorded event energy to the shelter model and labels the result as illustrative.

### 4.2 EDA CO₂ unit conversion — **assumption, flagged**

The EDA publishes cabin CO₂ in **ppm** and does **not** publish the cabin pressure. To compare
against the 3.0 mmHg requirement, the fetch script converts with the standard atmospheric
pressure of 760 mmHg:

```
mmHg = ppm / 1e6 * 760
```

**`TODO(verify)`** — the ISS cabin actually runs near 14.5 psia (≈735 mmHg), which would make
the converted values about **3% lower**. This is recorded in the manifest note for
`osdr-eda-iss` and in §7 below. The conversion direction is conservative (it slightly overstates
CO₂), so the Watch/Act thresholds are not being tripped by the assumption.

The alternative — not showing the cabin card at all — was rejected because it loses a real
dataset and a real requirement to fix a unit-conversion detail.

### 4.3 EDA sensor spikes — **1534 readings dropped**

The raw EDA CO₂ series contains readings up to **9000 ppm**, which is not physically plausible
for the ISS cabin and is clearly a sensor artefact. `scripts/fetch/osdr_eda.py` drops any reading
above **2× the series median**; **1534 of 21948** readings were removed this way.

**Decision: drop, do not clip.** Clamping a spike to the threshold would invent a reading at the
exact value that matters most for the rule, which is the worst possible place to be wrong.
Dropping is visible and the count is recorded.

### 4.4 EDA fixture size — **downsampled to hourly**

The raw hourly-resolution CO₂ file was **2.7 MB**, over the plan's 500 KB per-fixture budget.
The fetch script averages the readings down to **one row per hour** (1720 rows,
**231.8 KB**). The CO₂ trend, the daily cycle and the threshold crossings all survive the
downsampling; the minute-level peak shape does not, and nothing in ASTRA depends on it.

### 4.5 Inspiration4 CBC haemoglobin units — **column swap**

The OSDR CBC CSV reports haemoglobin as a **percentage** in this dataset. ASTRA shows g/dL, so
the grams-per-decilitre columns are used instead. Recorded in the manifest note for
`osdr-i4-labs`.

### 4.6 Which OSDR study holds which test — **split across two studies**

- **OSD-575** — the comprehensive metabolic panel: glucose, creatinine, sodium, potassium,
  ALT, calcium.
- **OSD-569** — the complete blood count: white blood cells, haemoglobin, platelets,
  neutrophils, lymphocytes, hematocrit.

Both were downloaded from the OSDR `geode-py` file endpoint. The manifest note records both
study ids so the next fetch does not have to rediscover the split.

### 4.7 The EDA API shape — **bare lists, not `{"data": [...]}`**

The first fetch failed with "no ISS reading had a matching temperature and humidity sample".
The cause: the EDA endpoints return **bare JSON arrays**, and the temperature/humidity maps were
built with rows whose values were `null`, so null rows overwrote good ones. Fixed by filtering
`if r.get("temperature_iss") is not None` before building the lookup maps.

### 4.8 Conjunction SOT threshold — **ASTRA's own value**

`CONJUNCTION_SOT_DEG = 3.0` is the Sun–Observer–Target elongation below which ASTRA warns about
a solar conjunction. It is **derived by us** from the Horizons elongation column, **not quoted
from a NASA document**. It is marked `TODO(verify)` in `engine/app/catalog.py` and flagged in
§7. The warning is presented as a mission-ops judgement, not as a NASA limit.

### 4.9 The AstroRad / DLR August 2026 news item — **not used**

A NASA-sourced item about a radiation reduction from August 2026 was found but the URL could
not be resolved and confirmed. **No reduction percentage is quoted anywhere in ASTRA.** Nothing
from it was implemented.

---

## 5. Code changes, by file

### Engine

| File | Change |
| --- | --- |
| `engine/app/sources.py` | **New.** 30-document citation catalogue with real URLs, plus the metric / hazard / organ / environment source maps and `sources_for()`. |
| `engine/app/nasa.py` | **New.** The read-only registry: reads `manifest.json`, resolves fixture paths, refuses anything not listed. |
| `engine/app/catalog.py` | Added `MISSION["launch_utc"]`, `TRANSIT_DAYS`, `CONJUNCTION_SOT_DEG`, `CONJUNCTION_WARNING_DAYS`; new `CABIN` block (thresholds, how/why/guide, actions, sources); new `LABS` list of 12 analytes with `LAB_BY_ID`; real `radiation_msv_day` values; `public_catalog()` now publishes `sources`. |
| `engine/app/rules.py` | New `cabin_status(co2_1h, co2_7d)`; new `cabin_insight(cabin, headache_crew)` — fires only when **≥2 crew report a headache in 24 h AND** the cabin is Watch or worse; new `classify_lab(value, ref_low, ref_high)` with a 10% tolerance band; `INSIGHT_SOURCES` + `insight_sources()` so every insight carries its evidence. |
| `engine/app/store.py` | New `utc_of(met_s, launch_utc)` so a mission-elapsed time can be turned into a real UTC moment. |
| `engine/app/services.py` | `Engine` now takes the registry; new `_horizons()`, `_light_time()`, `_conjunction()`, `_solar_event()`, `start_solar_replay()`, `stop_solar_replay()`, `_replay_model()`, `_donki_events()`, `_cabin_series()`, `_eda_dose()`, `cabin()`, `inspiration4()`, `_headache_crew()`; `env()` returns the real delay, `utc`, `mission_day` and `light_time_source`; `dashboard()` carries the cabin card and injects the cabin insight. |
| `engine/app/main.py` | New routes `GET /nasa/sources`, `GET /nasa/sources/{id}`, `GET /nasa/cabin`, `GET /nasa/inspiration4`, `GET /nasa/solar/events`, `POST /nasa/replay/solar`; the app starts even if the manifest is missing (registry falls back to non-strict) so the crew-facing app keeps working; `/admin/reset` clears any active solar replay. |
| `engine/app/seed.py` | Seed data updated so the demo shows the cabin insight on the station: Lucas now logs a headache on day 141 alongside Ana, because the real EDA CO₂ sits in the Watch band and the insight needs two headaches in the same 24 hours. |
| `engine/tests/test_nasa.py` | **New.** 38 tests. |

### Web

| File | Change |
| --- | --- |
| `web/lib/types.ts` | `sources: string[]` on `Hazard`, `MetricDef`, `OrganDef`, `Environment`, `Insight`; new `SourceRef`, `NasaSource`, `NasaSources`, `Cabin`, `SolarEvent`, `Conjunction`, `LabSeries`, `LabAnalyte`, `Inspiration4`; `Environment` gained `utc`, `mission_day`, `light_time_source`; `Dashboard` gained `cabin`; `Catalog` gained `sources` and `mission.launch_utc`. |
| `web/lib/engine.ts` | `getNasaSources()`, `getCabin()`, `getInspiration4()`, `getSolarEvents()`, `postSolarReplay()`. |
| `web/components/ui/SourceTag.tsx` | **New.** `SourceTag` (a pill linking to `/data#<id>`), `SourceList` (a row of evidence links) and `sourceName()` (the short readable name for each source id, so the UI never shows a raw key like `std3001v2`). |
| `web/app/data/page.tsx` | **New.** The NASA data page: totals, one card per ready source with the manifest note behind a "How it was obtained" disclosure, pending sources, a link to the Inspiration4 page, the cited-documents grid, and the two disclaimers. A 404 from `/nasa/sources` is caught and shown as a **stale engine** message ("ASTRA Core is running an older build… restart it"), because a stale engine otherwise looks like missing NASA data. |
| `web/app/data/inspiration4/page.tsx` | **New.** Small multiples: one chart per analyte, one coloured line per crew member, the reference range as a shaded band, the flight window marked, every point labelled with its status. A clear "not available" state when the fixture is missing. |
| `web/app/page.tsx` | **New.** The **Cabin air** card (station only): CO₂ now, the 7-day average, temperature, humidity, the status chip, a sparkline and the evidence links. The **Radiation** card: mission dose against the career limit, the rate it is accruing at and where that rate came from, and the solar-event state with its shelter countdown and actions. Insight cards now carry their evidence links. |
| `web/app/learn/page.tsx` | Every hazard, body system and indicator carries its evidence links. A new **Sources** section groups the cited documents by kind (standards, technical briefs, papers, web pages). |
| `web/app/settings/page.tsx` | A new **Solar particle event** card with the **Replay a real solar storm** button. When the DONKI fixture is missing the engine answers 503 and the button reports that, rather than pretending a storm happened. |
| `web/components/crew/CommsPanel.tsx` | The Earth link card now shows where the light time came from (a `SourceTag` pointing at JPL Horizons), the mission UTC, and the solar-conjunction warning when the SOT elongation is low. |
| `web/components/body/BodyExplorer.tsx` | The Metabolism and Immune panels link to the Inspiration4 page ("See this in real astronauts"). Every organ panel carries its evidence links. |
| `web/components/measure/MeasureWizard.tsx` | Step 2 ("Why it matters") now ends with "Where this comes from" and the evidence links for that measurement. |
| `web/components/settings/SettingsControls.tsx` | The `SolarReplay` control. |
| `web/app/actions.ts` | `startSolarReplay()` server action. |
| `web/components/ui/icons.ts` | Added `Database`. |
| `web/components/shell/Shell.tsx` | Added the **Data** nav item. |

---

## 6. Tests

`engine/tests/test_nasa.py` (new, 38 tests) covers:

- the registry reads the committed manifest; a `ready` source's file exists; an unknown source
  raises; a file that is not listed raises; `ASTRA_NASA_DATA` can point the registry elsewhere;
  an unknown role is rejected;
- every metric, hazard, organ and environment has at least one source; every source id resolves
  to a real document; every URL is `https`; every `kind` is one of the four allowed values;
- the thresholds match the documents (600 mSv, 3.0 / 2.5 mmHg, 1.84 / 0.64 mSv/day);
- the cabin status boundaries, including the 2.4 / 2.5 / 2.9 / 3.0 / 3.1 cases;
- the cabin insight needs two headaches **and** bad air, and points at the air rather than at
  medicine;
- the lab classification against and outside the reference range;
- the API routes, including that the cabin is available on the station only, that the cabin card
  carries its thresholds and their sources, that the Mars delay comes from Horizons, that the
  radiation rate carries the source it came from (`msl-rad` off-world, `osdr-eda-iss` on the
  station), that the seeded demo actually fires the cabin-air insight, and that the solar replay
  is either honest (200 with `illustrative: true`) or honest (503), never a fake storm.

**Engine test count went from 23 to 58.** The README was updated to match.

---

## 7. Decisions about how the NASA data is presented

### 7.1 The evidence is one click away, not buried

Every threshold, hazard, body system, measurement and insight carries a small link to the
document behind it, and every one of those links lands on the **Data** page at the right card.
The alternative — a bibliography at the bottom of the page — was rejected: a crew member reading
"2.5 mmHg" needs the source *there*, not three screens away.

The links show a short readable name (`STD-3001 Vol 2`, `OCHMO-TB-004`, `MSL/RAD transit`)
rather than the raw id. The ids are stable keys the engine points at; they are not what a person
should have to read.

### 7.2 The manifest note is shown verbatim

The **Data** page shows each source's `note` field exactly as written in `manifest.json`, behind
a "How it was obtained" disclosure. That note is where the exact request URL, the unit conversion
and the data-cleaning counts live. It is the record of what was actually done, so it is shown
rather than paraphrased into marketing copy.

### 7.3 Two numbers, two windows, one status

The cabin card shows the 1-hour CO₂ **and** the 7-day average, because they are compared
against two different NASA limits measured over two different windows. Showing only one would
hide half the rule. The card states which limit each number is compared against.

### 7.4 A missing source is a visible state, not an empty one

Where a fixture is absent (DONKI), the app shows a clear "not available" state, the manifest
says `pending`, the route returns 503, and the button reports the failure. It never renders a
placeholder storm, a zero, or a plausible-looking number. The Inspiration4 page does the same
when its dataset is missing.

### 7.5 The replay is labelled illustrative at every level

A recorded solar particle event tells us when it happened and how big it was. It does not tell us
the dose inside a specific shield on a specific day. So the event's own facts (time, instruments,
link) are real and the dose is ours, and the payload carries `illustrative: true` plus a note
saying so. The UI prints that note rather than hiding it.

### 7.6 Real data does not replace the demo story

The crew, the mission and the symptom storylines stay fictional — they have to, so the demo can
show a sleep-debt storyline and an escalation. What changed is the *environment*: the delay, the
dose rate, the cabin air and the blood panels are real. The README and the in-app disclaimers
say which is which.

---

## 8. The fetch scripts were re-run to confirm they reproduce the fixtures

On 9 November 2026 all three working scripts were re-run against the live NASA APIs. Each
reproduced its committed fixture byte-for-byte, which confirms the fixtures are real and that
anyone else can regenerate them:

| Script | Result |
| --- | --- |
| `scripts/fetch/horizons.py` | 541 rows (extended on 10 Nov from 401 to reach the 2028 conjunction), `mars_lt.json` 62.5 KB |
| `scripts/fetch/osdr_eda.py` | 21948 CO₂ readings, 1534 spikes dropped (median 3368 ppm), 1720 hourly rows, 76 dose days — identical |
| `scripts/fetch/osdr_i4.py` | 336 values, 12 analytes, 4 subjects (C001–C004) from OSD-575 and OSD-569 — identical |
| `scripts/fetch/donki.py` | Works against `ccmc.gsfc.nasa.gov/DONKI-API`: 11 SEP events, 23 flares, `replay.json` generated |

The DONKI failure was re-confirmed at the very end of the work, not just at the start. The
script tries `api.nasa.gov` first, falls back to the CCMC web service, and reports both
failures precisely rather than exiting quietly.

---

## 9. Open `TODO(verify)` items

| Where | What | Why it is open | What would close it |
| --- | --- | --- | --- |
| `engine/app/catalog.py` | `CONJUNCTION_SOT_DEG = 3.0` | ASTRA's own value derived from the Horizons elongation column, not a quoted NASA limit | Find the NASA / JPL definition of the solar-conjunction warning threshold and quote it, or re-label the warning as an ASTRA judgement in the UI copy |
| `engine/data/nasa/manifest.json` (`osdr-eda-iss`) | ppm → mmHg at 760 mmHg | The EDA does not publish the cabin pressure; the ISS actually runs near 735 mmHg, so the values are ~3% high | Find the EDA or ISS cabin pressure for the RR-7 window and re-run `scripts/fetch/osdr_eda.py` with it |
| `engine/data/nasa/manifest.json` (`donki-sep`) | The DONKI SEP fixture | `api.nasa.gov` 503 → 429 and the old CCMC host timed out (since fixed) | Resolved 9 Nov 2026: fetched from CCMC's current API (see §4.1) |
| `docs/plan/nasa-data-implementation.md` | AstroRad / DLR August 2026 | The URL was never resolved, so no number was quoted | Find a resolvable NASA source; only then implement a reduction factor |

---

## 10. House rules kept

- **Medicine stays in the engine.** Thresholds and classification live in `catalog.py` and
  `rules.py` as pure functions with no I/O. `services.py` does the reading.
- **No new runtime dependencies.** The fetch scripts use the Python standard library only
  (`urllib.request`, `json`, `csv`) and run with `python -I`.
- **Fixtures stay small.** Every committed fixture is under 500 KB:
  `mars_lt.json` 47 KB, `iss_cabin.json` 232 KB, `iss_dose.json` 4.7 KB, `labs.json` 72 KB.
- **House style.** ruff (120 cols) and `tsc --noEmit` and oxlint all clean; CSS modules; colour
  always paired with a text label; plain-language copy.
- **`npm run test`, `npm run lint` and `npm run typecheck` all pass, and `npm run build`
  succeeds.**

---

## 11. How to verify this work

```
npm run test        # 58 engine tests
npm run lint        # oxlint + ruff
npm run typecheck   # tsc --noEmit
npm run build       # the /data and /data/inspiration4 routes are in the output
```

Then, with the engine and the web app running:

1. **/data** — the totals line counts the ready sources, the pending sources, the cited documents.
   Each source card opens "How it was obtained" and shows the manifest note.
2. **/data/inspiration4** — twelve analyte charts, four crew-member lines each, the reference band
   shaded and the flight window marked.
3. **Overview on the station** — the **Cabin air** card shows real ISS CO₂ against the
   NASA-STD-3001 limit, and the cabin-air insight fires because two crew logged a headache.
4. **Overview on Mars** — the **Radiation** card shows the MSL/RAD dose rate and its source.
5. **Crew & comms on Mars** — the Earth link shows the JPL Horizons light time for the mission
   date and the source tag behind it.
6. **Health library** — every hazard, body system and indicator has evidence links, and the
   **Sources** section lists the cited documents by kind.
7. **Settings → Solar particle event** — the button starts the replay of the 28 Oct 2021 event;
   the Overview radiation card turns Act, names the event with a link to the DONKI record, and
   reverts 24 hours later (the extra dose stops accruing when the event ends).

### How this was verified

Each of those seven checks was run against a live engine, not read off the source. The web app was
built with `ENGINE_URL` pointed at a running engine, started with `next start`, and every route
above was fetched as HTML and checked for the NASA content it should carry — the source counts and
the manifest notes on `/data`, the twelve analyte charts on `/data/inspiration4`, the CO₂ number and
the NASA-STD-3001 limit on the Overview cabin card, the MSL/RAD rate on the radiation card, the
Horizons tag on the crew comms panel, the evidence links on `/learn`, and the solar-replay card
in Settings.

The engine's own JSON was checked alongside the pages, and it is the JSON that holds the numbers:

| Endpoint | What it returned |
| --- | --- |
| `GET /nasa/sources` | 9 sources `ready` with `files_ok: true`, 3 official slots `pending` |
| `GET /nasa/cabin?env=station` | CO₂ 2.782 mmHg (1 h), 2.744 mmHg (7 d), limits 3.0 / 2.5, status **Watch**, `source: osdr-eda-iss` |
| `GET /nasa/inspiration4` | `available: true`, 4 subjects, 7 timepoints, 336 points, 12 analytes with the dataset's own reference ranges |
| `GET /comms?env=mars` | `delay_s: 420.23`, `light_time_source: "horizons"` — the exact Horizons row for the mission date |
| `GET /comms?env=station` | `delay_s: 0.5`, `light_time_source: null` — near real-time, so no Horizons tag is shown |
| `GET /nasa/solar/events` | 11 real events, `active: null` until a replay starts |
| `POST /nasa/replay/solar` | 200, event `2021-10-28T16:35:00-SEP-001`, `illustrative: true` |

Two of those checks depend on the mission clock and on the seeded cabin data, so they were run
against a freshly reset database (`POST /admin/reset`) rather than whatever state the demo
database happened to be in. That is why the cabin-air insight fires: it needs two crew members to
have logged a headache within 24 hours, which is why Lucas's day-141 symptoms were changed to
include one.

One note for whoever picks this up next: the environment is read from the **`astra_env` cookie**,
not from a query string. `?env=mars` on a URL does nothing; the env switcher in the top bar sets the
cookie. A check script that forgets this will always read the default (`transit`) and conclude that
the Mars light time is missing.

### A stale engine will not show the new routes

An engine started before this work was in place keeps serving the old route table, and `--reload`
does not always notice: the reloader watched the files it knew about, and the `/nasa/*` routes plus
the new `engine/app/nasa/` package were never picked up by a running worker.

The symptom is specific and worth knowing:

```
GET /openapi.json   -> 15 paths, none containing "nasa"
GET /nasa/sources   -> 404
GET /catalog        -> no metric has a "sources" key
```

The third line is the giveaway: it means the engine is running pre-WP2 code, where no metric
carried a citation at all. Checking the source on disk is not enough — `python -c "import app.main"`
from `engine/` shows the current, correct route table while the server on :8000 still serves the
old one.

**The fix is to restart the engine.** `npm run dev` (or `npm start`) restarts ASTRA Core on :8000
and the web app on :3000; after that, `/nasa/sources` answers and the Data page populates. If the
port will not free itself, kill the uvicorn process by its PID (the reloader is the parent, the
worker its child — kill both) and start it again.

This is worth knowing because the failure is silent and looks like missing data rather than a stale
process: the Data page renders, the source cards are simply not there.

## 12. Fixes after the UI audit (10 Nov 2026)

| Problem found | Fix |
| --- | --- |
| Three different Earth delays on screen (the top bar, Settings and Emergency showed the fixed catalog 760 s while the dashboard showed the Horizons value) | `GET /catalog` now returns each environment through `Engine.env()`, so every page reads the same live delay; the transit tip is computed from it |
| The cabin "7-day average" averaged seven consecutive **hourly** readings, and the 124 constant-200 ppm sensor-fill rows could be read as real air | `Engine.cabin()` groups the series by day, drops rows at or below `CABIN_FILL_PPM`, maps one mission day to one series day, and averages a true 7 days. The seeded demo moment is anchored to `CABIN_DEMO_DATE` (2018-07-24, a real elevated-CO₂ stretch) |
| The radiation status ignored a solar storm in progress | `radiation()` returns Act while the replayed event is active |
| Station dose rate was 0.5 mSv/day in Settings/Learn but the EDA mean (0.29) on the dashboard | `Engine.env()` applies the EDA mean to the station and records `radiation_source` |
| Lunar rover (1.4) and base (0.6) dose rates have no NASA source | Marked `TODO(verify)` in the catalog and shown as "(est.)" in the app; the Overview says it is a planning estimate |
| Inspiration4 reference band came from the first subject only | The band is the widest range; each point carries its own range, and the status is graded against it |
| Inspiration4 flight window was −3…1 days | Now 0…3 days (launch to splashdown) |
| Inspiration4 copy said the crew flew to the ISS | Reworded: it was a free-flying orbital mission and did not dock |
| Evidence links went to `/data#<doc id>` but the cards are `doc-<id>` | `SourceList` links to `#doc-<id>` |

| The cabin and radiation cards had no link to their NASA source | Both cards now carry a `SourceTag` to their `/data` entry (`osdr-eda-iss`, `donki-sep`, and `msl-rad` or `osdr-eda-iss` for the dose rate), and the radiation card links to the DONKI event record |
| The conjunction warning only appeared once the blackout had started | `Engine._conjunction()` has two phases: a Watch warning for the 30 days before the Sun-Mars angle drops under 3 degrees ("Solar conjunction in N days"), then Act for the blackout, with the days left. Settings has a demo control (`POST /clock/skip-to-conjunction`) that skips the clock there, since the 2028 conjunction is about 310 mission days away |
| "Stop and reset" wiped all demo data | New `POST /nasa/replay/solar/stop` stops only the replay and its extra dose; the clock and readings are untouched. Reset demo data keeps its own confirmation |

| Heart rate, blood pressure and breathing were judged on resting ranges even after exercise | Each reading now carries a measurement context (rest, just woke up, after exercise, after an EVA). Post-exertion readings use the metric's `active` bands, skip the personal-baseline comparison and the persistence count, and are left out of the daily status, baseline and trend. Without an answer the engine infers the context from the post-EVA task or an exercise log in the last 30 minutes. The recovery bands are illustrative and marked `TODO(verify)` |

Still open: the two ID schemes (document ids with underscores, manifest ids with hyphens) are
still separate; the Settings and Simulate pages still fail as a whole if one request fails.

## 13. WP8: the official challenge resources (13 Nov 2026)

The challenge's Resources tab lists exactly five resources. The page itself failed TLS verification from
the dev machine, so the list was read through a text-only reader proxy and cross-checked: three NASA
Human Research Program pages and two Canadian Space Agency articles. No dataset, no API.

| Slot | Resource(s) | Role | Fixture | What it changes in the app |
| --- | --- | --- | --- | --- |
| A | NASA HRP *5 Hazards of Human Spaceflight* and *Risks of Human Spaceflight* (plus the five hazard pages they link) | evidence | `official/hrp.json` | Facts, page link and NASA video on each hazard card in the Guide; the **HRP risk map** on `/data/resources` |
| B | NASA *Ongoing HRP Research in Space* (13 studies) | evidence | `official/hrp_research.json` | The research table on `/data/resources` |
| C | CSA *Monitoring Radiation for Astronaut Health* and *Why Do We Conduct Science Experiments in Space?* (plus the Radi-N2, EVARM, MOSFET and infographic pages they link) | evidence | `official/csa.json` | The CSA section on `/data/resources` |

Decisions:

* **Evidence, not thresholds.** None of the five gives a threshold ASTRA did not already have from a more
  specific NASA document, so no catalog band changed. Where they state a number ASTRA already used (bone
  loss 1-1.5% a month, Mars at about 3/8 g), they agree with it; the HRP page's "up to 20 minutes one way"
  matches the Horizons fixture's maximum of 1203.4 s.
* **The CSA neutron numbers are context only.** Neutrons are about 30% of ISS radiation and ISS crews get
  about 150 µSv/day of neutron dose (Radi-N2). They are shown, not added to ASTRA's dose: the station rate
  already comes from a measured dose series and adding a neutron share on top would double count.
* **Transcribed, not scraped.** The pages are prose. Each was read on 13 Nov 2026 and transcribed into the
  fixtures with its own URL; no number appears that the page does not state. `official.py` only reads them.
* **Risk map.** Each of the 17 risks names the ASTRA metrics, body systems and screens that address it, and
  a level: *monitored* (an indicator ASTRA grades), *supported* (guidance or a tool, no body measurement) or
  *partial* (with the gap named). Result: 11 / 4 / 2. The two gaps: no decompression-sickness protocol, and
  no landing-load model. `tests/test_official.py` fails if a fixture names a metric or body system the
  catalog does not have, or if a *partial* risk does not name its gap.
* **Existing citations kept.** The HRP Roadmap entries stay; the 15 new documents (five hazard pages, the
  three index pages, ARCHeR, Standard Measures, five CSA pages) were appended to `sources.py` and to the
  hazard, metric and body-system lists after the existing ids.
* **Filled slots are not simulator scenarios.** `slot_scenarios()` now lists only slots still pending.
