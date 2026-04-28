import yt_dlp
import time

def test_speed(query):
    # Standard options
    opts_standard = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'default_search': 'ytsearch',
    }
    
    # Optimized options
    opts_fast = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'default_search': 'ytsearch1',
        'extract_flat': True,
    }

    print(f"Testing Standard YouTube Search for: {query}")
    start = time.time()
    try:
        with yt_dlp.YoutubeDL(opts_standard) as ydl:
            ydl.extract_info(query, download=False)
        print(f"Standard took: {time.time() - start:.2f}s")
    except Exception as e:
        print(f"Standard failed: {e}")

    print(f"\nTesting Fast YouTube Search for: {query}")
    start = time.time()
    try:
        with yt_dlp.YoutubeDL(opts_fast) as ydl:
            ydl.extract_info(f"ytsearch1:{query}", download=False)
        print(f"Fast took: {time.time() - start:.2f}s")
    except Exception as e:
        print(f"Fast failed: {e}")

    print(f"\nTesting SoundCloud Search for: {query}")
    start = time.time()
    opts_standard['default_search'] = 'scsearch'
    try:
        with yt_dlp.YoutubeDL(opts_standard) as ydl:
            ydl.extract_info(query, download=False)
        print(f"SoundCloud took: {time.time() - start:.2f}s")
    except Exception as e:
        print(f"SoundCloud failed: {e}")

if __name__ == "__main__":
    test_speed("sahiba")
