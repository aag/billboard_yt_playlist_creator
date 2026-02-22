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
import time

from datetime import datetime
from typing import TypedDict

import httplib2
import sqlite3

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
        missing_secrets_message = "Error: {0} is missing".format(client_secrets_file)

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
            flags = parser.parse_args()

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

                self.logger.info("\tVideo added: %s", title.encode("utf-8"))
                return

            except Exception as e:
                if e.resp.status == 409 and 'SERVICE_UNAVAILABLE' in str(e):
                    retry_count += 1
                    print(f"Attempt {retry_count} failed. Retrying in {backoff_time} seconds...")
                    time.sleep(backoff_time)
                    backoff_time *= 2  # Exponential backoff
                else:
                    raise
        raise Exception("Failed to add the song to the playlist after multiple retries.")



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
        return "https://www.youtube.com/playlist?list={0}".format(pl_id)


class BillboardAdapter(object):
    """An adapter class for the billboard.py library."""

    @classmethod
    def get_chart_data(
        cls, chart_id: str, date: str | None = None
    ) -> billboard.ChartData:
        """Returns the chart data for a given chart and date. If no date is
        given, it returns the current week's chart."""
        return billboard.ChartData(chart_id, date)


class PlaylistCreator(object):
    """This class contains the logic needed to retrieve Billboard charts and
    create playlists from them."""

    def __init__(
        self,
        logger: logging.Logger,
        youtube: YoutubeAdapter,
        billboard_adapter: BillboardAdapter,
    ) -> None:
        self.logger = logger
        self.youtube = youtube
        self.billboard = billboard_adapter

    def add_first_video_to_playlist(self, pl_id: str, search_query: str) -> None:
        """Does a search for videos and adds the first result to the given
        playlist"""
        video_id = self.youtube.get_video_id_for_search(search_query)

        # No search results were found, so log a message and return
        if video_id is None:
            self.logger.warning(
                "No search results found for '%s'. Moving on to the next song.",
                search_query,
            )
            return

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

            query = entry.artist + " " + entry.title
            song_info = (
                "#" + str(entry.rank) + ": " + entry.artist + " - " + entry.title
            )

            self.logger.info("Adding %s", song_info)
            self.add_first_video_to_playlist(pl_id, query)

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
        pl_title = "{0} - {1}".format(chart_name, chart_date)
        pl_description = (
            "This playlist contains the "
            + num_songs_phrase
            + "songs in the "
            + chart_name
            + " Songs chart for "
            "the week of " + chart_date + ".  " + web_url
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
        return

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

        # Billboard Dance/Club Play Songs
        self.create_playlist_from_chart(
            "dance-club-play-songs",
            "Dance/Club Play",
            "top 50 ",
            "http://www.billboard.com/charts/dance-club-play-songs",
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
        exit()

    config = configparser.ConfigParser()
    config.read(config_path)

    # Do basic checks on the config file
    if not config.has_section(section_name):
        logger.error(
            "Error: The config file doesn't have an accounts "
            "section. Check the config file format."
        )
        exit()

    if not config.has_option(section_name, "api_key"):
        logger.error(
            "Error: No developer key found in the config file. "
            "Check the config file values."
        )
        exit()

    config_values: ScriptConfig = {
        "api_key": config.get(section_name, "api_key"),
    }

    return config_values


def get_script_dir() -> str:
    """Returns the absolute path to the script directory"""
    return os.path.dirname(os.path.realpath(__file__)) + "/"


def main() -> None:
    """Script main function"""
    logging.basicConfig(format="%(message)s")
    logger = logging.getLogger("createbillboardplaylist")
    logger.setLevel(logging.INFO)

    config = load_config(logger)
    youtube = YoutubeAdapter(logger, config["api_key"], get_script_dir())
    billboard_adapter = BillboardAdapter()

    playlist_creator = PlaylistCreator(logger, youtube, billboard_adapter)
    playlist_creator.create_all()


if __name__ == "__main__":
    main()
