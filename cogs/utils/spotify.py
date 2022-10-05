import base64
import time

class Spotify:
    BASE_URL = "https://api.spotify.com/v1/"

    def __init__(self, session, *, client_id=None, client_secret=None):
        self.session = session
        self.client_id = client_id
        self.client_secret = client_secret

        self._token = None

    async def get_track(self, track_id):
        token = await self.get_token()
        async with self.session.get(f"{self.BASE_URL}tracks/{track_id}", headers={"Authorization": f"Bearer {token}"}) as resp:
            if resp.status == 400:
                return None

            track = await resp.json()
            return f"{track['name']} - {track['artists'][0]['name']}"

    async def get_album(self, album_id):
        token = await self.get_token()
        async with self.session.get(f"{self.BASE_URL}albums/{album_id}/tracks", headers={"Authorization": f"Bearer {token}"}) as resp:
            if resp.status == 400:
                return []

            tracks = await resp.json()
            return [f"{track['name']} - {track['artists'][0]['name']}" for track in tracks["items"]]

    async def get_playlist(self, playlist_id):
        token = await self.get_token()
        async with self.session.get(f"{self.BASE_URL}playlists/{playlist_id}/tracks", headers={"Authorization": f"Bearer {token}"}) as resp:
            if resp.status == 400:
                return []

            tracks = await resp.json()
            return [f"{track['track']['name']} - {track['track']['artists'][0]['name']}" for track in tracks["items"]]

    async def get_token(self):
        if self._token and (self._token["accessTokenExpirationTimestampMs"] / 1000) - time.time() > 0:
            return self._token["accessToken"]

        if self.client_id and self.client_secret:
            async with self.session.get(
                "https://accounts.spotify.com/api/token",
                data={"grant_type": "client_credentials"},
                headers={"Authorization": f"Basic {base64.b64encode(self.client_id + ':' + self.client_secret).decode('utf-8')}"}
            ):
                token = await resp.json()
        else:
            async with self.session.get("https://open.spotify.com/get_access_token?reason=transport&productType=web_player") as resp:
                token = await resp.json()

        assert "accessToken" in token
        assert "accessTokenExpirationTimestampMs" in token
        self._token = token

        return self._token["accessToken"]
