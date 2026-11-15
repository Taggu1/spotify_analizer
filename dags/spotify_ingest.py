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
        for item in items:
            cur.execute(
                """
                INSERT INTO plays (track_id,track_name,artist_name,played_at)
                VALUES (%s,%s,%s,%s)
                ON CONFLICT (track_id, played_at) DO NOTHING;

                """,
                (
                    item["track"]["id"],
                    item["track"]["name"],
                    item["track"]["artists"][0]["name"],
                    item["played_at"],

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


with DAG(
    dag_id="spotify_ingest",
    start_date=datetime(2026,1,1),
    schedule=timedelta(minutes=10),
    catchup=False,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=1)},

) as dag:
    PythonOperator(task_id="ingest_recent_plays",python_callable=ingest)