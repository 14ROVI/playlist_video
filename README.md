# Spotify playlist video generator
This program creates a video version of your Spotify playlist by using the Spotify API and YouTube-dl.

To use this you must first create an application on the [Spotify developer dashboard](https://developer.spotify.com/dashboard/applications). Then create an additional file named `env.py` with the following content:
```py
SPOTIFY_CLIENT_ID = "<CLIENT ID HERE>"
SPOTIFY_CLIENT_SECRET = "<CLIENT SECRET HERE>"
```
Once you have completed those two steps you can run `generator.py`, enter the url to your playlist and it will generate the video.

The program creates a folder named `temp` where it stores the audio and visual files before merging them with ffmpeg. This is nessecary. The program does promt you if you want to keep the *cache* at the end of it's execution. If you try to generate the same playlist's video twice then it won't need to fetch the audio from YouTube again if you do decide to keep the cache so I only reccomend it in that case. Otherwise, of course, there is no point wasting the storage space anymore.