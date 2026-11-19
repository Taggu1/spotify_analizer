import os
import urllib.parse
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler

import requests
from dotenv import load_dotenv

load_dotenv()
CLIENT_ID = os.environ["SPOTIFY_CLIENT_ID"]
CLIENT_SECRET = os.environ["SPOTIFY_CLIENT_SECRET"]
REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPE = "user-read-recently-played"

# 1. The page where you click "Agree"
auth_url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode({
    "client_id": CLIENT_ID,
    "response_type": "code",
    "redirect_uri": REDIRECT_URI,
    "scope": SCOPE,
})


# 2. A tiny server that catches Spotify's answer
class Handler(BaseHTTPRequestHandler):
    code = None

    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        Handler.code = urllib.parse.parse_qs(query).get("code", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Done! You can close this tab.")

    def log_message(self, *args):
        pass


print("Opening your browser...")
webbrowser.open(auth_url)
server = HTTPServer(("127.0.0.1", 8888), Handler)
while Handler.code is None:
    server.handle_request()

# 3. Trade the code for tokens
resp = requests.post(
    "https://accounts.spotify.com/api/token",
    data={
        "grant_type": "authorization_code",
        "code": Handler.code,
        "redirect_uri": REDIRECT_URI,
    },
    auth=(CLIENT_ID, CLIENT_SECRET),
)
resp.raise_for_status()
tokens = resp.json()

# 4. Save the refresh token into .env
with open(".env", "a") as f:
    f.write(f"\nSPOTIFY_REFRESH_TOKEN={tokens['refresh_token']}\n")
print("Refresh token saved to .env")

# 5. Quick test: show your last 5 plays
r = requests.get(
    "https://api.spotify.com/v1/me/player/recently-played",
    headers={"Authorization": f"Bearer {tokens['access_token']}"},
    params={"limit": 5},
)
r.raise_for_status()
for item in r.json()["items"]:
    print(item["played_at"], "-", item["track"]["name"], "-", item["track"]["artists"][0]["name"])