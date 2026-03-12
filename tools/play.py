name = "play"
description = "Play a YouTube video"

def run(query):
    import urllib.parse
    import webbrowser
    query = str(query) if query else "song"
    url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
    webbrowser.open(url)
    return "YouTube search opened in browser."
