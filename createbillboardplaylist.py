#!/usr/bin/python

# This is the Create Billboard Charts YouTube Playlist script
# It is a Python script that will download some of the current Billboard charts
# and create YouTube playlists containing videos for all the songs for the charts.
# If it is run regularly, it will create new playlists each week for the new Billboard
# charts.
#
# An example of what the script creates can be seen here:
# http://www.youtube.com/user/GimmeThatHotPopMusic
#
# Copyright 2011 Adam Goforth
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

import time
import datetime
import os.path
from ConfigParser import SafeConfigParser

# GData libraries from Google
import gdata.youtube
import gdata.youtube.service

# Universal Feed Parser
import feedparser

###########################
# Utility Functions
#
# Most of these functions were taken from the YouTube API Python
# Developer's Guide
# http://code.google.com/apis/youtube/1.0/developers_guide_python.html
###########################

def get_feed_by_search_query(search_terms):
    query = gdata.youtube.service.YouTubeVideoQuery()
    query.vq = search_terms
    query.orderby = 'relevance'
    query.racy = 'include'
    query.max_results = 1
    return yt_service.YouTubeQuery(query)

def playlist_url_from_id(pl_id):
    return 'http://gdata.youtube.com/feeds/api/playlists/' + pl_id

def add_first_found_video_to_playlist(pl_id, search_terms, video_title):
    query_feed = get_feed_by_search_query(search_terms)
    # Try waiting here to make the GData rate quota happy
    time.sleep(5)

    video_id = ""
    for entry in query_feed.entry:
        video_id = entry.id.text.split('/')[-1]

    # No search results were found, so print a message and return
    if video_id == "":
        print "No search results found for '" + search_terms + "'. Moving on to the next song."
        return

    video_title = ''

    print "Adding video with info pl_id: " + pl_id + " playlist url: " + playlist_url_from_id(pl_id) + " video_id: " + video_id + " video_title: " + video_title
    playlist_video_entry = yt_service.AddPlaylistVideoEntryToPlaylist(
        playlist_url_from_id(pl_id), video_id, video_title, '')

    if isinstance(playlist_video_entry, gdata.youtube.YouTubePlaylistVideoEntry):
        print 'Video added. Title: "' + video_title + '", ID: ' + video_id

def add_new_playlist(pl_title, pl_description):
    pl_entry = yt_service.AddPlaylist(pl_title, pl_description)
    # Try waiting here to make the GData rate quota happy
    time.sleep(5)

    if isinstance(pl_entry, gdata.youtube.YouTubePlaylistEntry):
        print 'New playlist added'

    pl_id = pl_entry.id.text.split('/')[-1]
    pl_url = playlist_url_from_id(pl_id)

    print "Playlist ID: " + pl_id + ", URL: " + pl_url
    return pl_id

def playlist_exists_with_title(title):
    existing_playlists = yt_service.GetYouTubePlaylistFeed(username='default')
    for entry in existing_playlists.entry:
        if entry.title.text == title:
            return True
    return False

def add_rss_entries_to_playlist(pl_id, rss):
    song_count = 0
    for item in rss['entries']:
        song_count += 1
        if (song_count > 100):
            break

        # Parse out the rank, artist, and song title from the <title> element
        rss_title = item.title
        song_rank = rss_title[:rss_title.find(':')]
        song_name = rss_title[rss_title.find(':') + 2:]
        artist = item.artist
        query = artist + ' ' + song_name
        song_title = '#' + song_rank + ': ' + artist + ' - ' + song_name

        print 'Adding ' + song_title
        add_first_found_video_to_playlist(pl_id, query, song_title)
        # Wait here to make the GData rate quota happy
        time.sleep(15)

