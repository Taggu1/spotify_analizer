import os 
import psycopg2
import requests
from dotenv import load_dotenv


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
        host="localhost", port=5433,
        dbname="postgres", user="postgres", password="postgres"
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


if __name__ == "__main__":
    token = get_access_token()
    plays = fetch_recent_plays(token)
    new_rows = save_plays(plays)

    print(f"Fetched {len(plays)} plays, saved {new_rows} new ones.")