import asyncio
import logging
from os import getenv
from typing import Dict

import pylrc
import syncedlyrics
from dotenv import load_dotenv
from pylrc.classes import Lyrics, LyricLine
from pypresence import AioPresence
from rich.json import JSON
from rich.logging import RichHandler
from spotipy import Spotify, SpotifyOAuth

from src.player import Player

logger = logging.getLogger(__name__)


def setup_logging():
    logging.basicConfig(
        level="INFO",
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)]
    )


def initialize_spotipy(client_id: str, client_secret: str, redirect_uri: str) -> Spotify:
    logger.info("Initializing Spotipy...")

    spotify = Spotify(
        auth_manager=SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=["user-read-email", "user-read-currently-playing", "user-read-playback-state"]
        )
    )

    logger.info("Spotipy initialized successfully! Logged in as:")

    logger.info(JSON.from_data(spotify.me()).text)

    return spotify


async def main():
    load_dotenv()

    setup_logging()

    spotify = initialize_spotipy(
        getenv("SPOTIFY_CLIENT_ID"),
        getenv("SPOTIFY_CLIENT_SECRET"),
        getenv("SPOTIFY_REDIRECT_URI")
    )

    presence = AioPresence(client_id=getenv("DISCORD_CLIENT_ID"))
    await presence.connect()

    last_track = None

    async def lyric_callback(line: LyricLine):
        logger.info(f"[{line.time}] {line.text}")

        await presence.update(
            large_image="lyrics",
            large_text="Lyrics",
            small_image="play",
            small_text="Playing",
            details=f"{last_track['name']} by {last_track['artists'][0]['name']}" if last_track else "Nothing playing",
            state=line.text
        )

    player = Player(lyric_callback=lyric_callback)

    while True:
        try:
            current_playback = get_current_playing(spotify)
        except ValueError:
            await presence.update(
                large_image="spotify",
                large_text="Spotify",
                small_image="pause",
                small_text="Paused",
                details="Nothing playing",
            )

            await player.stop()
            await asyncio.sleep(int(getenv("SPOTIFY_POLL_INTERVAL", "5")))

            continue

        if not last_track or not current_playback["item"]["id"] == last_track["id"]:
            last_track = current_playback["item"]
            lyrics = get_lyrics(current_playback["item"])

            await player.set_lyrics(lyrics)

        await player.set_progress(current_playback["progress_ms"] / 1000)

        if current_playback["is_playing"]:
            await player.start()
        else:
            await player.stop()

        await asyncio.sleep(5)


def get_current_playing(spotify: Spotify) -> dict:
    """
    Get the currently playing track on Spotify.
    :param spotify:
    :return:
    """
    current_playing = spotify.current_playback()

    if not current_playing or not current_playing["item"]["type"] == "track":
        logger.error("Not currently playing a track.")

        raise ValueError("Not currently playing a track.")

    logger.info(
        f"Fetched currently playing: {current_playing['item']['name']} by {', '.join([artist['name'] for artist in current_playing['item']['artists']])}"
    )

    return current_playing


def get_lyrics(track: Dict) -> Lyrics[LyricLine]:
    logger.info(
        f"Fetching lyrics for {track['name']} by {track['artists'][0]['name']}..."
    )

    lyrics = syncedlyrics.search(f"{track['name']} {track['artists'][0]['name']}")

    return pylrc.parse(lyrics)


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    loop.run_until_complete(main())
