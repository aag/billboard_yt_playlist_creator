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

import unittest

import logging
import mock

from createbillboardplaylist import PlaylistCreator

# Prevent log messages from being printed
logging.getLogger().setLevel(logging.CRITICAL)


class CreatePlaylistTestCase(unittest.TestCase):
    def test_add_first_video_to_playlist(self):
        video_id = "test-video-id"
        playlist_id = "test-playlist"
        search_query = "test artist - test song title"

        billboard = mock.Mock()
        youtube = mock.Mock()
        youtube.get_video_id_for_search.return_value = video_id

        playlist_creator = PlaylistCreator(logging.getLogger(), youtube, billboard)
        playlist_creator.add_first_video_to_playlist(playlist_id, search_query)

        youtube.get_video_id_for_search.assert_called_with(search_query)
        youtube.add_video_to_playlist.assert_called_with(playlist_id, video_id)

    def test_add_first_video_to_playlist_none_found(self):
        playlist_id = "test-playlist"
        search_query = "test artist - test song title"

        billboard = mock.Mock()
        youtube = mock.Mock()
        youtube.get_video_id_for_search.return_value = None

        playlist_creator = PlaylistCreator(logging.getLogger(), youtube, billboard)
        playlist_creator.add_first_video_to_playlist(playlist_id, search_query)

        youtube.get_video_id_for_search.assert_called_with(search_query)
        youtube.add_video_to_playlist.assert_not_called()

    def test_add_chart_entries_to_playlist_single_entry(self):
        video_id = "test-video-id"
        playlist_id = "test-playlist"
        artist = "test artist"
        title = "test song"
        search_query = "{} {}".format(artist, title)

        entry = mock.Mock()
        entry.artist = artist
        entry.title = title
        entry.rank = 1

        entries = [entry]

        billboard = mock.Mock()
        youtube = mock.Mock()
        youtube.get_video_id_for_search.return_value = video_id

        playlist_creator = PlaylistCreator(logging.getLogger(), youtube, billboard)
        playlist_creator.add_chart_entries_to_playlist(playlist_id, entries)

        youtube.get_video_id_for_search.assert_called_with(search_query)
        youtube.add_video_to_playlist.assert_called_with(playlist_id, video_id)


if __name__ == "__main__":
    unittest.main()
