import yt_dlp
import sys

def test_ytdl(query):
    ytdl_format_options = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': True,
        'quiet': False,
        'no_warnings': False,
        'default_search': 'scsearch',
        'source_address': '0.0.0.0'
    }

    print(f"Testing SoundCloud search for: {query}")
    try:
        with yt_dlp.YoutubeDL(ytdl_format_options) as ytdl:
            info = ytdl.extract_info(f"scsearch:{query}", download=False)
            if 'entries' in info and len(info['entries']) > 0:
                print(f"SUCCESS (SoundCloud): {info['entries'][0]['title']}")
            else:
                print("FAILED (SoundCloud): No entries found")
    except Exception as e:
        print(f"ERROR (SoundCloud): {e}")

    print(f"\nTesting YouTube search for: {query}")
    ytdl_format_options['default_search'] = 'ytsearch'
    try:
        with yt_dlp.YoutubeDL(ytdl_format_options) as ytdl:
            info = ytdl.extract_info(f"ytsearch:{query}", download=False)
            if 'entries' in info and len(info['entries']) > 0:
                print(f"SUCCESS (YouTube): {info['entries'][0]['title']}")
            else:
                print("FAILED (YouTube): No entries found")
    except Exception as e:
        print(f"ERROR (YouTube): {e}")

if __name__ == "__main__":
    query = "sahiba"
    if len(sys.argv) > 1:
        query = sys.argv[1]
    test_ytdl(query)
