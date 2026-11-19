import os 
import psycopg2
import requests
from dotenv import load_dotenv
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta


load_dotenv()
CLIENT_ID = os.environ["SPOTIFY_CLIENT_ID"]
CLIENT_SECRET = os.environ["SPOTIFY_CLIENT_SECRET"]
REFRESH_TOKEN = os.environ["SPOTIFY_REFRESH_TOKEN"]

    

def get_access_token():
    resp = requests.post(
        "https://accounts.spotify.com/api/token",
        data= {"grant_type":"refresh_token", "refresh_token": REFRESH_TOKEN},
        auth=(CLIENT_ID,CLIENT_SECRET)
    )
    resp.raise_for_status()

    return resp.json()["access_token"]

def fetch_recent_plays(access_token):

    resp = requests.get(
                "https://api.spotify.com/v1/me/player/recently-played",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"limit":50}
    )

    resp.raise_for_status()

    return resp.json()["items"]

def save_plays(items):
    conn = psycopg2.connect(
        host="postgres", port=5432,
        dbname="spotify", user="spotify", password="spotify"
    )

    instrted = 0
    with conn, conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS plays (
                track_id TEXT,
                track_name TEXT,
                artist_name TEXT,
                played_at TIMESTAMPTZ,
                artist_id TEXT,
                album_id TEXT,
                album_name TEXT,
                duration_ms INTEGER,
                ingested_at TIMESTAMPTZ DEFAULT now(),
                PRIMARY KEY (track_id, played_at)
            );
        """)


        for item in items:
            track = item["track"]
            cur.execute(
                """
                INSERT INTO plays (track_id,track_name,artist_name,played_at,
                album_id,album_name,artist_id,duration_ms)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (track_id, played_at) DO UPDATE SET 
                artist_id = EXCLUDED.artist_id,
                album_id = EXCLUDED.album_id,
                album_name = EXCLUDED.album_name,
                duration_ms = EXCLUDED.duration_ms;

                """,
                (
                    track["id"],
                    track["name"],
                    track["artists"][0]["name"],
                    item["played_at"],
                    track["album"]["id"],
                    track["album"]["name"],
                    track["artists"][0]["id"],
                    track.get("duration_ms"),
                    


                )
            )
            instrted += cur.rowcount
    conn.close()
    return instrted


def ingest():
    token = get_access_token()
    plays = fetch_recent_plays(token)
    new_rows = save_plays(plays)

    print(f"Fetched {len(plays)} plays, saved {new_rows} new ones.")

def check_data():
    conn = psycopg2.connect(
        host="postgres",port=5432,
        dbname="spotify",user="spotify",password="spotify"
    )

    with conn, conn.cursor() as cur:
        cur.execute("""SELECT COUNT(*) FROM plays;""")
        total = cur.fetchone()[0]

        cur.execute("""
        SELECT COUNT(*) FROM plays
        WHERE track_name IS NULL OR artist_name IS NULL;
        """)
        nulls = cur.fetchone()[0]

        cur.execute("""
        SELECT COUNT(*) FROM plays 
        WHERE played_at > now();
        """)
        future = cur.fetchone()[0]
    conn.close()

    print(f"Nulls: {nulls}, total_rows: {total}, future: {future}")

    if total == 0:
        raise ValueError("Plays is empty")
    if nulls > 0:
        raise ValueError(f"{nulls} Have missing track_name or artist_name")
    if future > 0:
        raise ValueError(f"{future} tracks have future dates")

with DAG(
    dag_id="spotify_ingest",
    start_date=datetime(2026,1,1),
    schedule=timedelta(minutes=10),
    catchup=False,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=1)},

) as dag:
    ingest_task = PythonOperator(task_id="ingest_recent_plays",python_callable=ingest)
    check_task = PythonOperator(task_id="check_data", python_callable=check_data)