from PIL import Image, ImageDraw, ImageFont, ImageFilter
from colorthief import ColorThief
from io import BytesIO
from yt_dlp import YoutubeDL
import ffmpeg
import asyncio
from aiohttp import ClientSession
import os
import html
from fontTools.ttLib import TTFont
from env import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET



headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.77 Safari/537.36"
}
ydl_opts = {
    'format': 'bestaudio',
    'extractaudio': True,
    'audioformat': 'mp3',
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'noplaylist': True,
    'nocheckcertificate': True
}


def has_glyph(font, glyph):
    for table in font['cmap'].tables:
        if ord(glyph) in table.cmap.keys():
            return True
    return False


def draw_text(draw, position, text, base_font, fill="black", anchor=None):
    cursor_pos = list(position)
    ttfont = TTFont(base_font.path)
    fallback_path = "unifont/"
    fallbacks = [
        (TTFont(fallback_path+f), ImageFont.truetype(fallback_path+f, base_font.size))
        for f in os.listdir(fallback_path)
    ]

    for letter in text:
        if has_glyph(ttfont, letter):
            font = base_font
        else:
            for (fc, imf) in fallbacks:
                if has_glyph(fc, letter):
                    print("fallback: ", letter)
                    font = imf
                    break
            else:
                font = base_font
                print(letter)
        draw.text(cursor_pos, letter, font=font, fill=fill, anchor=anchor)
        letter_size = draw.textsize(letter, font=font)
        cursor_pos[0] += letter_size[0]


def get_font_size(font: ImageFont.truetype, text: str, max_width: int) -> ImageFont.truetype:
    while font.getsize(text)[0] > max_width and font.size > 10:
        font = ImageFont.truetype(font.path, font.size - 1)
    return font


def get_lightness(colour) -> float:
    return (0.299 * colour[0] + 0.587 * colour[1] + 0.114 * colour[2]) / 255


def contrast_color(colour):
    d = 0 if get_lightness(colour) > 0.5 else 255
    return (d, d, d)


async def download_audio(ytdl, session, title, track_id, i, num_songs, template, text_colour, text_font):
    print(f"Getting audio for: {title} ({track_id})")

    query_string = f"{title} [official audio]"
    loop = asyncio.get_event_loop()
    info = await loop.run_in_executor(
        None,
        ytdl.extract_info,
        query_string,
        False
    )
    if "entries" in info:
        info = info["entries"][0]
    song_audio_url = info["url"]

    if not os.path.exists(f"temp/{track_id}.mp3"):
        async with session.get(song_audio_url) as request:
            content = await request.read()
            if not os.path.exists('temp/'): os.mkdir("temp/")
            with open(f"temp/{track_id}.mp3", "wb") as file:
                file.write(content)

    print(f"Drawing frame for: {title} ({track_id})")
    frame = template.copy()
    draw = ImageDraw.Draw(frame)
    draw.ellipse(
        (1920/2+100 - text_font.size,
        1080/2 - num_songs*text_font.size/2 + i*text_font.size + text_font.size*0.2,
        1920/2+100 - text_font.size*0.4,
        1080/2 - num_songs*text_font.size/2 + (i+1)*text_font.size - text_font.size*0.2),
        fill = text_colour
    )
    frame.save(f"temp/{track_id}.png", "PNG")

    return True