def create_playlist_from_feed(feed_url, chart_name, num_songs_phrase, web_url):
    # Get the songs from the Billboard RSS feed
    rss = feedparser.parse(feed_url)
    feed_date = time.strftime("%B %d, %Y", rss.entries[0].date_parsed)

    # Create a new playlist, if it doesn't already exist
    pl_title = chart_name + " - " + feed_date
    pl_description = "This playlist contains the " + num_songs_phrase + "songs in the Billboard " + chart_name + " Songs chart for the week of " + feed_date + ".  " + web_url
    pl_id = ""
    # Check for an existing playlist with the same title
    if playlist_exists_with_title(pl_title):
        print "Playlist already exists with title '" + pl_title + "'.  Delete it manually and re-run the script to recreate it."
        time.sleep(3)
        return False
    else:
        pl_id = add_new_playlist(pl_title, pl_description)
        add_rss_entries_to_playlist(pl_id, rss)
        return True

def load_config_values():
    # Load Config From settings.cfg
    scriptDir = os.path.dirname(__file__)
    if (scriptDir == ""):
        scriptDir = "."
    scriptDir = scriptDir + '/'
    configPath = scriptDir + 'settings.cfg'
    sectionName = 'accounts'

    if (not os.path.exists(configPath)):
        print "Error: No config file found. Copy settings-example.cfg to settings.cfg and customize it."
        exit()

    config = SafeConfigParser()
    config.read(configPath)

    # Do basic checks on the config file
    if not config.has_section(sectionName):
        print "Error: The config file doesn't have an accounts section. Check the config file format."
        exit()

    if not config.has_option(sectionName, 'developer_key'):
        print "Error: No developer key found in the config file.  Check the config file values."
        exit()

    if not config.has_option(sectionName, 'email'):
        print "Error: No YouTube account email found in the config file. Check the config file values."
        exit()

    if not config.has_option(sectionName, 'password'):
        print "Error: No YouTube account password found in the config file.  Check the config file values."
        exit()

    config_values = {
            'dev_key': config.get(sectionName, 'developer_key'),
            'email': config.get(sectionName, 'email'),
            'password': config.get(sectionName, 'password')
        }

    return config_values
    
def create_youtube_service(config):
    global yt_service

    # Create the service to use throughout the script
    yt_service = gdata.youtube.service.YouTubeService()

    # The YouTube API does not currently support HTTPS/SSL access.
    yt_service.ssl = False

    # The developer key for the Google API product
    yt_service.developer_key = config['dev_key']

    # Set up authentication for the YouTube user
    yt_service.email = config['email']
    yt_service.password = config['password']

    yt_service.source = 'BillboardPlaylistMaker'

    # Do the login
    yt_service.ProgrammaticLogin()


# Almost every function needs the YouTube service, so just use a global
global yt_service


if __name__ == '__main__':
    config = load_config_values()
    create_youtube_service(config)

    # Billboard Hot 100
    created = create_playlist_from_feed(
                "http://www.billboard.com/rss/charts/hot-100",
                "Hot 100",
                "",
                "http://www.billboard.com/charts/hot-100"
                )

    # Wait for 20 minutes to make the GData rate quota happy
    if created:
        time.sleep(1200)

    # Billboard Rock Songs
    created = create_playlist_from_feed(
                "http://www.billboard.com/rss/charts/rock-songs",
                "Rock",
                "top 25 ",
                "http://www.billboard.com/charts/rock-songs"
                )

    # Wait for 20 minutes to make the GData rate quota happy
    if created:
        time.sleep(1200)

    # Billboard R&B/Hip-Hop Songs 
    created = create_playlist_from_feed(
                "http://www.billboard.com/rss/charts/r-b-hip-hop-songs",
                "R&B/Hip-Hop",
                "top 50 ",
                "http://www.billboard.com/charts/r-b-hip-hop-songs"
                )

    # Wait for 20 minutes to make the GData rate quota happy
    if created:
        time.sleep(1200)

    # Billboard Dance/Club Play Songs
    created = create_playlist_from_feed(
                "http://www.billboard.com/rss/charts/dance-club-play-songs",
                "Dance/Club Play",
                "top 25 ",
                "http://www.billboard.com/charts/dance-club-play-songs"
                )

    # Wait for 20 minutes to make the GData rate quota happy
    if created:
        time.sleep(1200)

    # Billboard Pop Songs
    created = create_playlist_from_feed(
                "http://www.billboard.com/rss/charts/pop-songs",
                "Pop",
                "top 20 ",
                "http://www.billboard.com/charts/pop-songs"
                )

