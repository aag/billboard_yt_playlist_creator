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
from typing import Any, cast

import logging
import mock

from createbillboardplaylist import (
    VideoCache,
    PlaylistCreator,
    YoutubeAdapter,
    BillboardAdapter,
)

# Prevent log messages from being printed
logging.getLogger().setLevel(logging.CRITICAL)


class CreatePlaylistTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.video_cache = VideoCache(":memory:")

    def tearDown(self) -> None:
        self.video_cache.close()

    def _create_playlist_creator(self) -> tuple[PlaylistCreator, mock.Mock]:
        billboard_mock = mock.Mock()
        youtube_mock = mock.Mock()

        playlist_creator = PlaylistCreator(
            logging.getLogger(),
            cast(YoutubeAdapter, youtube_mock),
            cast(BillboardAdapter, billboard_mock),
            self.video_cache,
        )

        return playlist_creator, youtube_mock

    def test_add_video_to_playlist(self) -> None:
        video_id = "test-video-id"
        playlist_id = "test-playlist"
        artist = "test artist"
        title = "test song title"
        search_query = f"{artist} - {title}"

        playlist_creator, youtube_mock = self._create_playlist_creator()
        youtube_mock.get_video_id_for_search.return_value = video_id
        playlist_creator.add_video_to_playlist(playlist_id, artist, title)

        youtube_mock.get_video_id_for_search.assert_called_with(search_query)
        self.assertEqual(self.video_cache.get_video_id(artist, title), video_id)
        youtube_mock.add_video_to_playlist.assert_called_with(playlist_id, video_id)

    def test_add_video_to_playlist_uses_cached_mapping(self) -> None:
        stored_video_id = "stored-video-id"
        playlist_id = "test-playlist"
        artist = "test artist"
        title = "test song title"

        self.video_cache.set_mapping(artist, title, stored_video_id)

        playlist_creator, youtube_mock = self._create_playlist_creator()
        playlist_creator.add_video_to_playlist(playlist_id, artist, title)

        youtube_mock.get_video_id_for_search.assert_not_called()
        self.assertEqual(
            self.video_cache.list_mappings(),
            [(1, artist, title, stored_video_id)],
        )
        youtube_mock.add_video_to_playlist.assert_called_with(
            playlist_id, stored_video_id
        )

    def test_add_video_to_playlist_none_found(self) -> None:
        playlist_id = "test-playlist"
        artist = "test artist"
        title = "test song title"
        search_query = f"{artist} - {title}"

        playlist_creator, youtube_mock = self._create_playlist_creator()
        youtube_mock.get_video_id_for_search.return_value = None
        playlist_creator.add_video_to_playlist(playlist_id, artist, title)

        youtube_mock.get_video_id_for_search.assert_called_with(search_query)
        self.assertIsNone(self.video_cache.get_video_id(artist, title))
        youtube_mock.add_video_to_playlist.assert_not_called()

    def test_add_chart_entries_to_playlist_single_entry(self) -> None:
        video_id = "test-video-id"
        playlist_id = "test-playlist"
        artist = "test artist"
        title = "test song"
        search_query = f"{artist} - {title}"

        entry = mock.Mock()
        entry.artist = artist
        entry.title = title
        entry.rank = 1

        entries: list[Any] = [entry]

        playlist_creator, youtube_mock = self._create_playlist_creator()
        youtube_mock.get_video_id_for_search.return_value = video_id
        playlist_creator.add_chart_entries_to_playlist(playlist_id, entries)

        youtube_mock.get_video_id_for_search.assert_called_with(search_query)
        self.assertEqual(self.video_cache.get_video_id(artist, title), video_id)
        youtube_mock.add_video_to_playlist.assert_called_with(playlist_id, video_id)


class YoutubeAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.logger = logging.getLogger("test_logger")

    @mock.patch("createbillboardplaylist.YoutubeSearch")
    def test_get_video_id_for_search_returns_id_when_found(self, mock_ytsearch) -> None:
        expected_id = "video123"
        mock_ytsearch.return_value.to_dict.return_value = [{"id": expected_id}]

        adapter = YoutubeAdapter.__new__(YoutubeAdapter)
        result = adapter.get_video_id_for_search("test query")

        self.assertEqual(result, expected_id)

    @mock.patch("createbillboardplaylist.YoutubeSearch")
    def test_get_video_id_for_search_returns_none_when_not_found(
        self, mock_ytsearch
    ) -> None:
        mock_ytsearch.return_value.to_dict.return_value = []

        adapter = YoutubeAdapter.__new__(YoutubeAdapter)
        result = adapter.get_video_id_for_search("test query")

        self.assertIsNone(result)

    def test_add_video_to_playlist_success_on_first_attempt(self) -> None:
        with mock.patch(
            "createbillboardplaylist.YoutubeAdapter.__init__", return_value=None
        ):
            adapter = YoutubeAdapter(None, "fake-key", "/path/")  # type: ignore
            adapter.service = mock.Mock()
            adapter.logger = self.logger

            mock_execute = mock.Mock(return_value={"snippet": {"title": "Test Song"}})
            adapter.service.playlistItems().insert().execute = mock_execute

            adapter.add_video_to_playlist("pl-id", "vid-id")

            adapter.service.playlistItems().insert().execute.assert_called_once()

    def test_add_video_to_playlist_retries_with_exponential_backoff(self) -> None:
        with mock.patch(
            "createbillboardplaylist.YoutubeAdapter.__init__", return_value=None
        ):
            with mock.patch("time.sleep") as mock_sleep:
                adapter = YoutubeAdapter(None, "fake-key", "/path/")  # type: ignore
                adapter.service = mock.Mock()
                adapter.logger = self.logger

                mock_execute = mock.Mock(
                    side_effect=[
                        Exception(),
                        Exception(),
                        {"snippet": {"title": "Test Song"}},
                    ]
                )
                adapter.service.playlistItems().insert().execute = mock_execute

                adapter.add_video_to_playlist("pl-id", "vid-id")

                self.assertEqual(mock_execute.call_count, 3)
                mock_sleep.assert_has_calls([mock.call(1), mock.call(2)])

    def test_add_video_to_playlist_raises_after_max_retries(self) -> None:
        with mock.patch(
            "createbillboardplaylist.YoutubeAdapter.__init__", return_value=None
        ):
            with mock.patch("time.sleep"):
                adapter = YoutubeAdapter(None, "fake-key", "/path/")  # type: ignore
                adapter.service = mock.Mock()
                adapter.logger = self.logger

                mock_execute = mock.Mock(side_effect=Exception("API Error"))
                adapter.service.playlistItems().insert().execute = mock_execute

                with self.assertRaises(Exception) as context:
                    adapter.add_video_to_playlist("pl-id", "vid-id")

                self.assertIn("Failed to add the song", str(context.exception))
                self.assertEqual(mock_execute.call_count, 5)

    def test_create_new_playlist_returns_id_and_logs_info(self) -> None:
        with mock.patch(
            "createbillboardplaylist.YoutubeAdapter.__init__", return_value=None
        ):
            adapter = YoutubeAdapter(None, "fake-key", "/path/")  # type: ignore
            adapter.service = mock.Mock()
            adapter.logger = self.logger

            expected_id = "PL123456"
            adapter.service.playlists().insert().execute.return_value = {
                "id": expected_id
            }

            result = adapter.create_new_playlist("Test Playlist", "Test Description")

            self.assertEqual(result, expected_id)
            adapter.service.playlists().insert().execute.assert_called_once()

    def test_playlist_exists_with_title_returns_true_when_found(self) -> None:
        with mock.patch(
            "createbillboardplaylist.YoutubeAdapter.__init__", return_value=None
        ):
            adapter = YoutubeAdapter(None, "fake-key", "/path/")  # type: ignore
            adapter.service = mock.Mock()

            adapter.service.playlists().list().execute.return_value = {
                "items": [
                    {"snippet": {"title": "Other Playlist"}},
                    {"snippet": {"title": "Target Playlist"}},
                ]
            }

            result = adapter.playlist_exists_with_title("Target Playlist")

            self.assertTrue(result)

    def test_playlist_exists_with_title_returns_false_when_not_found(self) -> None:
        with mock.patch(
            "createbillboardplaylist.YoutubeAdapter.__init__", return_value=None
        ):
            adapter = YoutubeAdapter(None, "fake-key", "/path/")  # type: ignore
            adapter.service = mock.Mock()

            adapter.service.playlists().list().execute.return_value = {
                "items": [
                    {"snippet": {"title": "Other Playlist"}},
                ]
            }

            result = adapter.playlist_exists_with_title("Target Playlist")

            self.assertFalse(result)

    def test_playlist_exists_with_title_returns_false_for_empty_list(self) -> None:
        with mock.patch(
            "createbillboardplaylist.YoutubeAdapter.__init__", return_value=None
        ):
            adapter = YoutubeAdapter(None, "fake-key", "/path/")  # type: ignore
            adapter.service = mock.Mock()

            adapter.service.playlists().list().execute.return_value = {"items": []}

            result = adapter.playlist_exists_with_title("Target Playlist")

            self.assertFalse(result)

    def test_playlist_url_from_id_generates_correct_format(self) -> None:
        pl_id = "PL123456"
        expected_url = f"https://www.youtube.com/playlist?list={pl_id}"

        result = YoutubeAdapter._playlist_url_from_id(pl_id)

        self.assertEqual(result, expected_url)


class BillboardAdapterTests(unittest.TestCase):
    @mock.patch("createbillboardplaylist.billboard.ChartData")
    def test_get_chart_data_without_date(self, mock_chart: Any) -> None:
        result = BillboardAdapter.get_chart_data("hot-100")

        mock_chart.assert_called_with("hot-100", None)
        self.assertEqual(result, mock_chart.return_value)

    @mock.patch("createbillboardplaylist.billboard.ChartData")
    def test_get_chart_data_with_specific_date(self, mock_chart: Any) -> None:
        result = BillboardAdapter.get_chart_data("hot-100", "2024-01-01")

        mock_chart.assert_called_with("hot-100", "2024-01-01")
        self.assertEqual(result, mock_chart.return_value)


class VideoCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = VideoCache(":memory:")

    def tearDown(self) -> None:
        self.store.close()

    def test_get_video_id_returns_none_when_not_stored(self) -> None:
        result = self.store.get_video_id("test artist", "test song")

        self.assertIsNone(result)

    def test_set_and_get_mapping(self) -> None:
        self.store.set_mapping("test artist", "test song", "video123456")

        result = self.store.get_video_id("test artist", "test song")

        self.assertEqual(result, "video123456")

    def test_get_video_id_returns_none_for_different_artist_or_title(self) -> None:
        self.store.set_mapping("test artist", "test song", "video123456")

        self.assertIsNone(self.store.get_video_id("other artist", "test song"))
        self.assertIsNone(self.store.get_video_id("test artist", "other song"))

    def test_set_mapping_replaces_existing_mapping(self) -> None:
        self.store.set_mapping("test artist", "test song", "oldid123456")
        self.store.set_mapping("test artist", "test song", "newid123456")

        result = self.store.get_video_id("test artist", "test song")

        self.assertEqual(result, "newid123456")
        self.assertEqual(len(self.store.list_mappings()), 1)

    def test_remove_mapping_removes_stored_mapping(self) -> None:
        self.store.set_mapping("test artist", "test song", "video123456")
        mapping_id = self.store.list_mappings()[0][0]

        result = self.store.remove_mapping(mapping_id)

        self.assertTrue(result)
        self.assertIsNone(self.store.get_video_id("test artist", "test song"))

    def test_remove_mapping_returns_false_when_not_stored(self) -> None:
        result = self.store.remove_mapping(12345)

        self.assertFalse(result)

    def test_list_mappings_returns_all_stored_mappings(self) -> None:
        self.store.set_mapping("artist one", "song one", "video123456")
        self.store.set_mapping("artist two", "song two", "video654321")

        result = self.store.list_mappings()

        self.assertEqual(
            result,
            [
                (1, "artist one", "song one", "video123456"),
                (2, "artist two", "song two", "video654321"),
            ],
        )

    def test_search_finds_match_in_artist(self) -> None:
        self.store.set_mapping("Queen", "Bohemian Rhapsody", "video123456")
        self.store.set_mapping("Beatles", "Hey Jude", "video654321")

        result = self.store.search("queen")

        self.assertEqual(result, [(1, "Queen", "Bohemian Rhapsody", "video123456")])

    def test_search_finds_match_in_title(self) -> None:
        self.store.set_mapping("Queen", "Bohemian Rhapsody", "video123456")
        self.store.set_mapping("Beatles", "Hey Jude", "video654321")

        result = self.store.search("jude")

        self.assertEqual(result, [(2, "Beatles", "Hey Jude", "video654321")])

    def test_search_returns_multiple_matches(self) -> None:
        self.store.set_mapping("Queen", "Bohemian Rhapsody", "video123456")
        self.store.set_mapping("Queen", "Don't Stop Me Now", "video654321")

        result = self.store.search("queen")

        self.assertEqual(
            result,
            [
                (1, "Queen", "Bohemian Rhapsody", "video123456"),
                (2, "Queen", "Don't Stop Me Now", "video654321"),
            ],
        )

    def test_search_returns_empty_list_when_no_match(self) -> None:
        self.store.set_mapping("Queen", "Bohemian Rhapsody", "video123456")

        result = self.store.search("nobody")

        self.assertEqual(result, [])


class VideoCacheExtractVideoIdTests(unittest.TestCase):
    def test_extract_video_id_from_raw_id(self) -> None:
        result = VideoCache.extract_video_id("dQw4w9WgXcQ")

        self.assertEqual(result, "dQw4w9WgXcQ")

    def test_extract_video_id_from_watch_url(self) -> None:
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

        result = VideoCache.extract_video_id(url)

        self.assertEqual(result, "dQw4w9WgXcQ")

    def test_extract_video_id_from_watch_url_with_extra_params(self) -> None:
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10s"

        result = VideoCache.extract_video_id(url)

        self.assertEqual(result, "dQw4w9WgXcQ")

    def test_extract_video_id_from_short_url(self) -> None:
        url = "https://youtu.be/dQw4w9WgXcQ"

        result = VideoCache.extract_video_id(url)

        self.assertEqual(result, "dQw4w9WgXcQ")

    def test_extract_video_id_from_scheme_less_short_url(self) -> None:
        url = "youtu.be/dQw4w9WgXcQ"

        result = VideoCache.extract_video_id(url)

        self.assertEqual(result, "dQw4w9WgXcQ")

    def test_extract_video_id_from_scheme_less_watch_url(self) -> None:
        url = "www.youtube.com/watch?v=dQw4w9WgXcQ"

        result = VideoCache.extract_video_id(url)

        self.assertEqual(result, "dQw4w9WgXcQ")

    def test_extract_video_id_returns_none_for_invalid_value(self) -> None:
        result = VideoCache.extract_video_id("not a video id or url")

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
