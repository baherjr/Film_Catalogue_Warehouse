# Star schema

## 1. Catalogue scope

**Decision:** The fact holds only films that have details: 7,710 films on 7 Nov (6,829 before the 4 Nov ingest), out of ~1.28M distinct films in the export.

**How films get details:** each details run fetches the top 5,000 non-adult films by popularity in the latest export snapshot (`slice.py`, `--limit` default 5000), and the catalogue is every film any run has fetched. So `is_adult` is false in `dim_movie` unless TMDB reclassifies a film after its fetch.

**Why:** This is a film catalogue warehouse. A fact row whose film has no title, release date, genres, companies or credits can't be analysed alongside anything else, so it adds rows without adding questions it can answer.

**Consequence for `dim_movie`:** Every film in the fact has a full `dim_movie` row, so the fact → `dim_movie` relationship holds by construction. No "unknown" member is needed.

**Row count (4 Nov, before that day's ingest):** 643,285 rows = 6,829 films across 96 snapshot days (1 Aug – 4 Nov 2026, no gaps).

- A full rectangle would be 6,829 × 96 = 655,584. The 12,299 missing film-days (1.9%) are days a film was absent from the export, mostly films added to TMDB after 1 Aug. This is real absence, not a load gap.
- After the 4 Nov ingest (874 new films): **725,373 rows** = 7,703 films across the same 96 days. The full rectangle would be 7,703 × 96 = 739,488, so 14,115 film-days (1.9%) are absent, the same rate as before.

**Late-arriving films:** Membership means *has details today*. When a film is fetched for the first time, its full popularity history back to 1 Aug joins the fact.

- Why: a film enters the top 5,000 because its popularity rose, and that rise happened before it was fetched. Freezing history at the fetch date would cut it off.
- Cost: past snapshot dates gain rows whenever new films are fetched. This is Kimball's late-arriving dimension. The fact is a full-refresh table until week 6; the week 6 incremental model must insert new dates **and** the full history of films new to `dim_movie` since the last run.
- History only goes back to 1 Aug, where the export backfill starts. TMDB keeps export files for about 3 months, so older dates can't be added.

**Known gap (open, fix planned):** No details were fetched between 24 Oct and 4 Nov while exports kept loading. The 4 Nov ingest caught films in that day's top 5,000, but films that were in the top 5,000 only on some day from 25 Oct to 3 Nov are still missing. Fix: slice selection over the union of the top 5,000 across a date range.

## 2. `fct_movie_popularity_daily`

### Grain

One row per film with details per day that the film appears in TMDB's daily movie ID export.

### Fact table type

**Periodic snapshot.** Each daily export is a full snapshot of every film's popularity at that date, and a row exists because a day passed, not because something happened to the film. It isn't a transaction fact: a popularity score is a state TMDB recalculates every day, not an event with its own timestamp. It isn't an accumulating snapshot either: there's no lifecycle with milestone dates (such as announced → released → on streaming) that one row per film updates as it moves through.

### Measures

| Measure | Source | Additivity |
|---|---|---|
| `popularity` | export | **Non-additive** |
| `popularity_rank` | derived (see below) | **Non-additive** |

`popularity` is the only numeric fact in the export, and it can't be summed along any dimension:

- **Across days:** a film with 50 on Monday and 50 on Tuesday doesn't have 100 popularity. Each day's score is a fresh, unitless index, not a count of anything that happened that day. That alone rules out additive.
- **Across films:** it isn't semi-additive either (summable across films but not time, like an account balance). A genre's summed popularity mostly measures how many films the genre has, so a genre with many obscure films can outscore one with a few hits. The sum has no unit and no meaning.

Summarise it with `AVG`, median, `MAX`, or rank instead, and compare films within the same day or one film's trend over time.

The other export columns aren't measures. `adult`, `video` and `original_title` describe the film, so they go in the movie dimension. `vote_count` and `vote_average` from the details payload don't belong here either: each film's details are frozen at first fetch, so repeating them on every daily row would present one old value as a daily series.

### Derived measures

**`popularity_rank` is stored in the fact**, computed as `RANK() OVER (PARTITION BY snapshot_date ORDER BY popularity DESC)`. Tied films share a rank.

- **The rank is computed over the whole export (~1.25M films a day) *before* the scope filter.** A rank of 40 means 40th of every film TMDB lists that day, not 40th of our catalogue. The model ranks `stg_tmdb__movie_ids_daily` first, then joins to the films with details.
- Because the rank comes from the full export, it doesn't depend on which films are in the catalogue. A late-arriving film's backfilled history gets the same ranks it would have had if it had been fetched on day one, and existing rows never change when new films join.
- It depends only on rows from the same `snapshot_date`, and a reload replaces the whole date, so the stored value can't go stale.
- Computing it at query time would mean ranking ~1.25M rows for every day queried; a one-film rank trend over 96 days would rank ~120M rows to return 96. Stored, it's a filter.

Day-over-day change in popularity or rank stays at query time (`LAG` over `snapshot_date`). It depends on the previous row existing, and a film that's missing from one day's export would need a gap rule each analysis may want to set differently.

### Foreign keys

- **Movie version** → `dim_movie.movie_version_key`: the version valid on `snapshot_date` (point-in-time, section 4)
- **Movie (durable)** → `movie_id`, also kept on the fact so current-version questions and the bridges don't need the version key (section 3)
- **Date** → `dim_date.date_day`, from `snapshot_date`

Genre, company and person aren't direct keys: a film has several of each, so they're reached from `dim_movie` through the genre, company and cast/crew bridges (section 4). Key choices are in section 3.

### Source and materialisation

- **Source:** `stg_tmdb__movie_ids_daily` for the rows, popularity and rank; `stg_tmdb__movie_details` (`where is_latest`) for the scope filter.
- **Materialisation:** table. The fact itself is small (~725k rows), but the rank window runs over the full ~120M-row export, which is far too expensive to recompute on every query through a view. Full refresh until week 6, then incremental by `snapshot_date` plus the late-arriving backfill from section 1.

### Tests

- `dbt_utils.unique_combination_of_columns` on (`movie_id`, `snapshot_date`): the grain.
- `not_null` on `movie_version_key`, `movie_id`, `snapshot_date`, `popularity`, `popularity_rank`.
- `relationships` from `movie_version_key` to `dim_movie`, from `movie_id` to `dim_movie`, and from `snapshot_date` to `dim_date`.
- A singular test that each fact row's version is valid on its `snapshot_date` (`valid_from::date <= snapshot_date < coalesce(valid_to::date, '9999-12-31')`).
- A singular test that the fact's distinct `movie_id` count equals the latest details count: the scope rule from section 1.

### Predicted row count

**725,373 rows** (7,703 films, after the 4 Nov ingest; 643,285 before it). It grows by roughly the catalogue size per daily load (~7,700 rows/day), plus each new film's backfilled history.

For context, the full export is 119,681,805 rows across 96 dates and 1,282,121 distinct films; the fact keeps about 0.6% of it.

## 3. Dimensions

### Key policy

**A surrogate key only where the dimension tracks history.** `dim_movie` is the only Type 2 dimension, so it's the only one where the natural key can't identify a row. Every other dimension uses TMDB's own id.

- TMDB ids are stable integers from a single source, and the other dimensions are Type 1, so one id always means one row. A surrogate there would add a lookup on every build and protect against nothing.
- Kimball's default is surrogates everywhere, to insulate the warehouse from source key changes and to merge sources. Neither applies yet. If a second film source is ever added, this decision is revisited.
- **`dim_movie`'s surrogate is a hash, not a sequence.** `generate_surrogate_key` gives the same key for the same (`movie_id`, `valid_from`) on every build. The fact is a table that stores the key, so a sequence would renumber versions on each full refresh of `dim_movie` and silently break every stored fact row. The cost is a 32-character text key instead of an integer. On a ~725k-row fact that's about 25 MB, which doesn't matter at this size.

| Dimension | Grain | Key | Surrogate? | Source | Rows (7 Nov) |
|---|---|---|---|---|---|
| `dim_movie` | one row per film version | `movie_version_key` (durable: `movie_id`) | **Yes** | `stg_tmdb__movie_details`, `stg_tmdb__movie_ids_daily` | 7,710 (one version each) |
| `dim_company` | one row per production company | `company_id` | No | `stg_tmdb__movie_companies` | 8,554 |
| `dim_person` | one row per person | `person_id` | No | `stg_tmdb__movie_cast` + `stg_tmdb__movie_crew` | 386,226 |
| `dim_genre` | one row per TMDB movie genre | `genre_id` | No | seed `tmdb_genres.csv` | 19 |
| `dim_date` | one row per calendar day | `date_day` | No | `dbt_utils.date_spine` | 58,804 |

All five are tables in the `marts` schema. They're small, and the fact build and bridges join to them, so a view would recompute them on every build.

### `dim_movie`

- **Grain:** one row per film per period in which `status`, `runtime`, `budget` and `revenue` were unchanged.
- **Keys:** `movie_version_key` = `dbt_utils.generate_surrogate_key(['movie_id', 'valid_from'])`, unique per row. `valid_from` is a timestamp (the version's first `fetched_at`), so two versions fetched on the same day still get different keys. `movie_id` is the durable key: the same on every version of a film.
- **Why both keys:** the fact needs the version key to pick the version valid on its date (section 4). It also keeps `movie_id`, so "today's status" or "today's genres" is a plain join on `movie_id` with `is_current`, without resolving versions. This is Kimball's Type 7 pattern: the fact carries both keys.
- **Columns:**
  - Keys: `movie_version_key`, `movie_id`
  - Type 2: `status`, `runtime`, `budget`, `revenue`
  - Type 1: `title`, `original_title`, `original_language`, `imdb_id`, `release_date`, `is_adult`, `is_video`, `vote_count`, `vote_average`, `details_fetched_at`
  - Validity: `valid_from`, `valid_to` (NULL on the current version), `is_current`
- **`release_date` is a second role of `dim_date`.** It's a Type 1 column that joins to `dim_date.date_day` for year, decade or day-of-week analysis of releases. It's nullable: 50 catalogue films have no release date, and they keep NULL rather than pointing to an "unknown" date row.
- **Source:** versions are built from the payload history in `stg_tmdb__movie_details`, not a dbt snapshot (section 4). Type 1 columns come from the latest details row, and the export flags from the film's latest row in `stg_tmdb__movie_ids_daily`.
- **Tests:** `unique` and `not_null` on `movie_version_key`; `dbt_utils.unique_combination_of_columns` on (`movie_id`, `valid_from`); a singular test that each `movie_id` has exactly one `is_current` row; a singular test that a film's validity ranges don't overlap; a singular test that each film's first version starts at `2026-08-01 00:00 UTC` (the backdating rule from section 4); `relationships` from `release_date` to `dim_date`.

### `dim_company`

- **Grain:** one row per production company credited on at least one catalogue film.
- **Key:** `company_id`.
- **Columns:** `company_id`, `company_name`, `origin_country`.
- **Source:** `stg_tmdb__movie_companies`, one row per `company_id`, keeping the name and `origin_country` from the most recently fetched film (`row_number() over (partition by company_id order by fetched_at desc, movie_id desc)`, with `fetched_at` joined from the latest details row). A plain `distinct` isn't safe: TMDB can send two spellings for one id (1 company on 7 Nov, the Jadran case), and `distinct` would give it two rows. `movie_id` breaks ties between films fetched at the same moment, so the pick is the same on every build.
- **Type 1:** a renamed company shows its current name on every film. Company history isn't a question this warehouse asks.
- **Tests:** `unique` and `not_null` on `company_id`. `assert_one_name_per_company` returns companies with more than one name in staging, with `severity: warn`: the conflicts come from TMDB and the model resolves them, but a jump in the count should be seen.

### `dim_person`

- **Grain:** one row per person credited in the cast or crew of at least one catalogue film.
- **Key:** `person_id`.
- **Columns:** `person_id`, `person_name`, `known_for_department`.
- **Source:** the union of people from `stg_tmdb__movie_cast` and `stg_tmdb__movie_crew`, one row per `person_id`.
- **The risk:** a person's name or `known_for_department` can differ between credits, because each credit was fetched with a different film, possibly on a different date. On 7 Nov, 156 of 386,226 people have more than one name and 20 have more than one `known_for_department` (no one has both). A plain `distinct` would give those people two rows. The model keeps the values from the most recently fetched film (`row_number() over (partition by person_id order by fetched_at desc, movie_id desc)` over the `union all` of cast and crew credits, with `fetched_at` joined from the latest details row, since the cast and crew models don't carry it), so the attributes are always the latest TMDB value. Type 1.
- **`known_for_department` comes from both cast and crew credits.** 218,458 people (57%) appear only in crew, so taking it from cast alone would leave them with a NULL department.
- **Tests:** `unique` and `not_null` on `person_id`. A singular test, `assert_person_attributes_consistent`, returns people whose name or `known_for_department` differs across credits, with `severity: warn`. It returns 176 people on 7 Nov (156 name conflicts + 20 department conflicts). These conflicts come from TMDB, not from the warehouse, so they shouldn't fail the build, but a sudden jump in the count should be seen.

### `dim_genre`

- **Grain:** one row per TMDB movie genre.
- **Key:** `genre_id`.
- **Columns:** `genre_id`, `genre_name`.
- **Source:** a seed, `tmdb_genres.csv`, with TMDB's 19 movie genres, not `distinct` over staging. Only a seed can list a genre that no catalogue film has, which is the reason section 4 gives for having this dimension at all. The existing `accepted_values` test on `stg_tmdb__movie_genres.genre_id` already holds the same 19 ids, so the two must stay in sync.
- **Tests:** `unique` and `not_null` on `genre_id`; `relationships` from the genre bridge to it.

### `dim_date`

- **Grain:** one row per calendar day.
- **Key:** `date_day` (a `date`). Kimball often uses an integer `yyyymmdd` key, but Postgres stores a `date` in 4 bytes, it joins directly to `snapshot_date` and `release_date` with no conversion, and it reads as itself.
- **Range:** 1 Jan 1870 to 31 Dec 2030, 58,804 rows. The fact only needs 1 Aug 2026 onward, but `dim_date` also plays the `release_date` role. Catalogue release dates currently run from 15 Jun 1902 to 15 Mar 2028 (58 films have dates in the future), and 1870 covers TMDB's earliest films as the catalogue grows. One wide range serves both roles and costs nothing at this size. The `relationships` test from `release_date` fails as soon as a film is dated past 2030, which is the signal to extend the range.
- **Columns:** `date_day`, `year`, `quarter`, `month`, `month_name`, `iso_year`, `iso_week`, `day_of_week` (ISO, Monday = 1), `day_name`, `is_weekend`.
- **Source:** `dbt_utils.date_spine`.
- **Tests:** `unique` and `not_null` on `date_day`; a singular test that the row count equals the number of days in the range (no gaps).

## 4. Bridges and history

### Bridges

| Bridge | Grain | Keys | Role attributes | Source |
|---|---|---|---|---|
| `bridge_movie_genre` | One row per film per genre | `movie_id` → `dim_movie`, `genre_id` → `dim_genre` | none | `stg_tmdb__movie_genres` |
| `bridge_movie_company` | One row per film per production company | `movie_id` → `dim_movie`, `company_id` → `dim_company` | none | `stg_tmdb__movie_companies` |
| `bridge_movie_cast` | One row per cast credit: one person playing one part in one film | `movie_id` → `dim_movie`, `person_id` → `dim_person`; `credit_id` identifies the row | `character_name`, `billing_order` | `stg_tmdb__movie_cast` |
| `bridge_movie_crew` | One row per crew credit: one person doing one job on one film, so a person can have several rows for one film | `movie_id` → `dim_movie`, `person_id` → `dim_person`; `credit_id` identifies the row | `department`, `job` | `stg_tmdb__movie_crew` |

- **Latest version only.** Every bridge comes from each film's latest details payload (`is_latest`), matching staging. Bridges join `dim_movie` on `movie_id`, the durable key, not on a version key, so a film's genres, companies and credits are always its current ones, whichever version a fact row points to.
- **`dim_genre` exists** instead of keeping the name on the bridge. TMDB's 19-genre list is fixed, so either would work, but a separate dimension keeps every bridge the same shape (two keys, two dimensions), stores each name once, and lets a report list all 19 genres, including any that no catalogue film has. At 19 rows it costs nothing.
- **Cast and crew get two bridges, not one.** Their role attributes are different, so a combined bridge would leave half its columns NULL on every row and need a `role_type` filter in every query. Both point to one shared `dim_person`. The role attributes belong on the bridge, not on `dim_person`, because they describe the person's role on one film, not the person.
- **Counting through a bridge counts a film once per member.** Per-genre or per-company averages are what we want. Grand totals summed across genres count each film several times.

### History on `dim_movie`

| Treatment | Columns |
|---|---|
| **SCD Type 2 (tracked)** | `status`, `runtime`, `budget`, `revenue` |
| **Type 1 (overwritten)** | `title`, `original_title`, `original_language`, `imdb_id`, `release_date`, `is_adult`, `is_video`, `vote_count`, `vote_average`, `details_fetched_at` |
| **Not on `dim_movie`** | genres, companies, credits: on the bridges, from the latest version, so in effect Type 1 |

- **Type 1 columns are corrections or current-state values.** An analysis wants a corrected title or release date on every date. (`overview` isn't in staging yet. If it's added, it's Type 1.)
- **Votes are Type 1**, with `details_fetched_at` next to them so readers know how old they are. Votes change almost every day for popular films, so tracking them would open a new version on nearly every refetch, the problem flagged in week 3, and bury the real status, budget and revenue changes. If vote history is ever needed, it's a measure over time and belongs in a periodic snapshot fact.

#### How versions are built: from staging history

`raw.movie_details` is append-only and keeps every payload version a film has had, and `stg_tmdb__movie_details` exposes all of them. `dim_movie` builds its versions from that history in an ordinary model. It doesn't use a dbt snapshot.

1. Order each film's payloads by `fetched_at`.
2. Start a new version only when one of the four tracked columns differs from the previous payload, compared with `IS DISTINCT FROM` so a NULL-to-value change counts. A payload that only changes a title or the votes doesn't open a version.
3. `valid_from` is the `fetched_at` of the version's first payload. The film's **first** version is backdated to `2026-08-01 00:00 UTC`, the start of the export history, so a late-arriving film's backfilled history (section 1) has a version to join to before its first fetch.
4. `valid_to` is the next version's `valid_from`, or NULL on the current version. `is_current` is `valid_to IS NULL`.
5. Type 1 columns come from the latest details row and the film's latest export row, joined on `movie_id`, so every version shows the current values.

Why this instead of a dbt snapshot:

- **It's rebuildable.** The history lives in raw, so `dim_movie` can be dropped and rebuilt with the same versions. A snapshot keeps its own copy of the history outside raw, and that copy can't be rebuilt if it's lost.
- **Versions are dated by when TMDB's data was fetched**, not by when a dbt job happened to run.
- **Backdating the first version is one `case` expression** in the model, not a fix applied to snapshot output afterwards.
- **Only the four tracked columns open a version.** That's the job `strategy: check` with `check_cols` would do, done explicitly in step 2.

Materialised as a table, full refresh. At 7,710 films the version logic is cheap; the build takes about 3 minutes, almost all of it picking each film's latest export flags from the ~120M-row export view.

#### How the fact joins a versioned dimension: point-in-time

**A fact row joins to the version of the film that was valid on its `snapshot_date`.** A row for 15 Aug carries the `movie_version_key` of the 15 Aug version. This is why section 3 gives `dim_movie` a surrogate key: `movie_id` alone can't pick a version.

- **Why:** the questions are about how popularity moves as a film changes. Popularity while a film was "Post Production" versus after "Released", or before and after its revenue grew, needs each day to see the attributes it really had. Joining on `movie_id` to the current version would label every past day with today's status and revenue, which is what SCD2 is meant to prevent.
- **Current-version questions still work:** the fact also keeps `movie_id`, and `dim_movie` has `is_current`, so "today's genres" or "today's status" is a join on the durable key (Type 7, section 3).
- **The key is resolved when the fact is built**, not at query time: `valid_from::date <= snapshot_date < coalesce(valid_to::date, '9999-12-31')`. If two versions start on the same day, the earlier one gets an empty range and the later one wins.
- **Versions are dated by when a change is fetched, not when TMDB made it.** Once the change feed refetches changed films daily, that's at most a day late, which matches the fact's daily grain.

#### Limitation

Until the change feed exists (week 6), details are a single snapshot per film, taken 15 Oct (19 Oct, 24 Oct or 4 Nov for films that joined later), so `dim_movie` has exactly one version per film and the point-in-time join gives the same result as a current-version join.
