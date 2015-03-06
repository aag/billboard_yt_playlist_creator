Create Billboard Charts YouTube Playlist script
===============================================
This is a Python script that will download some of the current Billboard charts
and create YouTube playlists containing videos for all the songs for the charts.
If it is run regularly, it will create new playlists each week for the
current Billboard charts.

When run, the script downloads the current charts from RSS feeds on the
Billboard website.  For each chart, it searches YouTube for a video of each
song and adds the first result to a dated playlist of the chart for the current
week.

The script creates playlists for these charts:

- Hot 100
- Pop
- Dance/Club Play
- R&B/Hip-Hop
- Rock

An example of what the script creates can be seen here:
http://www.youtube.com/user/GimmeThatHotPopMusic

Dependencies
------------
- [Google GData API Python Client 2.0](http://code.google.com/p/gdata-python-client/)
- [Universal Feed Parser 4.1](http://code.google.com/p/feedparser/)

Usage
-----
Download the Python dependencies and install them using the included
installation instructions.

Copy settings-example.cfg to settings.cfg and fill in your Google API Developer
Key and YouTube account information.  Then run:

```sh
$ python createbillboardplaylist.py
```

License
-------
This code is free software licensed under the GPL 3. See the
[COPYING](COPYING) file for details.
