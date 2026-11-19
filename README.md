# Spotify Listening Pipeline

A personal data engineering project that collects my Spotify listening history, stores it in Postgres, and shows it on a dashboard. Everything runs locally in Docker.

It combines two data sources:

- **Spotify Web API**: Airflow polls my recently played tracks every 10 minutes.
- **Extended streaming history export**: a one-off backfill of my full history (years of JSON files).

## Architecture

```
                 ┌─────────────────────────────┐
Spotify API ───► │ Airflow DAG: spotify_ingest │ ──► plays (raw, API)
                 │  ingest → quality check     │               │
                 └─────────────────────────────┘               │
                                                               ▼
Export JSON ───► Airflow DAG: spotify_load_history ──► streaming_history (raw, export)
                                                               │
                                                               ▼
                                          SQL views: all_plays → listens
                                                               │
                                                               ▼
                                              Streamlit dashboard (Plotly)
```

All services run with Docker Compose.

## Tech stack

| Tool | Role |
|---|---|
| Docker Compose | Runs every service with one command |
| Postgres 16 | Storage (raw tables + analytics views) |
| Airflow 2.10 | Scheduling, retries, data quality checks |
| Python (requests, psycopg2) | API calls and loading |
| Streamlit + Plotly | Dashboard |

## Project structure

```
spotify-de/
├── docker-compose.yml
├── .env                     # secrets (not committed)
├── get_token.py             # one-time OAuth script to get the refresh token
├── dags/
│   ├── spotify_ingest.py        # API → plays, then quality check
│   └── spotify_load_history.py  # export JSON → streaming_history
├── sql/
│   └── 02_views.sql         # all_plays, listens, and dashboard views
├── dashboard/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── dashboard.py
│   └── .streamlit/config.toml
└── exports/                 # Spotify export JSON files (not committed)
```

## Prerequisites

- Docker and Docker Compose
- Python 3.10+ on your machine (only for the one-time token script)
- A **Spotify Premium** account (required for API apps in Development Mode)
- Optional: your Spotify "Extended streaming history" export (request it from your Spotify account privacy page; it can take days to arrive)

## Setup

### 1. Clone and create `.env`

```bash
git clone https://github.com/Taggu1/spotify_analizer.git spotify-de
cd spotify-de
```

Create a `.env` file:

```
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
SPOTIFY_REFRESH_TOKEN=
AIRFLOW_UID=50000
```

### 2. Create a Spotify app