async def main():
    playlist_link = input("Enter spotify playlist link: ")
    playlist_id = playlist_link.split("/")[-1].split("?")[0]

    async with ClientSession(headers=headers) as session:
        print("Logging into Spotify API")
        async with session.post(
            "https://accounts.spotify.com/api/token",
            data = {
                "grant_type": "client_credentials",
                "client_id": SPOTIFY_CLIENT_ID,
                "client_secret": SPOTIFY_CLIENT_SECRET,
            }
        ) as request:
            json_data = await request.json()
            access_token = json_data["access_token"]
            session.headers["Authorization"] = f"Bearer {access_token}"

        print("Getting playlist data")
        async with session.get(f"https://api.spotify.com/v1/playlists/{playlist_id}") as request:
            json_data = await request.json()
            playlist_name = json_data["name"]
            playlist_subtitle = json_data["description"] or ""
            playlist_subtitle = html.unescape(playlist_subtitle)
            playlist_image_url = json_data["images"][0]["url"]
            tracks_url = json_data["tracks"]["href"]

        print("Getting track data")
        async with session.get(tracks_url) as request:
            json_data = await request.json()
            songs = [
                {
                    "id": song["track"]["id"],
                    "duration": song["track"]["duration_ms"],
                    "name": song["track"]["name"].split(" - ")[0],
                    "artist": song["track"]["artists"][0]["name"]
                } for song in json_data["items"]
            ]

        print("Creating template")
        async with session.get(playlist_image_url) as request:
            playlist_image = await request.read()
            playlist_image = Image.open(BytesIO(playlist_image))
            playlist_image = playlist_image.convert("RGB")
            playlist_image = playlist_image.resize((650, 650))

        with BytesIO() as file_object:
            playlist_image.save(file_object, "PNG")
            cf = ColorThief(file_object)
            colours = cf.get_palette(15, 100)
        try:
            with BytesIO() as file_object:
                playlist_image.crop((int(playlist_image.width*0.8), 0, playlist_image.width, playlist_image.height)).filter(ImageFilter.BoxBlur(20)).save(file_object, "PNG")
                cf = ColorThief(file_object)
                base_colour = cf.get_color(100)
        except:
            base_colour = (255, 255, 255)

        text_colour = max(colours, key = lambda c: abs(get_lightness(base_colour) - get_lightness(c)) )
        if abs(get_lightness(text_colour) - get_lightness(base_colour)) < 0.3:
            text_colour = contrast_color(base_colour)

        template = Image.new("RGB", (1920, 1080), base_colour)
        template.paste(playlist_image, (int(1920/4 - playlist_image.width/2), int(1080/2 - playlist_image.height/2)))
        draw = ImageDraw.Draw(template)
        
        title_font = ImageFont.truetype("font.ttf", 35, layout_engine=ImageFont.LAYOUT_RAQM)
        title_font = get_font_size(title_font, playlist_name, playlist_image.width)
        draw_text(
            draw,
            (int(1920/4 - playlist_image.width/2), int(1080/2 + playlist_image.height/2 + 5)),
            playlist_name,
            base_font=title_font,
            fill=text_colour
        )

        subtitle_font = ImageFont.truetype("font.ttf", 20)
        chunks = [""]
        for word in playlist_subtitle.split(" "):
            if subtitle_font.getsize(chunks[-1]+" "+word)[0] > playlist_image.width:
                chunks.append(" "+word)
            else:
                chunks[-1] += " "+word
        chunks = [chunk[1:] for chunk in chunks]
        playlist_subtitle = "\n".join(chunks)
        draw.multiline_text((int(1920/4 - playlist_image.width/2), int(1080/2 + playlist_image.height/2 + 5 + title_font.size + 2)), playlist_subtitle, font=subtitle_font, fill=text_colour)

        text_max_width = 1920/2 - 200
        text_font = ImageFont.truetype("font.ttf", 25)
        for song in songs:
            text_font = get_font_size(text_font, song["name"]+" - "+song["artist"], text_max_width)
        
        for i, song in enumerate(songs):
            draw_text(draw, (1920/2+100, 1080/2 - len(songs)*text_font.size/2 + i*text_font.size), song["name"] + " - " + song["artist"], base_font=text_font, fill=text_colour)

        print("Downloading audio and creating frames")
        with YoutubeDL(ydl_opts) as ytdl:
            coros = [
                download_audio(ytdl, session, song["name"]+" - "+song["artist"], song["id"], i, len(songs), template, text_colour, text_font)
                for i, song in enumerate(songs)
            ]
            await asyncio.gather(*coros)

        print("Creating videos")
        if not os.path.exists('output/'): os.mkdir("output/")
        videos = []
        audios = []
        for song in songs:
            track_id = song["id"]
            duration = song["duration"] / 1000
            videos.append(ffmpeg.input(f"temp/{track_id}.png", framerate=1, t=duration, loop=1))
            audios.append(ffmpeg.input(f"temp/{track_id}.mp3"))
        
        (
            ffmpeg
            .concat(*[val for pair in zip(videos, audios) for val in pair], v=1, a=1)
            .output(f"output/{playlist_name}.mp4", framerate=1, pix_fmt="yuv420p", vcodec="libx264", acodec="aac")
            .overwrite_output()
            .run()
        )
        print(f"Saved video to output/{playlist_name}.mp4!")

        if input("Remove cache? [y/n]: ").lower() == "y":
            for f in os.listdir("temp/"):
                os.remove("temp/"+f)
            os.rmdir("temp/")



asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
loop = asyncio.get_event_loop()
loop.run_until_complete(main())
