# DataLens — Project Specification & Build Plan

This file is the authoritative spec for the DataLens project. It captures the full
requirements given by the user so that work can continue correctly across sessions.
**Do not delete this file.** Update the "Phase Status" section as phases complete.

## Phase Status

- [x] Phase 1: Foundation — project scaffolding, FastAPI + Next.js communication,
  health check
- [x] Phase 2: CSV ingestion — upload, validation, encoding detection, safe
  storage, profiling engine, tests
- [x] Phase 3: Data quality engine — explainable 0-100 quality score and
  descriptive statistics engine, tests
- [x] Phase 4: Exploratory visual analytics and correlation analysis
- [x] Phase 5: Data cleaning and transformations (versioned working copy, explicit operations, Clean tab)
- [x] Phase 6: Before/after comparison, transformation history, and cleaned
  CSV export (undo deliberately not implemented; see Phase 6 Decisions)
- [x] Phase 7: Final polish — sample datasets, documentation, deployment
  readiness, demo preparation, portfolio/interview documentation (feature-complete)

**Rule: do not proceed to the next phase until the user explicitly says to continue.**

---

## Context & Purpose

Portfolio project for a Software Engineering master's graduate with a Data Science
specialization, meant to be demoed live in interviews. Primary purpose: demonstrate
strong practical Python engineering, data analysis, data quality, statistics,
FastAPI/backend development, Pandas, NumPy, testing, and full-stack integration
with Next.js.

**Explicit product decision:** DataLens does **not** include machine-learning-based
anomaly detection (no Isolation Forest, no scikit-learn, no ML anomaly scoring).
The user maintains separate ML-focused projects and does not want ML forced into
this one. Ordinary statistical/data-analysis techniques (Pearson/Spearman
correlation, quartiles, IQR, histograms, descriptive statistics, and potentially
simple statistical outlier detection) are **not** machine learning and remain
in scope where they provide clear product value — see "Explicitly Out of Scope"
below for exactly what was cut and why.

**Critical constraint:** All actual data analysis (CSV processing, profiling,
statistics, data quality, cleaning, correlations) MUST be done in Python.
Next.js/TypeScript is UI only — it must NOT reimplement analysis logic or compute
statistics client-side. Not a Jupyter notebook — a real production-style web app.

## Tech Stack

**Backend:** Python 3.11, FastAPI, Pandas, NumPy, SciPy (as needed for statistical
helpers), SQLAlchemy, SQLite, Pydantic, pytest, Uvicorn.

**Frontend:** Next.js, TypeScript, Tailwind CSS, Recharts (or similar), responsive UI.

**Other:** Git, requirements.txt or pyproject.toml, .env.example, README.md,
proper .gitignore. No Docker, no cloud services — everything runs locally on Windows.

Environment: Python 3.11.5, Node.js 25.2.1, npm 11.6.2, Git 2.42.0.

## Application Purpose

User uploads an arbitrary CSV and the app automatically: profiles its structure,
evaluates data quality with an explainable score, generates descriptive statistics,
visualizes distributions, analyzes correlations between columns, and lets the user
clean/transform the data, compare before vs after, and export the cleaned CSV. Must
work with arbitrary CSVs, not hardcoded for one sample dataset.

## Product Workflow

```
CSV Upload
  → Validation / Encoding Detection
  → Dataset Profiling
  → Data Quality Analysis
  → Descriptive Statistics
  → Visual Exploration
  → Correlation Analysis
  → Data Cleaning / Transformations
  → Before vs After Comparison
  → Export Cleaned CSV
```

## User Flow

Landing Page → Upload CSV → Validate → Python analyzes → Analysis Dashboard →
Explore Data → Review Data Quality Issues → Clean/Transform → Re-run Analysis →
Compare Before vs After → Export Cleaned CSV.

## Landing / Upload Page

- Product name "DataLens", tagline "Turn raw datasets into actionable insights."
- Drag-and-drop upload, file picker, progress/status, validation with helpful errors,
  sample dataset option.
- Validate: extension, empty files, malformed CSV, file size, parsing errors.
- After upload show: file name, size, rows, columns. Then allow starting analysis.

