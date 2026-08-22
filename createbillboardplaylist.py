#!/usr/bin/python

"""
This is the Create Billboard Charts YouTube Playlist script
It is a Python script that will download some of the current Billboard charts
and create YouTube playlists containing videos for all the songs for the
charts. If it is run regularly, it will create new playlists each week for the
new Billboard charts.

An example of what the script creates can be seen here:
http://www.youtube.com/user/GimmeThatHotPopMusic
"""

# Copyright 2011-2026 Adam Goforth
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import configparser
import logging
import os.path
import re
import sqlite3
import sys
import time

from datetime import datetime
from typing import TypedDict
from urllib.parse import parse_qs, urlparse

import httplib2

# youtube-search
from youtube_search import YoutubeSearch

# Google Data API
from googleapiclient.discovery import build
from oauth2client.file import Storage
from oauth2client.client import flow_from_clientsecrets
from oauth2client.tools import argparser, run_flow

# billboard.py
import billboard


class YoutubeAdapter(object):
    """An adapter class for the Youtube service. This class presents the API
    that our script logic needs and handles the interaction with the Youtube
    servers."""

    YOUTUBE_READ_WRITE_SCOPE = "https://www.googleapis.com/auth/youtube"
    YOUTUBE_API_SERVICE_NAME = "youtube"
    YOUTUBE_API_VERSION = "v3"
    REDIRECT_URI = "http://127.0.0.1:8989"

    def __init__(self, logger: logging.Logger, api_key: str, config_path: str) -> None:
        """Create an object which contains an instance of the YouTube service
        from the Google Data API library"""
        self.logger = logger

        client_secrets_file = config_path + "client_secrets.json"
        missing_secrets_message = f"Error: {client_secrets_file} is missing"

        # Do OAuth2 authentication
        flow = flow_from_clientsecrets(
            client_secrets_file,
            message=missing_secrets_message,
            scope=YoutubeAdapter.YOUTUBE_READ_WRITE_SCOPE,
            redirect_uri=YoutubeAdapter.REDIRECT_URI,
        )

        storage = Storage(config_path + "oauth2.json")
        credentials = storage.get()

        if credentials is None or credentials.invalid:
            parser = argparse.ArgumentParser(
                description=__doc__,
                formatter_class=argparse.RawDescriptionHelpFormatter,
                parents=[argparser],
            )
            # Use parse_known_args because sys.argv may contain the
            # subcommand (e.g. "create"), which this parser doesn't know about
            flags, _ = parser.parse_known_args()

            credentials = run_flow(flow, storage, flags)

        # Create the service to use throughout the script
        self.service = build(
            YoutubeAdapter.YOUTUBE_API_SERVICE_NAME,
            YoutubeAdapter.YOUTUBE_API_VERSION,
            developerKey=api_key,
            http=credentials.authorize(httplib2.Http()),
        )

    def get_video_id_for_search(self, query: str) -> str | None:
        """Returns the videoId of the first search result if at least one video
        was found by searching for the given query, otherwise returns
        None"""
        search_result = YoutubeSearch(query, max_results=1).to_dict()
        if len(search_result) == 0:
            return None

        return search_result[0]["id"]

    def add_video_to_playlist(self, pl_id: str, video_id: str) -> None:
        """Adds the given video as the last video as the last one in the given
        playlist"""
        self.logger.info("\tAdding video pl_id: %s video_id: %s", pl_id, video_id)

        max_retries = 5
        retry_count = 0
        backoff_time = 1  # In seconds

        while retry_count < max_retries:
            try:
                video_insert_response = (
                    self.service.playlistItems()
                    .insert(
                        part="snippet",
                        body=dict(
                            snippet=dict(
                                playlistId=pl_id,
                                resourceId=dict(kind="youtube#video", videoId=video_id),
                            )
                        ),
                        fields="snippet",
                    )
                    .execute()
                )

                title = video_insert_response["snippet"]["title"]

                self.logger.info("\tVideo added: %s", title))
                return

            except Exception:
                retry_count += 1
                print(
                    f"Attempt {retry_count} failed. Retrying in {backoff_time} seconds..."
                )
                time.sleep(backoff_time)
                backoff_time *= 2  # Exponential backoff
        raise Exception(
            "Failed to add the song to the playlist after multiple retries."
        )

    def create_new_playlist(self, title: str, description: str) -> str:
        """Creates a new, empty YouTube playlist with the given title and
        description"""
        playlists_insert_response = (
            self.service.playlists()
            .insert(
                part="snippet,status",
                body=dict(
                    snippet=dict(title=title, description=description),
                    status=dict(privacyStatus="public"),
                ),
                fields="id",
            )
            .execute()
        )

        pl_id = playlists_insert_response["id"]
        pl_url = self._playlist_url_from_id(pl_id)

        self.logger.info("New playlist added: %s", title)
        self.logger.info("\tID: %s", pl_id)
        self.logger.info("\tURL: %s", pl_url)

        return pl_id

    def playlist_exists_with_title(self, title: str) -> bool:
        """Returns true if there is already a playlist in the channel with the
        given name"""
        playlists = (
            self.service.playlists()
            .list(part="snippet", mine=True, maxResults=10, fields="items")
            .execute()
        )

        for playlist in playlists["items"]:
            if playlist["snippet"]["title"] == title:
                return True

        return False

    @staticmethod
    def _playlist_url_from_id(pl_id: str) -> str:
        """Returns the URL of a playlist, given its ID"""
        return f"https://www.youtube.com/playlist?list={pl_id}"


