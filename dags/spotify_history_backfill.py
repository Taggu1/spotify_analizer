import glob
import json
import os

import psycopg2
from psycopg2.extras import execute_values
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

def get_conn():
    return psycopg2.connect(
    host="postgres", port=5432,
    dbname="spotify", user="spotify", password="spotify" 
)

def create_tables():
    conn = get_conn()

    with conn, conn.cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS streaming_history (
            ts TIMESTAMPTZ NOT NULL,
            platform TEXT,
            ms_played INTEGER,
            track_id TEXT,
            track_name TEXT,
            artist_name TEXT,
            album_name TEXT,
            episode_name TEXT,
            episode_show_name TEXT,
            reason_start TEXT,
            reason_end TEXT,
            shuffle BOOLEAN,
            skipped BOOLEAN,
            offline BOOLEAN,
            UNIQUE NULLS NOT DISTINCT (ts, platform, track_id, episode_name, ms_played)
        );
        """)
    conn.close()

def create_views():
    conn = get_conn()

    with conn, conn.cursor() as cur:
        cur.execute("""
        CREATE OR REPLACE VIEW all_plays AS
        SELECT ts AS played_at, track_id, track_name, artist_name, album_name,
            ms_played, 'export' AS source
        FROM streaming_history
        WHERE track_id IS NOT NULL
        UNION ALL
        SELECT played_at, track_id, track_name, artist_name, album_name,
            NULL::int AS ms_played, 'api' AS source
        FROM plays
        WHERE played_at > (SELECT COALESCE(MAX(ts), '-infinity'::timestamptz)
                        FROM streaming_history);

        CREATE OR REPLACE VIEW listens AS
        SELECT * FROM all_plays
        WHERE source = 'api' OR ms_played >= 30000;

        CREATE OR REPLACE VIEW daily_plays AS
        SELECT (played_at AT TIME ZONE 'Africa/Cairo')::date AS day,
            COUNT(*) AS plays
        FROM listens
        GROUP BY 1
        ORDER BY 1 DESC;

        CREATE OR REPLACE VIEW top_artists AS
        SELECT artist_name, COUNT(*) AS plays
        FROM listens
        GROUP BY artist_name
        ORDER BY plays DESC;

        CREATE OR REPLACE VIEW plays_by_hour AS
        SELECT TO_CHAR(played_at AT TIME ZONE 'Africa/Cairo','HH12 AM') as hour, COUNT(*) as plays FROM listens
        GROUP BY 1
        ORDER BY 1 DESC;
    
        """)
    conn.close()

def load_history():
    conn = get_conn()
    files = sorted(glob.glob("exports/*Audio*.json"))

    total_read = 0
    total_new = 0

    def track_id_from_uri(uri):
        return uri.split(":")[-1] if uri else None

    for path in files:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        rows = [
            (
                r["ts"],
                r.get("platform"),
                r.get('ms_played'),
                track_id_from_uri(r.get('spotify_track_uri')),
                r.get("master_metadata_track_name"),
                r.get("master_metadata_album_artist_name"),
                r.get("master_metadata_album_album_name"),
                r.get("episode_name"),
                r.get("episode_show_name"),
                r.get("reason_start"),
                r.get("reason_end"),
                r.get("shuffle"),
                r.get("skipped"),
                r.get("offline")
            )
            for r in data
        ]

        with conn, conn.cursor() as cur:
            before = cur.execute("SELECT COUNT(*) FROM streaming_history;") or None
            cur.execute("SELECT COUNT(*) FROM streaming_history;");
            before = cur.fetchone()[0]

            execute_values(
                cur,
                """
                INSERT INTO streaming_history (ts, platform, ms_played, track_id,
                track_name,artist_name, album_name, episode_Name,
                episode_show_name, reason_start, reason_end,
                shuffle, skipped, offline
                )
                VALUES %s
                ON CONFLICT DO NOTHING
                """,
                rows,
                page_size=2000
            )

            cur.execute("SELECT COUNT(*) FROM streaming_history;")
            after = cur.fetchone()[0]
        total_read += len(rows)
        total_new += after - before
        print(f'BEFORE ${before} AFTER ${after}')
        print(f"{os.path.basename(path)}: {len(rows)} rows, {after - before} new")
    conn.close()
    print(f"\nDone. Read {total_read} rows, inserted {total_new}.")

def normalize_history():
    conn = get_conn()

    with conn, conn.cursor() as cur:
        cur.execute("""
            CREATE OR REPLACE VIEW  streaming_history_normalized AS
            SELECT *,
                CASE
                    WHEN LOWER(platform) LIKE '%playstation%' THEN 'PlayStation'
                    WHEN LOWER(platform) LIKE '%android%' THEN 'Andorid'
                    WHEN LOWER(platform) LIKE '%windows%' THEN 'Windows'
                    WHEN LOWER(platform) LIKE '%osx%' THEN 'Mac os'
                    WHEN LOWER(platform) LIKE '%linux%' THEN 'Linux'
                    ELSE 'Other / Unknown'       
                END as normalized_platform
            FROM streaming_history;
        """)
    conn.close()


with DAG(
        dag_id="spotify_load_history",
    start_date=datetime(2026,1,1),
    schedule=None,
    catchup=False,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=1)},
) as dag:
    create_tables_task = PythonOperator(task_id="create_history_table", python_callable=create_tables)
    create_views_task = PythonOperator(task_id="create_views", python_callable=create_views)

    load_history_task = PythonOperator(task_id="load_history", python_callable=load_history)
    normalize_history = PythonOperator(task_id="normalize_history", python_callable=normalize_history)

    create_tables_task >> load_history_task >> normalize_history >> create_views_task