## Dataset Profiling Engine (Python, `services/profiler.py`) — COMPLETE (Phase 2)

Determine: row count, column count, column names, inferred dtypes, numerical/
categorical/boolean/datetime columns, missing value count & %, unique values,
duplicate rows, memory usage, sample values.

Numerical columns: count, mean, median, std, variance, min, max, p25, p50, p75, range.

Categorical columns: unique count, most frequent value + its frequency, top-value
distribution. Be careful with high-cardinality columns.

CSV ingestion also includes: streaming upload with a configurable size limit, safe
UUID-based on-disk storage (never trusting the uploaded filename), and text-encoding
detection (UTF-8/UTF-8 BOM preferred, Windows-1252/ISO-8859-1 fallback via
`charset-normalizer` with a confidence check, rejecting undetectable/binary content
rather than guessing).

## Data Quality Engine (Python, `services/quality.py`) — COMPLETE (Phase 3)

Detects: missing/null values, blank strings, duplicate rows, constant columns,
mostly-empty columns, infinite numeric values, mixed/inconsistent data types within
a column, high-cardinality categorical columns, and potential identifier columns.

**Explainable Data Quality Score 0-100**, implemented with clearly defined,
documented scoring rules (not arbitrary):

- The score starts at 100.
- Each *category* of problem computes a penalty proportional to how prevalent it
  is (e.g. missing values lose ~1 point per 1% of all cells missing), using a
  fixed, documented rate.
- Each category's penalty is capped to a per-category maximum, so one dominant
  problem — or the same minor issue repeated across many columns — can never
  single-handedly destroy the score.
- Penalties are whole numbers, computed once and reused for both the displayed
  breakdown and the score itself, so the breakdown always sums to exactly
  `100 - score`.
- High-cardinality/identifier-column detection is informational only (zero
  penalty) — e.g. an order-ID column being 100% unique is normal, not a defect.

API returns overall score + score breakdown + list of issues, each with: type,
column (nullable — dataset-wide issues like duplicate rows have no column),
severity, affected_rows, percentage, message/explanation, suggested action. Full
rationale documented in `services/quality.py`'s module docstring and in this
repo's README.

## Statistics Engine (Python, `services/statistics.py`) — COMPLETE (Phase 3)

Independent of the lighter profiler; computes the fuller, type-appropriate
statistical breakdown for a dedicated Statistics view:

- Numeric: count, missing count, mean, median, std, variance, min, max, range,
  p25/p50/p75, IQR.
- Categorical: count, missing count, unique count, most frequent value + count,
  top values.
- Boolean: count, missing count, true/false counts, true percentage.
- Datetime: valid count, missing count, earliest, latest, range (days).

## Correlation Analysis (Python, `services/correlations.py`) — COMPLETE (Phase 4)

Pearson and Spearman via `DataFrame.corr` (pairwise-complete observations). Numeric
columns only; constant and too-sparse columns are excluded with a stated reason;
fewer than two usable columns returns a clear 422. Pairs with |r| ≥ 0.7 are listed as
strong relationships. Every response carries a "correlation does not establish
causation" disclaimer. Coefficients are rounded to 6 decimals and JSON-safe.

## Visualization Engine (Python, `services/visualizations.py`) — COMPLETE (Phase 4)

Python computes chart-ready data; Next.js only renders it. Each chart has its own
endpoint and validates column existence, column kind, and parameter ranges.

- Histogram: NumPy bins (default "auto" rule, capped at 100 bins), counts only.
- Categorical frequency: Top N (default 20, max 100) with the rest grouped as "Other";
  percentages; deterministic ordering.
- Scatter: at most 2,000 points from a seeded random sample (reproducible); the
  Pearson r reported is computed on all usable rows, not the sample.
- Distribution summary: min, Q1, median, Q3, max, IQR (box plot drawn as custom SVG).
- Datetime trend: mean/min/max/count per calendar period; the finest period
  (day → year) keeping the chart at or under 120 points is chosen automatically.

Scope note: these are descriptive views only — no outlier flagging or ML.

## Analysis Dashboard — Explore tab (Phase 4)