class BillboardAdapter(object):
    """An adapter class for the billboard.py library."""

    @classmethod
    def get_chart_data(
        cls, chart_id: str, date: str | None = None
    ) -> billboard.ChartData:
        """Returns the chart data for a given chart and date. If no date is
        given, it returns the current week's chart."""
        return billboard.ChartData(chart_id, date)


class VideoCache(object):
    """Stores mappings from songs to YouTube video IDs in a local SQLite
    database. It acts as a cache so that songs which have already been searched
    for don't need to be searched again, and it allows the video used for a
    song to be overridden manually."""

    def __init__(self, db_path: str) -> None:
        self.conn = sqlite3.connect(db_path)
        self._create_table()

    def _create_table(self) -> None:
        """Creates the mappings table if it doesn't exist"""
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS mappings ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "artist TEXT NOT NULL, title TEXT NOT NULL, video_id TEXT NOT NULL,"
            " UNIQUE (artist, title))"
        )

    def close(self) -> None:
        """Closes the database connection"""
        self.conn.close()

    def get_video_id(self, artist: str, title: str) -> str | None:
        """Returns the stored video ID for the given song, or None if no
        mapping is stored"""
        row = self.conn.execute(
            "SELECT video_id FROM mappings WHERE artist = ? AND title = ?",
            (artist, title),
        ).fetchone()
        return row[0] if row else None

    def set_mapping(self, artist: str, title: str, video_id: str) -> None:
        """Stores the given video ID for the given song, replacing any existing
        mapping"""
        self.conn.execute(
            "INSERT OR REPLACE INTO mappings (artist, title, video_id)"
            " VALUES (?, ?, ?)",
            (artist, title, video_id),
        )
        self.conn.commit()

    def remove_mapping(self, id: int) -> bool:
        """Removes the stored mapping with the given ID. Returns True if a
        mapping was removed"""
        cursor = self.conn.execute("DELETE FROM mappings WHERE id = ?", (id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def list_mappings(self) -> list[tuple[int, str, str, str]]:
        """Returns all stored mappings"""
        rows = self.conn.execute(
            "SELECT id, artist, title, video_id FROM mappings ORDER BY id"
        ).fetchall()
        return [(id, artist, title, video_id) for id, artist, title, video_id in rows]

    def search(self, value: str) -> list[tuple[int, str, str, str]]:
        """Returns all stored (ID, artist, title, video ID) quadruples where
        the artist or title contains the given text"""
        pattern = f"%{value}%"
        rows = self.conn.execute(
            "SELECT id, artist, title, video_id FROM mappings"
            " WHERE artist LIKE ? OR title LIKE ? ORDER BY id",
            (pattern, pattern),
        ).fetchall()
        return [(id, artist, title, video_id) for id, artist, title, video_id in rows]

    @staticmethod
    def extract_video_id(value: str) -> str | None:
        """Returns the YouTube video ID from a raw video ID or a YouTube URL.
        Returns None if no video ID could be determined"""
        value = value.strip()
        parsed = urlparse(value)

        # A slash means this isn't a raw video ID, so treat it as a scheme-less
        # URL (e.g. youtu.be/ID) by adding a scheme and parsing again
        if not parsed.netloc and "/" in value:
            parsed = urlparse("http://" + value)

        if "youtu.be" in parsed.netloc and parsed.path:
            return VideoCache._validate_video_id(parsed.path.lstrip("/"))

        query_params = parse_qs(parsed.query)
        if "v" in query_params:
            return VideoCache._validate_video_id(query_params["v"][0])

        return VideoCache._validate_video_id(value)

    @staticmethod
    def _validate_video_id(video_id: str) -> str | None:
        """Returns the given string if it looks like a valid YouTube video ID,
        otherwise returns None"""
        if re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            return video_id
        return None


class PlaylistCreator(object):
    """This class contains the logic needed to retrieve Billboard charts and
    create playlists from them."""

    def __init__(
        self,
        logger: logging.Logger,
        youtube: YoutubeAdapter,
        billboard_adapter: BillboardAdapter,
        mappings: VideoCache,
    ) -> None:
        self.logger = logger
        self.youtube = youtube
        self.billboard = billboard_adapter
        self.mappings = mappings

    def add_video_to_playlist(self, pl_id: str, artist: str, title: str) -> None:
        """Adds a video for the given song to the given playlist. If a mapping
        is stored for the song it is used; otherwise a search is done and the
        first result is mapped and added"""
        video_id = self.mappings.get_video_id(artist, title)

        if video_id is None:
            query = f"{artist} - {title}"
            video_id = self.youtube.get_video_id_for_search(query)

            # No search results were found, so log a message and return
            if video_id is None:
                self.logger.warning(
                    "No cache entry or search results found for '%s'. Moving on to the next song.",
                    query,
                )
                return

            self.mappings.set_mapping(artist, title, video_id)

        self.youtube.add_video_to_playlist(pl_id, video_id)

    def add_chart_entries_to_playlist(
        self, pl_id: str, entries: list[billboard.ChartEntry]
    ) -> None:
        """Given the list of entries from a billboard.py listing, search for a
        video for each entry and add it to the given playlist"""
        song_count = 0
        for entry in entries:
            song_count += 1
            if song_count > 100:
                break

            song_info = f"#{entry.rank}: {entry.artist} - {entry.title}"

            self.logger.info("Adding %s", song_info)
            self.add_video_to_playlist(pl_id, entry.artist, entry.title)

        self.logger.info("\n---\n")

    def create_playlist_from_chart(
        self, chart_id: str, chart_name: str, num_songs_phrase: str, web_url: str
    ) -> None:
        """Create and populate a new playlist with the current Billboard chart
        with the given ID"""
        # Get the songs from the Billboard web page
        chart = self.billboard.get_chart_data(chart_id)
        assert chart.date is not None, "Chart date must not be None"
        chart_date = datetime.strptime(chart.date, "%Y-%m-%d").strftime("%B %d, %Y")

        # Create a new playlist, if it doesn't already exist
        pl_title = f"{chart_name} - {chart_date}"
        pl_description = (
            f"This playlist contains the {num_songs_phrase}songs in the "
            f"{chart_name} Songs chart for "
            f"the week of {chart_date}.  {web_url}"
        )

        # Check for an existing playlist with the same title
        if self.youtube.playlist_exists_with_title(pl_title):
            self.logger.warning(
                "Playlist already exists with title '%s'. "
                "Delete it manually and re-run the script to "
                "recreate it.",
                pl_title,
            )
            return

        pl_id = self.youtube.create_new_playlist(pl_title, pl_description)
        self.add_chart_entries_to_playlist(pl_id, chart.entries)

    def create_all(self) -> None:
        """Create all of the default playlists with this week's Billboard
        charts."""
        self.logger.info("### Script started at %s ###\n", time.strftime("%c"))

        # Billboard Rock Songs
        self.create_playlist_from_chart(
            "rock-songs",
            "Rock",
            "top 50 ",
            "http://www.billboard.com/charts/rock-songs",
        )

        # Billboard R&B/Hip-Hop Songs
        self.create_playlist_from_chart(
            "r-b-hip-hop-songs",
            "R&B/Hip-Hop",
            "top 50 ",
            "http://www.billboard.com/charts/r-b-hip-hop-songs",
        )

        # Billboard Dance/Electronic Songs
        self.create_playlist_from_chart(
            "dance-electronic-songs",
            "Dance/Electronic Songs",
            "top 25",
            "http://www.billboard.com/charts/dance-electronic-songs",
        )

        # Billboard Pop Songs
        self.create_playlist_from_chart(
            "pop-songs",
            "Pop",
            "top 40 ",
            "http://www.billboard.com/charts/pop-songs",
        )

        # Billboard Hot 100
        self.create_playlist_from_chart(
            "hot-100",
            "Hot 100",
            "",
            "http://www.billboard.com/charts/hot-100",
        )

        self.logger.info("### Script finished at %s ###\n", time.strftime("%c"))


class ScriptConfig(TypedDict):
    api_key: str


def load_config(logger: logging.Logger) -> ScriptConfig:
    """Loads config values from the settings.cfg file in the script dir"""
    config_path = get_script_dir() + "settings.cfg"
    section_name = "accounts"

    if not os.path.exists(config_path):
        logger.error(
            "Error: No config file found. Copy settings-example.cfg "
            "to settings.cfg and customize it."
        )
        sys.exit(1)

    config = configparser.ConfigParser()
    config.read(config_path)

    # Do basic checks on the config file
    if not config.has_section(section_name):
        logger.error(
            "Error: The config file doesn't have an accounts "
            "section. Check the config file format."
        )
        sys.exit(1)

    if not config.has_option(section_name, "api_key"):
        logger.error(
            "Error: No developer key found in the config file. "
            "Check the config file values."
        )
        sys.exit(1)

    config_values: ScriptConfig = {
        "api_key": config.get(section_name, "api_key"),
    }

    return config_values


def get_script_dir() -> str:
    """Returns the absolute path to the script directory"""
    return os.path.dirname(os.path.realpath(__file__)) + "/"


def parse_args() -> argparse.Namespace:
    """Parses the command line arguments"""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("create", help="Create this week's Billboard chart playlists")

    add_parser = subparsers.add_parser(
        "cache-set",
        help="Store the video to use for a song in the cache",
    )
    add_parser.add_argument("artist", help="The artist name")
    add_parser.add_argument("title", help="The song title")
    add_parser.add_argument("video_id_or_url", help="A YouTube video ID or URL")

    remove_parser = subparsers.add_parser(
        "cache-remove",
        help="Remove a stored cache entry so the song is searched for again",
    )
    remove_parser.add_argument(
        "id", type=int, help="The ID of the stored cache entry to remove"
    )

    subparsers.add_parser("cache-list", help="List all stored video cache entries")

    search_parser = subparsers.add_parser(
        "cache-search",
        help="Search stored video cache entries by artist or title text",
    )
    search_parser.add_argument("value", help="Text to look for in artist and title")

    # Unknown arguments are ignored here because they may be meant for the
    # OAuth2 flow (e.g. --noauth_local_webserver)
    return parser.parse_known_args()[0]


def main() -> None:
    """Script main function"""
    logging.basicConfig(format="%(message)s")
    logger = logging.getLogger("createbillboardplaylist")
    logger.setLevel(logging.INFO)

    args = parse_args()
    video_cache = VideoCache(get_script_dir() + "cache.db")

    if args.command == "create":
        config = load_config(logger)
        youtube = YoutubeAdapter(logger, config["api_key"], get_script_dir())
        billboard_adapter = BillboardAdapter()

        playlist_creator = PlaylistCreator(
            logger, youtube, billboard_adapter, video_cache
        )
        playlist_creator.create_all()
        return

    if args.command == "cache-set":
        video_id = VideoCache.extract_video_id(args.video_id_or_url)
        song_info = f"{args.artist} - {args.title}"
        if video_id is None:
            logger.error(
                "Error: '%s' is not a valid YouTube video ID or URL.",
                args.video_id_or_url,
            )
            sys.exit(1)
        else:
            video_cache.set_mapping(args.artist, args.title, video_id)
            logger.info("Stored cache entry for '%s': %s", song_info, video_id)

    elif args.command == "cache-remove":
        if video_cache.remove_mapping(args.id):
            logger.info("Removed cache entry with ID %s.", args.id)
        else:
            logger.error("No stored cache entry found with ID %s.", args.id)
            sys.exit(1)

    elif args.command == "cache-list":
        entries = video_cache.list_mappings()
        if not entries:
            print("No cache entries exist.")
        for id, artist, title, video_id in entries:
            print(f"{id}: {artist} - {title}: {video_id}")

    elif args.command == "cache-search":
        results = video_cache.search(args.value)
        if not results:
            print(f"No cache entries match '{args.value}'.")
        for id, artist, title, video_id in results:
            print(f"{id}: {artist} - {title}: {video_id}")

    video_cache.close()


if __name__ == "__main__":
    main()
