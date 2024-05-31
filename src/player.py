import asyncio
import logging
import time
from asyncio import AbstractEventLoop, Event, Task, Future
from typing import Optional, Callable

from pylrc.classes import Lyrics, LyricLine


async def default_lyric_callback(lyric: LyricLine):
    print(lyric.text)


def find_lyric_to_play(lyrics: Lyrics[LyricLine], current_time: float) -> Optional[LyricLine]:
    """
    Find the last lyrics that should be displayed at the current time.
    :param lyrics: The lyrics to search through.
    :param current_time: The current time in the song.
    :return: The lyric to display.
    """
    for line in reversed(lyrics):
        if line.time < current_time:
            return line

    return None


class Player:
    def __init__(
            self,
            lyrics: Optional[Lyrics[LyricLine]] = None,
            current_time: Optional[float] = 0,
            lyric_callback: Optional[Callable[[LyricLine], Future]] = None,
    ):
        self.lyrics: Lyrics[LyricLine] = lyrics or Lyrics()
        self.current_time: float = current_time
        self.playing: bool = False
        self.progress_event: Event = asyncio.Event()
        self.lyrics_event: Event = asyncio.Event()
        self.loop: AbstractEventLoop = asyncio.get_event_loop()

        self.task: Optional[Task] = None

        self.lyric_callback = lyric_callback or default_lyric_callback

    async def start(self):
        if self.playing:
            return

        self.playing = True
        self.task = asyncio.create_task(self._play_loop())

    async def stop(self):
        if not self.playing:
            return

        self.playing = False

        if self.task:
            self.task.cancel()

    async def set_progress(self, progress):
        if abs(self.current_time - progress) < 1:
            return

        self.current_time = progress
        self.progress_event.set()

    async def set_lyrics(self, lyrics):
        self.lyrics = lyrics
        self.lyrics_event.set()

    async def _play_loop(self):
        last_lyric: Optional[LyricLine] = None

        start_time = time.time()

        while True:
            if self.lyrics_event.is_set():
                last_lyric = None
                start_time = time.time()
                self.lyrics_event.clear()

            if self.progress_event.is_set():
                start_time = time.time() - self.current_time
                self.progress_event.clear()

            await asyncio.sleep(0.1)

            if not self.progress_event.is_set():
                self.current_time = time.time() - start_time

            lyric = find_lyric_to_play(self.lyrics, self.current_time)

            if lyric == last_lyric:
                continue

            await self.lyric_callback(lyric)
            last_lyric = lyric
