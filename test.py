import spotipy
from spotipy.oauth2 import SpotifyOAuth

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id="9a3c6efd113a470d995d98b98328346d",
    client_secret="0919f0fe75d24c29a5948e6d9af3c050",
    redirect_uri="http://127.0.0.1:8888/callback",
    scope="user-library-read user-top-read playlist-modify-private",
))

# Your top tracks
for t in sp.current_user_top_tracks(limit=5)["items"]:
    print(t["name"])
