import yt_dlp
import urllib.request
import urllib.error

def test():
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'default_search': 'ytsearch1',
    }
    print("Extracting...")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info("ytsearch1:sahiba", download=False)
        if 'entries' in info:
            info = info['entries'][0]
        url = info.get('url')
        print(f"Extracted URL starts with: {url[:50]}...")
        
        # Test if the URL is accessible
        print("Testing URL accessibility...")
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                print(f"Success! Status: {response.status}")
        except urllib.error.HTTPError as e:
            print(f"HTTP Error: {e.code} - {e.reason}")
        except Exception as e:
            print(f"Other Error: {e}")

if __name__ == "__main__":
    test()