1. Open the [Spotify developer dashboard](https://developer.spotify.com/dashboard) and click **Create app**.
2. Set the **Redirect URI** to exactly `http://127.0.0.1:8888/callback` and tick **Web API**.
3. Copy the **Client ID** and **Client secret** into `.env`.

### 3. Get the refresh token (once)

```bash
pip install requests python-dotenv
python get_token.py
```

Approve access in the browser. The script appends `SPOTIFY_REFRESH_TOKEN` to `.env` and prints your last 5 plays as a test.

### 4. Start Postgres and create the databases

```bash
docker compose up -d postgres

# Separate database for Airflow's own metadata
docker exec -it spotify-postgres psql -U spotify -d spotify -c "CREATE USER airflow WITH PASSWORD 'airflow';"
docker exec -it spotify-postgres psql -U spotify -d spotify -c "CREATE DATABASE airflow OWNER airflow;"

# The raw API table
docker exec -it spotify-postgres psql -U spotify -d spotify -c "
CREATE TABLE IF NOT EXISTS plays (
    track_id    TEXT,
    track_name  TEXT,
    artist_id   TEXT,
    artist_name TEXT,
    album_id    TEXT,
    album_name  TEXT,
    duration_ms INTEGER,
    played_at   TIMESTAMPTZ,
    ingested_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (track_id, played_at)
);"
```

### 5. Start Airflow and the dashboard

```bash
mkdir -p dags logs exports
docker compose up airflow-init      # first time only, wait until it exits
docker compose up -d --build
```

### 6. Turn on the pipeline

1. Open Airflow at http://localhost:8080 (default login `admin` / `admin`).
2. Unpause **`spotify_ingest`**. It now runs every 10 minutes: fetch recent plays, save them, run quality checks.

### 7. Backfill the full history (optional)

1. Copy the `Streaming_History_Audio_*.json` files from your export into `exports/`.
2. In Airflow, trigger **`spotify_load_history`** once. It creates the table and loads every file. Re-running it is safe and inserts nothing new.
3. Create the analytics views:

```bash
docker exec -i spotify-postgres psql -U spotify -d spotify < sql/02_views.sql
```

### 8. Open the dashboard

http://localhost:8501

## Services and ports

| Service | URL / port | Notes |
|---|---|---|
| Airflow | http://localhost:8080 | Default login is for local use only |
| Dashboard | http://localhost:8501 | Streamlit |
| Postgres | `localhost:5433` | From your machine. Inside Docker it is `postgres:5432` |

## Data model

**Raw tables** (one per source, never mixed):

- `plays`: from the API. Primary key `(track_id, played_at)`.
- `streaming_history`: from the export. Unique on `(ts, platform, track_id, episode_name, ms_played)` using `NULLS NOT DISTINCT`, so reloads never create duplicates.

**Views:**

- `all_plays`: music plays from both sources. Export data is used up to its last timestamp, and API plays are added only after that, so nothing is double-counted.
- `listens`: `all_plays` filtered to real listens (API plays, or export plays of 30 seconds or more).
- `daily_plays`, `top_artists`, `plays_by_hour`: aggregates over `listens`, in Cairo time.

## Data quality

After each ingest, the `check_data` task fails the run if:

- the `plays` table is empty,
- any row is missing a track or artist name,
- any play has a timestamp in the future.

## Design decisions

- **No Kafka or Spark.** One person's listening history is a few hundred events a day. Python and Postgres handle that easily, and a simpler stack is easier to run and debug.
- **Separate raw tables per source.** The API and the export have different fields. Keeping them apart avoids a messy merged table, and the merge logic lives in a single, visible SQL view.
- **Idempotent loads.** Every load can be re-run safely thanks to primary keys / unique constraints and `ON CONFLICT`.
- **Logic in SQL views, not in the dashboard.** The dashboard only displays; changing what counts as a "listen" is a one-line change in a view.
- **Personal data stays out of the database.** The loader skips the export's username, IP address, and user agent fields.

## Troubleshooting

| Problem | Fix |
|---|---|
| `connection refused` to `localhost:5433` inside a DAG | Inside Docker use host `postgres`, port `5432` |
| Task fails with a 400/401 from Spotify | The refresh token is missing or revoked. Re-run `get_token.py` and update `.env` |
| `INVALID_CLIENT: Invalid redirect URI` | The redirect URI in the Spotify app must be exactly `http://127.0.0.1:8888/callback` |
| `airflow-init` fails with a password error | The `airflow` user/database from step 4 is missing |
| DAG missing in Airflow | Check for a red import-error banner at the top of the DAG list |
| History DAG is green but loaded nothing | Check that `exports/` is mounted into the Airflow containers and the files match `*Audio*.json` |
| Port already in use | Stop the other process, or change the left side of the port mapping |

## Privacy and security

- `.env` and `exports/` contain personal data and secrets. Both are in `.gitignore` and must never be committed.
- The default passwords (`spotify/spotify`, `admin/admin`) are for local development only. Change them, and avoid publishing database or Airflow ports, before deploying anywhere.

## Roadmap

- [ ] Move all passwords into `.env` and add a `.env.example`
- [ ] Run table and view creation automatically from `sql/` files
- [ ] Pin Python dependency versions
- [ ] Nightly database backup
- [ ] Unit tests and a CI workflow
- [ ] Deploy to a small server behind HTTPS with a login
- [ ] More analysis: skip rates, listening by device, taste over time