Explore tab contains: statistics glossary, correlation heatmap (Pearson/Spearman
toggle), histogram, categorical frequency, scatter plot (X/Y selectors), distribution
box plot, datetime trend. Column selectors only offer compatible column kinds.

## Analysis Dashboard

Top summary cards: Rows, Columns, Missing Values, Duplicates, Data Quality Score.
Tabs: Overview, Columns, Data Quality, Statistics, Visualizations, Correlations,
Cleaning, History.

Overview: dataset info, quality score, key warnings, column type breakdown, quick
stats. Columns tab: click a column → inferred type, missing values, unique values,
statistics, distribution, sample values.

## Data Cleaning (Python, `services/cleaner.py`) — COMPLETE (Phase 5)

Missing numerical: remove rows / mean / median / custom value.
Missing categorical: remove rows / mode / custom value.
Other ops: remove duplicates, drop column, rename column, safe dtype conversion,
trim whitespace, standardize blank/null values, basic categorical normalization
(e.g. "California" / " california " / "CALIFORNIA" → one value), only when
explicitly requested. **Never silently modify data — every transformation is
user-initiated.**

## Transformation History — COMPLETE (Phase 6)

Ordered log of every applied step, read from the `transformations` table and shown on
the Compare & Export tab (e.g. "Removed 2 duplicate row(s)", "Renamed "hire_dt" to
"hire_date""). Undo is not implemented; see Phase 6 Decisions.

## Before vs After Comparison — COMPLETE (Phase 6)

Compare & Export tab: original (version 0) vs current working version, for rows, columns,
missing values, duplicate rows, and quality score, with changes. Operation totals (rows
removed, duplicates removed, values filled, text rows changed, columns dropped and renamed)
come from the recorded history. "Values modified" is intentionally not reported. See
Phase 6 Decisions.

## Export — CSV COMPLETE (Phase 6); JSON not implemented

Cleaned CSV download of the current working version. Analysis-results JSON export was
optional and was not built. Structure backend so PDF/HTML reporting could be added later,
but don't overbuild now.

## Explicitly Out of Scope

- **ML-based anomaly detection** (Isolation Forest, scikit-learn, or any other ML
  model). This was in earlier drafts of this spec as a planned Phase 5
  ("Outlier + anomaly detection") but has been deliberately removed as a product
  decision — the user maintains separate ML-focused portfolio projects and wants
  DataLens to stay focused on practical data engineering/analysis/statistics
  instead of forcing in ML for its own sake.
- **Statistical outlier detection** (IQR/Z-score based `services/outliers.py`, an
  `/outliers` endpoint, and an "Outliers" summary card) is similarly not a
  committed feature. It is not machine learning and could be added later if it
  provides clear product value, but should not be added merely to replace the
  removed ML feature.

## Database (SQLite + SQLAlchemy)

Persist metadata only — not raw CSVs in SQLite. Store working files on disk under a
data directory, referenced via UUID (never trust uploaded filenames).

Tables (guideline, can be refined):
- **Dataset** (`models/dataset.py`, Phase 2; `working_version` added Phase 5):
  id (UUID string), original_filename, stored_filename (`{id}.csv`, the original),
  upload_timestamp, row_count, column_count (both describe the *current* working
  dataset), file_size_bytes (original upload size), encoding (display label),
  encoding_codec (Python codec used to re-read the original), working_version
  (0 = analysis uses the original; N = analysis uses `{id}.v{N}.csv`).
  Databases created before Phase 5 are migrated in `init_db` by adding
  `working_version` with default 0.
- **Transformation** (`models/transformation.py`, Phase 5, internal): id (integer
  autoincrement), dataset_id (FK → datasets.id, indexed), version (the working version
  this step produced), operation, column (nullable), parameters (validated request as
  JSON text, without the `operation` key), affected_rows, rows_before, rows_after,
  timestamp (UTC). Written only by the cleaning path; read only by
  `GET /transformations` and the comparison's operation totals (Phase 6).
- **AnalysisRun** — not implemented. Quality and statistics are computed per request
  from the current version and never persisted.

## API Design (FastAPI)

Implemented so far:

```
POST   /api/datasets/upload
GET    /api/datasets
GET    /api/datasets/{id}
DELETE /api/datasets/{id}

GET    /api/datasets/{id}/profile
GET    /api/datasets/{id}/quality
GET    /api/datasets/{id}/statistics
```

Phase 4 (implemented):

```
GET    /api/datasets/{id}/correlations?method=pearson|spearman
GET    /api/datasets/{id}/visualizations/histogram?column=&bins=
GET    /api/datasets/{id}/visualizations/categorical?column=&top_n=
GET    /api/datasets/{id}/visualizations/scatter?x=&y=
GET    /api/datasets/{id}/visualizations/distribution?column=
GET    /api/datasets/{id}/visualizations/datetime-trend?datetime_column=&value_column=
```

Phase 5 (implemented):

```
POST   /api/datasets/{id}/clean
```

The clean endpoint takes a JSON body discriminated on `operation`, with one strict
model per operation (`fill_missing`, `remove_duplicates`, `normalize_text`,
`drop_columns`, `rename_column`, `convert_type`). Responses: `TransformationResult`
(200), or an error from the shared hierarchy: 404 unknown dataset, 409 no-op, 400
invalid parameter, 422 incompatible type / invalid conversion / invalid request
body, 500 write failure (dataset unchanged).

Phase 6 (implemented, all read-only):

```
GET    /api/datasets/{id}/comparison        original (v0) vs current metrics + operation totals
GET    /api/datasets/{id}/transformations   applied-step history, oldest first
GET    /api/datasets/{id}/export            current working CSV as a download
```

Export responses are `text/csv` with `Content-Disposition: attachment; filename="<stem>_cleaned.csv"`
after changes, or `<stem>_original.csv` when nothing has been applied. The stem is limited to
letters, digits, `.`, `_`, and `-`, and is at most 100 characters.

Every request/response for these endpoints keeps the current error shape:
`{"error": "<ExceptionName>", "message": "<readable text>"}`. Request validation errors
add a `details` array. Phase 6 adds `DatasetFileMissingError` and `CorruptHistoryError`
(both 500), for a missing version file or an unreadable stored history row.

Use proper HTTP status codes, Pydantic request/response models, centralized error
handling, validation, and working Swagger docs at `/docs`.

## Python Architecture

```
backend/
  app/
    main.py                      app factory: CORS, exception handlers, routers
    api/
      dependencies.py            get_dataset_or_404, load_dataframe (version-aware)
      errors.py                  readable request-validation summaries
      routes/
        health.py                GET /api/health
        datasets.py              upload, list, get, delete, profile, quality, statistics
        analysis.py              correlations + /visualizations/* (Phase 4)
        cleaning.py              POST /clean (Phase 5)
        review.py                comparison, transformations, export (Phase 6, read-only)
    core/
      config.py                  pydantic-settings (DATALENS_* env vars)
      exceptions.py              DataLensError hierarchy (status code per class)
      sanitize.py                safe_float, safe_coefficient, to_json_safe
      column_kind.py             numeric / categorical / boolean / datetime inference
      numeric.py                 clean_numeric_series, numeric_values, parse_datetime_values
    db/session.py                engine per settings, get_db, init_db (+ migration)
    models/
      database.py                shared declarative Base
      dataset.py                 Dataset
      transformation.py          Transformation (Phase 5)
    schemas/
      dataset.py, analysis.py    dataset metadata; profile
      quality.py, statistics.py  Phase 3
      correlations.py            Phase 4
      visualizations.py          Phase 4
      cleaning.py                Phase 5 request union + TransformationResult
      history.py                 Phase 6 history schema (TransformationRecord)
      comparison.py              Phase 6 comparison schema
    services/
      csv_service.py             validation, streaming save, read_dataframe
      encoding_service.py        UTF-8 / BOM / Windows-1252 / ISO-8859-1 detection
      profiler.py                Phase 2 profile
      quality.py                 Phase 3 quality score + issues
      statistics.py              Phase 3 statistics
      correlations.py            Phase 4
      visualizations.py          Phase 4 chart data
      cleaner.py                 Phase 5 pure transformations
      transformations.py         Phase 5 locking, atomic writes, version pointer
      history.py                 Phase 6 history read-back and display sentences
      comparison.py              Phase 6 original-vs-current metrics and operation totals
      exporter.py                Phase 6 export source file and safe filenames
  tests/                         test_health, test_csv_service, test_encoding_service,
                                 test_sanitize, test_profiler, test_quality,
                                 test_statistics, test_correlations, test_visualizations,
                                 test_analysis_api, test_cleaner, test_cleaning_api, test_api,
                                 test_comparison_api, test_history_api, test_export_api
```

Exact structure may evolve with good reason. Avoid giant files.
Use type hints, docstrings where useful, clear naming, classes only where they add
value, Pythonic design, separation of concerns.

## Testing (pytest)

Meaningful tests only — not padding. Cover: normal CSV, empty CSV, malformed CSV,
encoding detection (UTF-8/BOM/legacy/undetectable), missing values, duplicates,
numerical/categorical/mixed data, data quality scoring (including score bounds and
breakdown-sums-to-score), statistics (numeric/categorical/boolean/datetime),
JSON-safety (NaN/Infinity), cleaning transformations (Phase 5), API upload/analysis,
and 404/error responses.

## Sample Datasets — COMPLETE (Phase 7)

Generated deterministically by `sample_data/generate_sample_data.py` (fixed seed 42; same
output bytes on every run). The committed CSVs are the generator's defaults, about 3,900 rows
in total. See `sample_data/README.md` for the planted quality problems. The original
requirements are kept below.

At minimum, generate via a Python script:
1. `manufacturing_data.csv` — serial_number, production_line, timestamp,
   temperature, pressure, test_duration, result, error_code — with missing values,
   duplicates, and realistic data-quality problems, plus PASS/FAIL values.
2. `employee_data.csv` — employee_id, department, age, salary, experience_years,
   location, hire_date — with realistic data-quality problems. (An initial version,
   `sample_employee_data.csv`, already exists at the repo root for manual testing.)
3. `sales_data.csv` — order_id, date, region, product, quantity, unit_price,
   revenue.

Large enough to be an interesting demo, not huge.

## Frontend Design

Professional SaaS/data-platform look, not flashy. Responsive layout, sidebar nav,
dashboard with cards/tables/charts/tabs/tooltips, loading/skeleton/empty/error
states. Prioritize clarity, professional appearance, data readability. No analysis
logic duplicated in TypeScript.

## Performance & Safety

Sanitize filenames, use internal UUID file IDs, limit upload size, validate content,
handle encoding/malformed CSV errors, avoid path traversal, never execute uploaded
content, clean up temp files. Design for portfolio/demo-sized datasets, not
multi-GB enterprise scale — document this limitation in the README.

## README Requirements

Description, Features, Architecture (Mermaid diagram if appropriate), Tech Stack,
Screenshots placeholder, Local Setup (backend venv + pip install + uvicorn; frontend
npm install + npm run dev), environment variables, how to run pytest, how to use
sample datasets, "What I Learned", "Technical Highlights".

## Development Process Rules

- Work incrementally through Phases 1-7 as listed at the top of this file.
- **Stop after each phase and wait for explicit user confirmation before
  continuing to the next phase.**
- Do not build the entire app in one blind pass.

## Teaching Requirement

For every important Python component implemented, briefly explain: what it does,
why it's implemented this way, what Python concepts it demonstrates, what
Pandas/NumPy functionality is used, and what an interviewer might ask about it.
Don't over-explain trivial syntax. If there are multiple reasonable approaches,
briefly note the tradeoff before choosing.

## Code Quality Rules (hard constraints)

Do NOT: fake functionality, hardcode analysis results, add dead buttons, generate
random/fake metrics in the UI, compute statistics in the frontend, silently swallow
Python exceptions, put everything in main.py, overengineer simple things, add
unnecessary dependencies. Every dashboard value must come from real analysis of the
uploaded CSV, and the app must work on CSVs never seen before.

## Portfolio Demo Goal

End-to-end live demo: Upload CSV → Python analyzes → dashboard appears → inspect
data-quality issues → inspect statistics → visualize distributions → inspect
correlations → clean data → compare before/after → export cleaned CSV.

## Working Copy & Cleaning (Phase 5) — COMPLETE

- The uploaded file is version 0 and is never modified. Each successful cleaning step
  writes a complete new version (`{id}.v{n}.csv`) through a temp file and an atomic
  `os.replace`, then moves the `working_version` pointer in one database commit.
  A failure before the commit leaves the previous version in place.
- Analysis routes always read the version the pointer names; nothing is cached.
- Operations: fill missing (mean, median, mode, custom, remove rows), remove duplicates
  (all columns or a subset), trim and blank-to-missing for text columns, drop columns,
  rename column, convert type (number, date, true/false, text) with refusal and a count
  when values can't convert.
- Endpoint: `POST /api/datasets/{id}/clean` with a discriminated union body on
  `operation`. Unknown operations and fields are rejected with a readable message.
- Not in Phase 5: user-facing history, undo, cleaned CSV export (Phase 6).

## Dataset Scope

- Current scope: interactive, demo-sized CSV files up to **50 MB** (`DATALENS_MAX_UPLOAD_SIZE_MB`
  defaults to 50). The limit is configurable but is not raised by default.
- Reason: every analysis loads the whole file into one in-memory pandas DataFrame, and
  the Explore, quality, and statistics routes recompute from it per request. Larger
  files would make requests slow without a streaming or chunked design, which is out of
  scope for this portfolio project.
- Reading a file a second time on every request is a deliberate simplicity trade-off.
  There is no cache, so results can never be stale.

## Current Limitations (end of Phase 7)

The project is feature-complete. These are the remaining limitations. The README
covers them in more detail.

- No undo or rollback. Each working version is a full copy, so disk use grows with
  each cleaning step. Previous versions are deleted on commit (see Phase 6 Decisions).
- The history shows operations and counts, not per-value changes. "Values modified" is
  not reported anywhere.
- `affected_rows` means different things per operation: cells filled, rows removed,
  rows with changed text, non-missing values converted. For drop and rename it is every
  row or zero by convention, so the UI hides it for those two operations.
- Export of an untouched dataset returns the original upload's bytes and encoding. A
  cleaned export is always UTF-8, and the file has no BOM, so Excel may misread accents.
- On Windows, a cleaning step that finishes while an export is still streaming the
  previous version can't delete that file. The leftover is logged, not removed.
- Single-process locking: the transformation lock is an in-process `threading.Lock`.
  Multiple server workers would need a database-level lock.
- SQLite only. Schema migration is a small inline `ALTER TABLE` in `init_db`, not
  Alembic.
- Type conversion is strict: numbers with currency symbols, thousands separators, or
  mixed formats are refused, not repaired. Mode ties resolve to the smallest value.
- Datetime detection requires at least 90% of sampled values to parse. A column that
  is mostly malformed dates is treated as categorical.
- Quality analysis is not a substitute for statistical outlier detection. Outlier
  detection is out of scope.
- Request validation: malformed query-parameter *types* (e.g. `bins=abc`) get FastAPI's
  default 422 body. Range and business-rule errors use the app's error shape.
- Visual correlation heatmap is HTML, not canvas, so very wide matrices (hundreds of
  columns) would need virtualization.

## Phase 6 Requirements (implemented; the list below is the original brief)

Scope: before/after comparison, transformation history, and cleaned CSV export. Phase
7 covers polish and documentation.

1. **Before/after comparison.** Compare the original upload (version 0) with the current
   working version. Show rows, missing values, duplicate rows, and the quality score for
   both, plus rows removed, values modified, columns dropped or renamed, and the list of
   transformations applied. Compute everything in Python from the two real files. The
   frontend only renders the response. Every value must come from analysis of the files.
2. **Transformation history.** Expose the ordered `transformations` rows for a dataset
   (`GET /api/datasets/{id}/transformations`) and show them as a list in the UI, for
   example "Removed 1 duplicate row(s) — 8 → 7 rows — version 2". Show the operation,
   column, parameters, affected rows, and timestamp. Decide whether to show the
   `summary` text, which Phase 5 does not store; if it's wanted, store it in the
   `transformations` row.
3. **Cleaned CSV export.** `GET /api/datasets/{id}/export` returns the current working
   version as a CSV download with `Content-Disposition`. Export is only available when
   a working version exists, or it returns the original file, which is clearly labelled.
   The download must not depend on any state the user might have changed in the browser.
   Optional: JSON export of the analysis results (profile, quality, statistics).
4. **Undo (optional, only if it stays simple).** Could roll the pointer back one version,
   for example `POST /api/datasets/{id}/undo`. The file of the undone version can be kept
   or removed. Undo must never touch the original upload. If undo proves complicated,
   document it as a limitation rather than building it.
5. **Safety.** Phase 6 reads only. The working-copy invariants below still apply. The
   export and comparison paths must never write to the upload directory.
6. **Tests.** Comparison values checked against hand-computed results on a small CSV,
   history matches the applied operations, export bytes match the working file, export
   of an unmodified dataset returns the original, and 404 behavior.
7. **UI.** A Compare view with a before/after table and the transformation list, and an
   Export button that links to the endpoint. No dead buttons.

## Phase 6 Decisions

- **Undo: not implemented.** Phase 5 deletes the previous working version on commit, so
  undoing one step would mean keeping that file, adding a pointer rollback, and changing
  history semantics. The added risk to the version-0 guarantee wasn't worth it for a
  portfolio app. Documented as a limitation.
- **Comparison has two kinds of numbers, kept apart.** Dataset-state metrics (rows,
  columns, missing values, duplicate rows, quality score) come from the same profiler
  and quality helpers as the dashboard, so they can't drift. Operation totals come only
  from recorded history.
- **No "values modified" metric.** Positional row comparison of two files breaks as soon
  as duplicates are removed, so the number would be misleading. It is omitted, not estimated.
- **History source of truth is the `transformations` table.** The display sentence is
  built from structured fields in `services/history.py`. No `summary` column was added, so
  no migration was needed. Stored parameters that can't be read fail with
  `CorruptHistoryError` rather than being shown.
- **Export streams the working file as-is.** It isn't rebuilt from a DataFrame, so the
  bytes match the analysed file. Nothing is written to disk. Filenames are sanitized.
- **Read-only guarantee.** Comparison, history, and export never write to the upload
  directory or the database. Tests check that the original's SHA-256 and the directory
  listing are unchanged.
- **Optional JSON export: not built.** CSV export was the required item.

## Working-Copy Invariants (must hold in every future phase)

- `{id}.csv` (version 0, the original upload) is never written after upload.
- A working version becomes visible only through the `working_version` pointer, which
  moves only after its file is complete on disk and its database row is committed.
- Analysis routes load through `api/dependencies.load_dataframe`, which follows the
  pointer. Any new analysis route must use it, never read `stored_filename` directly
  (except for the original-only comparison in Phase 6).
- A failed operation leaves no partial file and no changed pointer.
- Deleting a dataset removes its original, every working version, and its
  transformation rows.

## Continuity Notes

- Read this file, then `README.md`. Run `pytest` in `backend/` (251 tests at the end of
  Phase 7), `npx tsc --noEmit`, `npm run lint`, and `npm run build` in `frontend/`.
- Phase 7 additions: `sample_data/` and an expanded README. The production-only settings are
  `DATALENS_ENVIRONMENT=production` (disables `/docs`) and `NEXT_PUBLIC_API_BASE_URL`
  (baked in at build time).
- Deployment: not deployed anywhere. No Docker, by decision: the app runs as two local
  processes with no infrastructure to containerize. Choosing a host is a manual decision.
- Development servers: `uvicorn app.main:app --port 8000` in `backend/` (no `--reload`
  in the verification setup, so restart after backend edits) and `npm run dev` in
  `frontend/`.
- Local test data lives in `backend/data/` (gitignored). Deleting it resets all uploads.
- `sample_employee_data.csv` and `sample_messy_cleaning.csv` in the project root are
  untracked manual-testing files, not committed fixtures.
- Phases are approved one at a time. Do not start the next phase until the user says so.