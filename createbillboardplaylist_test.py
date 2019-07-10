import unittest

import logging
import mock

from createbillboardplaylist import PlaylistCreator

# Prevent log messages from being printed
logging.getLogger().setLevel(logging.CRITICAL)

class CreatePlaylistTestCase(unittest.TestCase):
    def test_add_first_video_to_playlist(self):
        video_id = 'test-video-id'
        playlist_id = 'test-playlist'
        search_query = 'test artist - test song title'

        billboard = mock.Mock()
        youtube = mock.Mock()
        youtube.get_video_id_for_search.return_value = video_id

        playlist_creator = PlaylistCreator(logging.getLogger(), youtube, billboard)
        playlist_creator.add_first_video_to_playlist(playlist_id, search_query)

        youtube.get_video_id_for_search.assert_called_with(search_query)
        youtube.add_video_to_playlist.assert_called_with(playlist_id, video_id)

    def test_add_first_video_to_playlist_none_found(self):
        video_id = 'test-video-id'
        playlist_id = 'test-playlist'
        search_query = 'test artist - test song title'

        billboard = mock.Mock()
        youtube = mock.Mock()
        youtube.get_video_id_for_search.return_value = None

        playlist_creator = PlaylistCreator(logging.getLogger(), youtube, billboard)
        playlist_creator.add_first_video_to_playlist(playlist_id, search_query)

        youtube.get_video_id_for_search.assert_called_with(search_query)
        youtube.add_video_to_playlist.assert_not_called()

    def test_add_chart_entries_to_playlist_single_entry(self):
        video_id = 'test-video-id'
        playlist_id = 'test-playlist'
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

 
if __name__ == '__main__':
    unittest.main()
