import mock
import unittest

from createbillboardplaylist import PlaylistCreator


class CreatePlaylistTestCase(unittest.TestCase):
    def test_add_first_video_to_playlist(self):
        VIDEO_ID = 'test-video-id'
        PLAYLIST_ID = 'test-playlist'
        SEARCH_QUERY = 'test artist - test song title'

        billboard = mock.Mock()
        youtube = mock.Mock()
        youtube.get_video_id_for_search.return_value = VIDEO_ID

        playlist_creator = PlaylistCreator(youtube, billboard)
        playlist_creator.add_first_video_to_playlist(PLAYLIST_ID, SEARCH_QUERY)

        youtube.get_video_id_for_search.assert_called_with(SEARCH_QUERY)
        youtube.add_video_to_playlist.assert_called_with(PLAYLIST_ID, VIDEO_ID)




if __name__ == '__main__':
    unittest.main()
