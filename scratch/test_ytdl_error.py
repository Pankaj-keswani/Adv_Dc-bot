import yt_dlp

def test():
    try:
        print("Importing yt_dlp...")
        import yt_dlp
        print("Attempting search...")
        ydl_opts = {'quiet': False, 'nocheckcertificate': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info("ytsearch:sahiba", download=False)
        print("Success!")
    except Exception as e:
        print(f"Caught error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test()
