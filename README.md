Create YouTube Playlists of Music Charts
========================================

[![License](https://img.shields.io/badge/License-GPL3-blue.svg)](COPYING)

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
- [Google API v3 Client Library for Python](https://developers.google.com/api-client-library/python/)
- [Universal Feed Parser 4.1+](http://code.google.com/p/feedparser/)

Usage
-----
1. Clone the git repository.

2. Install the Python dependencies. If you have pip installed, you can use
    these commands:

    ```sh
    $ sudo pip install --upgrade google-api-python-client
    $ sudo pip install --upgrade feedparser
    ```

3. Generate a new Installed Application Client ID and download the JSON key
    from the Credentials page of your
    [Google Developer Console](https://console.developers.google.com/). Click
    the "Create a new Client ID" under OAuth and choose "Installed application"
    and "Other" in the dialog box that appears. You will have to enter some
    information about your application. Once the Client ID has been generated,
    click the "Download JSON" button and save the file with the name
    `client_secrets.json` in the root directory of your clone of the git
    repository.

4. Generate a Public API access key by clicking the "Create new Key" button.

5. Copy `settings-example.cfg` to `settings.cfg` and fill in your
    Public API access key. Then run:

    ```sh
    $ python createbillboardplaylist.py --noauth_local_webserver
    ```

6. The first time you run the script, you will have to authenticate the
    application in a web browser. Open the URL that the script outputs,
    approve the application for the YouTube Account in which you want to
    create the playlists, and enter the verification code on the command line.
    This will create a file, `oauth2.json`, which must be kept in the root
    of the git repository as long as you want to upload playlists to this
    account.

7. In subsequent runs of the script, you can run it without any command line
    arguments:

    ```sh
    $ python createbillboardplaylist.py
    ```


License
-------
This code is free software licensed under the GPL 3. See the
[LICENSE.md](LICENSE.md) file for details.
