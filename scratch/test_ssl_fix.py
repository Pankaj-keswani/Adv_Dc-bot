import os
import certifi
import yt_dlp

# Set the SSL certificate file
os.environ['SSL_CERT_FILE'] = certifi.where()

def test_ytdl(query):
    ytdl_format_options = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'quiet': False,
        'no_warnings': False,
        'default_search': 'scsearch',
        'source_address': '0.0.0.0'
    }

    print(f"Testing SoundCloud search with SSL FIX for: {query}")
    try:
        with yt_dlp.YoutubeDL(ytdl_format_options) as ytdl:
            info = ytdl.extract_info(f"scsearch:{query}", download=False)
            if 'entries' in info and len(info['entries']) > 0:
                print(f"SUCCESS (SoundCloud): {info['entries'][0]['title']}")
            else:
                print("FAILED (SoundCloud): No entries found")
    except Exception as e:
        print(f"ERROR (SoundCloud): {e}")

if __name__ == "__main__":
    test_ytdl("sahiba")
